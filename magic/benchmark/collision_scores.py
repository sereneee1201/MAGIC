# -*- coding: utf-8 -*-

import numpy as np
import trimesh
from trimesh import Trimesh

from magic.generation import Dimensions3D, RegionShape, Rotation3D, Vector3D
from magic.utils.maths import clamp
from magic.utils.mesh import create_bbox


def _compute_boolean_intersection(mesh1: Trimesh, mesh2: Trimesh) -> float:
    inter_mesh = trimesh.boolean.intersection([mesh1, mesh2], engine="manifold", check_volume=False)
    return 0.0 if inter_mesh is None or inter_mesh.volume is None else inter_mesh.volume.item()


def object_collision_score(
    dims1: Dimensions3D, pos1: Vector3D, rot1: Rotation3D, dims2: Dimensions3D, pos2: Vector3D, rot2: Rotation3D
) -> float:
    mesh1 = create_bbox(dims1, pos1, rot1)
    mesh2 = create_bbox(dims2, pos2, rot2)
    inter_vol = _compute_boolean_intersection(mesh1, mesh2)
    union_vol = dims1.volume + dims2.volume - inter_vol
    return 0.0 if union_vol <= 0.0 else clamp(inter_vol / union_vol, 0.0, 1.0)  # 0 is the best score


def region_containment_score(
    region: RegionShape, dims: Dimensions3D, pos: Vector3D, rot: Rotation3D, alpha: float = 0.8
) -> float:
    def create_room_mesh() -> Trimesh:
        height = dims.height + pos.y + 10 if region.height is None else region.height  # 10 is a buffer
        center = region.shifted_center
        room = trimesh.creation.box(extents=(region.width, height, region.depth))
        room.apply_translation((center.x, height / 2, -center.y))
        return room

    def compute_min_distance(room_mesh: Trimesh, obj_mesh: Trimesh) -> float:
        room_min, room_max = room_mesh.bounds
        obj_min, obj_max = obj_mesh.bounds
        gap = np.maximum(0, np.maximum(room_min - obj_max, obj_min - room_max))
        return np.linalg.norm(gap).item()  # euclidean norm of the gap vector; 0 if (partially) inside

    def compute_score(room_mesh: Trimesh, alpha: float) -> float:
        obj_mesh = create_bbox(dims, pos, rot)
        score_vol = _compute_boolean_intersection(room_mesh, obj_mesh) / dims.volume  # intersection/object
        min_dist = compute_min_distance(room_mesh, obj_mesh)  # Distance between the object and the room
        score_dist = 1 / (1 + min_dist)  # 1 if min_dist == 0, approaches 0 as min_dist increases
        score = alpha * score_vol + (1 - alpha) * score_dist  # Final score
        return clamp(score, 0.0, 1.0)  # 1 is the best score

    alpha = clamp(alpha, 0, 1)
    room_mesh = create_room_mesh()
    score = compute_score(room_mesh, alpha)
    return score
