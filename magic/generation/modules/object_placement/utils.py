# -*- coding: utf-8 -*-

from itertools import combinations
from typing import Optional

import numpy as np

from magic.benchmark.collision_scores import object_collision_score
from magic.generation import AnticipatedObject, Dimensions3D, Region, Rotation3D, Vector2D, Vector3D
from magic.utils.dtypes import SDict


def is_collided(obj1: AnticipatedObject, obj2: AnticipatedObject, eps: float = 1e-8) -> bool:
    return (
        object_collision_score(
            obj1.dimensions,
            obj1.position[-1],
            obj1.rotation[-1],
            obj2.dimensions,
            obj2.position[-1],
            obj2.rotation[-1],
        )
        > eps
    )


def closest_rot_y_on_wall(rot_y: float) -> float:
    while rot_y < 0:
        rot_y += 360
    rot_y %= 360
    if rot_y < 45 or rot_y >= 315:
        return 0.0
    elif 45 <= rot_y < 135:
        return 90.0
    elif 135 <= rot_y < 225:
        return 180.0
    else:
        return 270.0


def clip_object_within_region(
    obj_dims: Dimensions3D,
    obj_pos: Vector3D,
    obj_rot: Rotation3D,
    region_min: Vector2D,
    region_max: Vector2D,
    region_height: Optional[float],
) -> Vector3D:
    obb = AnticipatedObject.get_obb(obj_dims, obj_pos, obj_rot)
    min_values = [region_min.x, 0.0, region_min.y]
    max_values = [region_max.x, region_height or np.inf, region_max.y]
    clamped = np.clip(obb, min_values, max_values)
    diff = clamped - obb
    adjust = Vector3D(
        x=float(max(diff[:, 0], key=abs)), y=float(max(diff[:, 1], key=abs)), z=float(max(diff[:, 2], key=abs))
    )
    return obj_pos + adjust


def hang_wall_or_ceiling(region: Region, obj_name: str, pos: Vector3D, rot: Rotation3D) -> tuple[Vector3D, Rotation3D]:
    obj = region.objects[obj_name]
    new_rot = Rotation3D(x=0.0, y=closest_rot_y_on_wall(rot.y), z=rot.z) if obj.hanged_on_wall else rot
    new_pos = (
        clip_object_within_region(
            obj.dimensions, pos, new_rot, region.shape.min_vertex, region.shape.max_vertex, region.shape.height
        )
        if obj_name not in region.allowed_outside
        else pos
    )
    if obj.hanged_on_wall:
        match new_rot.y:
            case 0.0:
                new_pos.z = region.shape.min_vertex.y + obj.dimensions.depth / 2
            case 90.0:
                new_pos.x = region.shape.min_vertex.x + obj.dimensions.depth / 2
            case 180.0:
                new_pos.z = region.shape.max_vertex.y - obj.dimensions.depth / 2
            case 270.0:
                new_pos.x = region.shape.max_vertex.x - obj.dimensions.depth / 2
            case _:
                raise RuntimeError(f"Unexpected yaw angle on wall: {new_rot.y}")
    if obj.hanged_from_ceiling and not obj.supported_from_below and region.shape.height is not None:
        new_pos.y = region.shape.height - obj.get_oriented_dimensions(obj.dimensions, new_rot).height / 2
    return new_pos, new_rot


def resolve_collisions(
    objects: SDict[AnticipatedObject],
    region: Region,
    max_iters: int = 100,
    max_step: float = 1e-1,
    min_step: float = 1e-3,
    repulsion_strength: float = 1.0,
    containment_strength: float = 1.0,
    hanging_strength: float = 1.0,
    eps: float = 1e-8,
) -> SDict[AnticipatedObject]:
    _objects = {
        oname: AnticipatedObject(
            hanged_on_wall=obj.hanged_on_wall,
            hanged_from_ceiling=obj.hanged_from_ceiling,
            dimensions=obj.dimensions,
            position=[obj.position[-1]],
            rotation=[obj.rotation[-1]],
        )
        for oname, obj in objects.items()
    }
    for i in range(max_iters):
        step = (min_step - max_step) * i / (max_iters - 1) + max_step

        # get all pairs of collided objects
        collision_pairs: list[tuple[str, str]] = []
        for o1_name, o2_name in combinations(_objects.keys(), 2):
            o1_name, o2_name = sorted((o1_name, o2_name))
            if (o1_name, o2_name) in region.allowed_collision:
                continue
            if is_collided(_objects[o1_name], _objects[o2_name], eps=eps):
                collision_pairs.append((o1_name, o2_name))

        force_map = {oname: Vector3D() for oname in _objects.keys()}

        # calculate repulsion forces from object-object collisions
        for o1_name, o2_name in collision_pairs:
            rep_dir = _objects[o1_name].position[-1] - _objects[o2_name].position[-1]
            if rep_dir.magnitude > eps:
                rep_force = rep_dir.normalized * step * repulsion_strength
                force_map[o1_name] += rep_force
                force_map[o2_name] -= rep_force

        # calculate remaining forces for each object
        for oname in _objects.keys():
            # containment force
            con_dir = Vector3D()
            if (v := region.shape.min_vertex.x - _objects[oname].get_min_vertex(-1).x) > 0:
                con_dir += Vector3D(x=v, y=0, z=0)
            if (v := region.shape.max_vertex.x - _objects[oname].get_max_vertex(-1).x) < 0:
                con_dir += Vector3D(x=v, y=0, z=0)
            if (v := -_objects[oname].get_min_vertex(-1).y) > 0:
                con_dir += Vector3D(x=0, y=v, z=0)
            if (
                region.shape.height is not None
                and (v := region.shape.height - _objects[oname].get_max_vertex(-1).y) < 0
            ):
                con_dir += Vector3D(x=0, y=v, z=0)
            if (v := region.shape.min_vertex.y - _objects[oname].get_min_vertex(-1).z) > 0:
                con_dir += Vector3D(x=0, y=0, z=v)
            if (v := region.shape.max_vertex.y - _objects[oname].get_max_vertex(-1).z) < 0:
                con_dir += Vector3D(x=0, y=0, z=v)
            if con_dir.magnitude > eps:
                force_map[oname] += con_dir.normalized * step * containment_strength

            # hanging force
            if _objects[oname].hanged_on_wall:
                wall_dir = Vector3D()
                match _objects[oname].rotation[-1].y:
                    case 0.0:
                        wall_dir += Vector3D(z=region.shape.min_vertex.y - _objects[oname].get_min_vertex(-1).z)
                    case 90.0:
                        wall_dir += Vector3D(x=region.shape.min_vertex.x - _objects[oname].get_min_vertex(-1).x)
                    case 180.0:
                        wall_dir += Vector3D(z=region.shape.max_vertex.y - _objects[oname].get_max_vertex(-1).z)
                    case 270.0:
                        wall_dir += Vector3D(x=region.shape.max_vertex.x - _objects[oname].get_max_vertex(-1).x)
                    case _:
                        raise RuntimeError(f"Unexpected yaw angle: {_objects[oname].rotation[-1].y}")
                if wall_dir.magnitude > eps:
                    force_map[oname] += wall_dir.normalized * step * hanging_strength
            if region.shape.height is not None and _objects[oname].hanged_from_ceiling:
                ceiling_dir = Vector3D(y=region.shape.height - _objects[oname].get_max_vertex(-1).y)
                if ceiling_dir.magnitude > eps:
                    force_map[oname] += ceiling_dir.normalized * step * hanging_strength

        # break early if no force needs to be applied
        if all(force == Vector3D() for force in force_map.values()):
            break

        # apply the calculated movements to the objects
        for oname, force in force_map.items():
            _objects[oname].position.append(_objects[oname].position[-1] + force)
    return _objects
