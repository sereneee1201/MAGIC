# -*- coding: utf-8 -*-

import random
from typing import Any, Optional

import numpy as np
import trimesh
from scipy.spatial.transform import Rotation as R

from magic.generation import Dimensions3D, Region, Rotation3D, Vector3D
from magic.generation.dsl.operations import OperationDsl, RandomNumber
from magic.utils.dtypes import SDict
from magic.utils.mesh import create_bbox


def get_constraint_dsl() -> str:
    constraints = """\
mustEqualTo(a: Number, b: Number)  # `a` and `b` must be equal
mustNotEqualTo(a: Number, b: Number)  # `a` and `b` must not be equal
mustGreaterThan(a: Number, b: Number)  # `a` must be greater than `b`
mustGreaterThanOrEqualTo(a: Number, b: Number)  # `a` must be greater than or equal to `b`
mustLessThan(a: Number, b: Number)  # `a` must be less than `b`
mustLessThanOrEqualTo(a: Number, b: Number)  # `a` must be less than or equal to `b`
allowCollide(obj1: ObjectName, obj2: ObjectName)  # By default, every pair of objects in a region must not collide. This constraint allows `obj1` and `obj2` to collide, if required by the user.
allowOutside(obj: ObjectName)  # By default, every object is placed inside its assigned region. This constraint allows `obj` to be placed outside its assigned region, if required by the user."""
    return constraints


def get_constraint_dsl_signature() -> SDict[tuple[list[type | str], None]]:
    return {
        "mustEqualTo": ([float, float], None),
        "mustNotEqualTo": ([float, float], None),
        "mustGreaterThan": ([float, float], None),
        "mustGreaterThanOrEqualTo": ([float, float], None),
        "mustLessThan": ([float, float], None),
        "mustLessThanOrEqualTo": ([float, float], None),
        "mustVisible": (["PositionVector", str], None),
        "mustOcclude": (["PositionVector", str, str], None),
        "allowCollide": ([str, str], None),
        "allowOutside": ([str], None),
        "alignsAxis": ([str, str, str], None),
        "mustFace": ([str, str], None),
    }


class ConstraintDslDescription(object):
    @staticmethod
    def mustEqualTo(a: Any, b: Any) -> str:
        return f"{a} is equal to {b}"

    @staticmethod
    def mustNotEqualTo(a: Any, b: Any) -> str:
        return f"{a} is not equal to {b}"

    @staticmethod
    def mustGreaterThan(a: Any, b: Any) -> str:
        return f"{a} is greater than {b}"

    @staticmethod
    def mustGreaterThanOrEqualTo(a: Any, b: Any) -> str:
        return f"{a} is greater than or equal to {b}"

    @staticmethod
    def mustLessThan(a: Any, b: Any) -> str:
        return f"{a} is less than {b}"

    @staticmethod
    def mustLessThanOrEqualTo(a: Any, b: Any) -> str:
        return f"{a} is less than or equal to {b}"

    @staticmethod
    def mustVisible(pos: Any, obj: str) -> str:
        return f"{obj} is visible from {pos}"

    @staticmethod
    def mustOcclude(pos: Any, obj1: str, obj2: str) -> str:
        return f"{obj1} is not visible from {pos} because it is occluded by {obj2}"

    @staticmethod
    def alignsAxis(obj1: str, obj2: str, axis: str) -> str:
        return f"{obj1} and {obj2} align along the {axis.upper()} axis"

    @staticmethod
    def mustFace(obj1: str, obj2: str) -> str:
        return f"{obj1} faces {obj2}"


class ConstraintDsl(object):
    def __init__(self, op: OperationDsl) -> None:
        self.op = op
        self.region: Optional[Region] = None
        self.sol: Optional[int] = None

    def set_region_(self, region: Region) -> None:
        if not isinstance(region, Region):
            raise TypeError(f"Expected a Region instance, got {type(region)}")
        self.region = region
        self.op.set_region_(region)

    def set_solution_index_(self, index: int) -> None:
        if not isinstance(index, int):
            raise ValueError(f"Solution index must be an integer, got {index}")
        self.sol = index
        self.op.set_solution_index_(index)

    def mustEqualTo(self, a: float, b: float) -> bool:
        return a == b if isinstance(b, RandomNumber) else abs(a - b) <= 1e-6

    def mustNotEqualTo(self, a: float, b: float) -> bool:
        return not self.mustEqualTo(a, b)

    def mustGreaterThan(self, a: float, b: float) -> bool:
        return a > b

    def mustGreaterThanOrEqualTo(self, a: float, b: float) -> bool:
        return self.mustGreaterThan(a, b) or self.mustEqualTo(a, b)

    def mustLessThan(self, a: float, b: float) -> bool:
        return a < b

    def mustLessThanOrEqualTo(self, a: float, b: float) -> bool:
        return self.mustLessThan(a, b) or self.mustEqualTo(a, b)

    def __is_bbox_completely_visible(self, start_pos: Vector3D, target_obj: str, other_objs: list[str]) -> SDict[Any]:
        def sample_bbox_surface(dims: Dimensions3D, pos: Vector3D, rot: Rotation3D) -> np.ndarray:
            aabb_min = Vector3D(x=-dims.width / 2, y=-dims.height / 2, z=-dims.depth / 2)
            aabb_max = Vector3D(x=dims.width / 2, y=dims.height / 2, z=dims.depth / 2)
            random_x = lambda: random.uniform(aabb_min.x, aabb_max.x)
            random_y = lambda: random.uniform(aabb_min.y, aabb_max.y)
            random_z = lambda: random.uniform(aabb_min.z, aabb_max.z)
            samples = []
            for _ in range(round(dims.height * dims.depth * 100)):
                samples.append([aabb_min.x, random_y(), random_z()])
                samples.append([aabb_max.x, random_y(), random_z()])
            for _ in range(round(dims.width * dims.depth * 100)):
                samples.append([random_x(), aabb_min.y, random_z()])
                samples.append([random_x(), aabb_max.y, random_z()])
            for _ in range(round(dims.width * dims.height * 100)):
                samples.append([random_x(), random_y(), aabb_min.z])
                samples.append([random_x(), random_y(), aabb_max.z])
            rotation = R.from_euler("xyz", -np.radians([rot.x, rot.y, -rot.z]))
            rotated = rotation.apply(samples)
            translated = rotated + np.array([pos.x, pos.y, -pos.z])
            return translated

        if len(other_objs) == 0:
            return {"blocked": False, "by": set()}

        samples = sample_bbox_surface(
            self.region.objects[target_obj].dimensions,
            self.region.objects[target_obj].position[self.sol],
            self.region.objects[target_obj].rotation[self.sol],
        )
        if len(samples) == 0:
            return {"blocked": False, "by": set()}

        # build a scene with all other bounding boxes
        bboxs = []
        tri2name = []
        for obj_name in other_objs:
            bbox = create_bbox(
                self.region.objects[obj_name].dimensions,
                self.region.objects[obj_name].position[self.sol],
                self.region.objects[obj_name].rotation[self.sol],
            )
            bboxs.append(bbox)
            tri2name.extend(obj_name for _ in range(len(bbox.faces)))
        if len(bboxs) == 0:
            return {"blocked": False, "by": set()}

        # raycast from the start position to each sample point
        start_pt = np.array([start_pos.x, start_pos.y, -start_pos.z])
        origins = np.repeat([start_pt], len(samples), axis=0)
        directions = samples - start_pt
        lengths = np.linalg.norm(directions, axis=1)
        directions = directions / (lengths[:, None] + 1e-8)
        scene = trimesh.util.concatenate(bboxs)
        ray_intersector = trimesh.ray.ray_triangle.RayMeshIntersector(scene)
        locations, index_ray, index_tri = ray_intersector.intersects_location(
            ray_origins=origins, ray_directions=directions, multiple_hits=False
        )
        blockers = set()
        for i, length in enumerate(lengths):
            if i in index_ray:
                hit_loc = locations[index_ray == i][0]
                hit_dist = np.linalg.norm(hit_loc - start_pt)
                if hit_dist < length - 1e-6:  # epsilon for numeric stability
                    tri_index = index_tri[index_ray == i][0]
                    blockers.add(tri2name[tri_index])
        return {"blocked": len(blockers) > 0, "by": blockers}

    def mustVisible(self, pos: Vector3D, obj: str) -> bool:
        other_objs = [name for name in self.region.objects if name != obj]
        visibility = self.__is_bbox_completely_visible(pos, obj, other_objs)
        return visibility["blocked"]

    def mustOcclude(self, pos: Vector3D, obj1: str, obj2: str) -> bool:
        other_objs = [name for name in self.region.objects if name != obj1]
        visibility = self.__is_bbox_completely_visible(pos, obj1, other_objs)
        return visibility["blocked"] and obj2 in visibility["by"]

    def allowCollide(self, obj1: str, obj2: str) -> bool:
        return True

    def allowOutside(self, obj: str) -> bool:
        return True

    def mustFace(self, obj1: str, obj2: str) -> bool:
        start_pt = np.array(
            [
                self.region.objects[obj1].position[self.sol].x,
                self.region.objects[obj1].position[self.sol].y,
                -self.region.objects[obj1].position[self.sol].z,
            ]
        )
        rotation = R.from_euler(
            "xyz",
            -np.radians(
                [self.op.getObjectRotationX(obj1), self.op.getObjectRotationY(obj1), -self.op.getObjectRotationZ(obj1)]
            ),
        )
        forward = rotation.apply([0, 0, -1])
        target_bbox = create_bbox(
            self.region.objects[obj2].dimensions,
            self.region.objects[obj2].position[self.sol],
            self.region.objects[obj2].rotation[self.sol],
        )
        origins = np.atleast_2d(start_pt)
        directions = np.atleast_2d(forward)
        locations, index_ray, index_tri = target_bbox.ray.intersects_location(
            ray_origins=origins, ray_directions=directions, multiple_hits=False
        )
        return len(locations) > 0
