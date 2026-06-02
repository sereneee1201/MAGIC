# -*- coding: utf-8 -*-

import random
from typing import Any, Optional

import numpy as np

from magic.generation import Region, Rotation3D, Vector3D
from magic.utils.dtypes import SDict


def get_operation_dsl(is_indoor: bool = True) -> str:
    op = """\
add(a: Number, b: Number) -> Number  # Return the sum of `a` and `b`
subtract(a: Number, b: Number) -> Number  # Return the difference of `a` subtracted by `b`
multiply(a: Number, b: Number) -> Number  # Return the product of `a` and `b`
divide(a: Number, b: Number) -> Number  # Return the quotient of `a` divided by `b`, where `b` is non-zero
square(a: Number) -> Number  # Return the square of `a`
sqrt(a: Number) -> Number  # Return the square root of `a`, where `a` is non-negative
max(a: Number, b: Number) -> Number  # Return the maximum of `a` and `b`
min(a: Number, b: Number) -> Number  # Return the minimum of `a` and `b`
random(a: Number, b: Number) -> Number  # Return a uniformly random real number between `a` and `b`
createPositionVector(x: Number, y: Number, z: Number) -> PositionVector  # Create a three-dimensional position vector
getPositionVectorX(pos: PositionVector) -> Number  # Return the X value of `pos`
getPositionVectorY(pos: PositionVector) -> Number  # Return the Y value of `pos`
getPositionVectorZ(pos: PositionVector) -> Number  # Return the Z value of `pos`
getObjectWidth(obj: ObjectName) -> Number  # Return the width of the bounding box of `obj`
getObjectHeight(obj: ObjectName) -> Number  # Return the height of the bounding box of `obj`
getObjectDepth(obj: ObjectName) -> Number  # Return the depth of the bounding box of `obj`
getObjectMinPosition(obj: ObjectName) -> PositionVector  # Return the position of the leftmost, bottommost, and backmost corner of the bounding box of `obj` in world space
getObjectMinPositionX(obj: ObjectName) -> Number  # Return the leftmost X coordinate of the bounding box of `obj` in world space
getObjectMinPositionY(obj: ObjectName) -> Number  # Return the bottomost Y coordinate of the bounding box of `obj` in world space
getObjectMinPositionZ(obj: ObjectName) -> Number  # Return the backmost Z coordinate of the bounding box of `obj` in world space
getObjectMaxPosition(obj: ObjectName) -> PositionVector  # Return the position of the rightmost, topmost, and frontmost corner of the bounding box of `obj` in world space
getObjectMaxPositionX(obj: ObjectName) -> Number  # Return the rightmost X coordinate of the bounding box of `obj` in world space
getObjectMaxPositionY(obj: ObjectName) -> Number  # Return the topmost Y coordinate of the bounding box of `obj` in world space
getObjectMaxPositionZ(obj: ObjectName) -> Number  # Return the frontmost Z coordinate of the bounding box of `obj` in world space
getRegionWidth() -> Number  # Return the width of the region"""
    if is_indoor:
        op += """
getRegionHeight() -> Number  # Return the height of the region"""
    op += """
getRegionDepth() -> Number  # Return the depth of the region
getRegionMinPositionX() -> Number  # Return the leftmost X coordinate of the region in world space"""
    if is_indoor:
        op += """
getRegionMinPositionY() -> Number  # Return the bottomost Y coordinate of the region in world space"""
    op += """
getRegionMinPositionZ() -> Number  # Return the backmost Z coordinate of the region in world space
getRegionMaxPositionX() -> Number  # Return the rightmost X coordinate of the region in world space"""
    if is_indoor:
        op += """
getRegionMaxPositionY() -> Number  # Return the topmost Y coordinate of the region in world space"""
    op += """
getRegionMaxPositionZ() -> Number  # Return the frontmost Z coordinate of the region in world space
createRotationVector(x: Degree, y: Degree, z: Degree) -> RotationVector  # Create a three-dimensional rotation vector in degrees. Note that `Degree` is a subclass of `Number` and is bounded to the range [0, 360).
getRotationVectorX(rot: RotationVector) -> Degree  # Return the X value of `rot`
getRotationVectorY(rot: RotationVector) -> Degree  # Return the Y value of `rot`
getRotationVectorZ(rot: RotationVector) -> Degree  # Return the Z value of `rot`
getObjectRotation(obj: ObjectName) -> RotationVector  # Return the rotation of `obj` in object space
getObjectRotationX(obj: ObjectName) -> Degree  # Return the X rotation of `obj` in object space. Equivalent to `getRotationVectorX(getObjectRotation(obj))`.
getObjectRotationY(obj: ObjectName) -> Degree  # Return the Y rotation of `obj` in object space. Equivalent to `getRotationVectorY(getObjectRotation(obj))`.
getObjectRotationZ(obj: ObjectName) -> Degree  # Return the Z rotation of `obj` in object space. Equivalent to `getRotationVectorZ(getObjectRotation(obj))`."""
    return op


def get_operation_dsl_signature() -> SDict[tuple[list[type | str], type | str]]:
    return {
        "add": ([float, float], float),
        "subtract": ([float, float], float),
        "multiply": ([float, float], float),
        "divide": ([float, float], float),
        "square": ([float], float),
        "sqrt": ([float], float),
        "max": ([float, float], float),
        "min": ([float, float], float),
        "random": ([float, float], float),
        "createPositionVector": ([float, float, float], "PositionVector"),
        "getPositionVectorX": (["PositionVector"], float),
        "getPositionVectorY": (["PositionVector"], float),
        "getPositionVectorZ": (["PositionVector"], float),
        "getObjectWidth": ([str], float),
        "getObjectHeight": ([str], float),
        "getObjectDepth": ([str], float),
        "getObjectMinPosition": ([str], "PositionVector"),
        "getObjectMinPositionX": ([str], float),
        "getObjectMinPositionY": ([str], float),
        "getObjectMinPositionZ": ([str], float),
        "getObjectMaxPosition": ([str], "PositionVector"),
        "getObjectMaxPositionX": ([str], float),
        "getObjectMaxPositionY": ([str], float),
        "getObjectMaxPositionZ": ([str], float),
        "getDistanceBetweenObjects": ([str, str], float),
        "getDistanceFromFloor": ([str], float),
        "getDistanceFromWall": ([str], float),
        "getDistanceFromCeiling": ([str], float),
        "getRegionWidth": ([], float),
        "getRegionDepth": ([], float),
        "getRegionMinPositionX": ([], float),
        "getRegionMinPositionZ": ([], float),
        "getRegionMaxPositionX": ([], float),
        "getRegionMaxPositionZ": ([], float),
        "getRegionHeight": ([], float),
        "getRegionMinPositionY": ([], float),
        "getRegionMaxPositionY": ([], float),
        "createRotationVector": ([float, float, float], "RotationVector"),
        "getRotationVectorX": (["RotationVector"], float),
        "getRotationVectorY": (["RotationVector"], float),
        "getRotationVectorZ": (["RotationVector"], float),
        "getObjectRotation": ([str], "RotationVector"),
        "getObjectRotationX": ([str], float),
        "getObjectRotationY": ([str], float),
        "getObjectRotationZ": ([str], float),
    }


class OperationDslDescription(object):
    @staticmethod
    def add(a: Any, b: Any) -> str:
        return f"the sum of {a} and {b}"

    @staticmethod
    def subtract(a: Any, b: Any) -> str:
        return f"the difference of {a} subtracted by {b}"

    @staticmethod
    def multiply(a: Any, b: Any) -> str:
        return f"the product of {a} and {b}"

    @staticmethod
    def divide(a: Any, b: Any) -> str:
        return f"the quotient of {a} divided by {b}"

    @staticmethod
    def square(a: Any) -> str:
        return f"the square of {a}"

    @staticmethod
    def sqrt(a: Any) -> str:
        return f"the square root of {a}"

    @staticmethod
    def max(a: Any, b: Any) -> str:
        return f"the maximum of {a} and {b}"

    @staticmethod
    def min(a: Any, b: Any) -> str:
        return f"the minimum of {a} and {b}"

    @staticmethod
    def random(a: Any, b: Any) -> str:
        return f"a random number between {a} and {b}"

    @staticmethod
    def createPositionVector(x: Any, y: Any, z: Any) -> str:
        return f"({x}, {y}, {z})"

    @staticmethod
    def getPositionVectorX(pos: Any) -> str:
        return f"the X coordinate of {pos}"

    @staticmethod
    def getPositionVectorY(pos: Any) -> str:
        return f"the Y coordinate of {pos}"

    @staticmethod
    def getPositionVectorZ(pos: Any) -> str:
        return f"the Z coordinate of {pos}"

    @staticmethod
    def getObjectWidth(obj: Any) -> str:
        return f"the width of {obj}"

    @staticmethod
    def getObjectHeight(obj: Any) -> str:
        return f"the height of {obj}"

    @staticmethod
    def getObjectDepth(obj: Any) -> str:
        return f"the depth of {obj}"

    @staticmethod
    def getObjectMinPosition(obj: Any) -> str:
        return f"the minimum corner of {obj}"

    @staticmethod
    def getObjectMinPositionX(obj: Any) -> str:
        return f"the left position of {obj}"

    @staticmethod
    def getObjectMinPositionY(obj: Any) -> str:
        return f"the bottom position of {obj}"

    @staticmethod
    def getObjectMinPositionZ(obj: Any) -> str:
        return f"the back position of {obj}"

    @staticmethod
    def getObjectMaxPosition(obj: Any) -> str:
        return f"the maximum corner of {obj}"

    @staticmethod
    def getObjectMaxPositionX(obj: Any) -> str:
        return f"the right position of {obj}"

    @staticmethod
    def getObjectMaxPositionY(obj: Any) -> str:
        return f"the top position of {obj}"

    @staticmethod
    def getObjectMaxPositionZ(obj: Any) -> str:
        return f"the front position of {obj}"

    @staticmethod
    def getDistanceBetweenObjects(obj1: Any, obj2: Any) -> str:
        return f"the distance between {obj1} and {obj2}"

    @staticmethod
    def getDistanceFromFloor(obj: Any) -> str:
        return f"the distance from {obj} to the floor"

    @staticmethod
    def getDistanceFromWall(obj: Any) -> str:
        return f"the distance from {obj} to the nearest wall"

    @staticmethod
    def getDistanceFromCeiling(obj: Any) -> str:
        return f"the distance from {obj} to the ceiling"

    @staticmethod
    def getRegionWidth() -> str:
        return f"the width of the region"

    @staticmethod
    def getRegionHeight() -> str:
        return f"the height of the region"

    @staticmethod
    def getRegionDepth() -> str:
        return f"the depth of the region"

    @staticmethod
    def getRegionMinPositionX() -> str:
        return f"the left of the region"

    @staticmethod
    def getRegionMinPositionY() -> str:
        return f"the floor of the region"

    @staticmethod
    def getRegionMinPositionZ() -> str:
        return f"the back of the region"

    @staticmethod
    def getRegionMaxPositionX() -> str:
        return f"the right of the region"

    @staticmethod
    def getRegionMaxPositionY() -> str:
        return f"the ceiling of the region"

    @staticmethod
    def getRegionMaxPositionZ() -> str:
        return f"the front of the region"

    @staticmethod
    def createRotationVector(x: Any, y: Any, z: Any) -> str:
        return f"({x}, {y}, {z})"

    @staticmethod
    def getRotationVectorX(rot: Any) -> str:
        return f"the X rotation angle of {rot}"

    @staticmethod
    def getRotationVectorY(rot: Any) -> str:
        return f"the Y rotation angle of {rot}"

    @staticmethod
    def getRotationVectorZ(rot: Any) -> str:
        return f"the Z rotation angle of {rot}"

    @staticmethod
    def getObjectRotation(obj: Any) -> str:
        return f"the rotation of {obj}"

    @staticmethod
    def getObjectRotationX(obj: Any) -> str:
        return f"the pitch angle of {obj}"

    @staticmethod
    def getObjectRotationY(obj: Any) -> str:
        return f"the yaw angle of {obj}"

    @staticmethod
    def getObjectRotationZ(obj: Any) -> str:
        return f"the roll angle of {obj}"


class RandomNumber(float):
    def __new__(cls, a: float, b: float) -> "RandomNumber":
        a, b = sorted((a, b))
        obj = super().__new__(cls, random.uniform(a, b))
        obj.a = a
        obj.b = b
        return obj

    def __add__(self, other: Any) -> "RandomNumber":
        if isinstance(other, RandomNumber):
            return RandomNumber(self.a + other.a, self.b + other.b)
        return RandomNumber(self.a + other, self.b + other)

    def __radd__(self, other: Any) -> "RandomNumber":
        return self.__add__(other)

    def __sub__(self, other: Any) -> "RandomNumber":
        if isinstance(other, RandomNumber):
            return RandomNumber(self.a - other.a, self.b - other.b)
        return RandomNumber(self.a - other, self.b - other)

    def __rsub__(self, other: Any) -> "RandomNumber":
        if isinstance(other, RandomNumber):
            return RandomNumber(other.a - self.a, other.b - self.b)
        return RandomNumber(other - self.a, other - self.b)

    def __mul__(self, other: Any) -> "RandomNumber":
        if isinstance(other, RandomNumber):
            return RandomNumber(self.a * other.a, self.b * other.b)
        return RandomNumber(self.a * other, self.b * other)

    def __rmul__(self, other: Any) -> "RandomNumber":
        return self.__mul__(other)

    def __truediv__(self, other: Any) -> "RandomNumber":
        if isinstance(other, RandomNumber):
            if other.a == 0 or other.b == 0:
                raise ValueError("Division by zero is not allowed")
            return RandomNumber(self.a / other.b, self.b / other.a)
        if other == 0:
            raise ValueError("Division by zero is not allowed")
        return RandomNumber(self.a / other, self.b / other)

    def __rtruediv__(self, other: Any) -> "RandomNumber":
        if isinstance(other, RandomNumber):
            if self.a == 0 or self.b == 0:
                raise ValueError("Division by zero is not allowed")
            return RandomNumber(other.a / self.b, other.b / self.a)
        if self.a == 0 or self.b == 0:
            raise ValueError("Division by zero is not allowed")
        return RandomNumber(other / self.b, other / self.a)

    def __pow__(self, other: Any) -> "RandomNumber":
        if isinstance(other, RandomNumber):
            return RandomNumber(self.a**other.a, self.b**other.b)
        return RandomNumber(self.a**other, self.b**other)

    def __rpow__(self, other: Any) -> "RandomNumber":
        if isinstance(other, RandomNumber):
            return RandomNumber(other.a**self.a, other.b**self.b)
        return RandomNumber(other**self.a, other**self.b)

    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, (int, float)):
            raise NotImplementedError()
        return self.a <= other <= self.b

    def __ne__(self, other: Any) -> bool:
        return not self.__eq__(other)

    def __gt__(self, other: Any) -> bool:
        if not isinstance(other, (int, float)):
            raise NotImplementedError()
        return self.a > other

    def __ge__(self, other: Any) -> bool:
        return self.__gt__(other) or self.__eq__(other)

    def __lt__(self, other: Any) -> bool:
        if not isinstance(other, (int, float)):
            raise NotImplementedError()
        return self.b < other

    def __le__(self, other: Any) -> bool:
        return self.__lt__(other) or self.__eq__(other)


class OperationDsl(object):
    def __init__(self) -> None:
        self.region: Optional[Region] = None
        self.sol: Optional[int] = None

    def set_region_(self, region: Region) -> None:
        if not isinstance(region, Region):
            raise TypeError(f"Expected a Region instance, got {type(region)}")
        self.region = region

    def set_solution_index_(self, index: int) -> None:
        if not isinstance(index, int):
            raise ValueError(f"Solution index must be an integer, got {index}")
        self.sol = index

    def add(self, a: float, b: float) -> float:
        return a + b

    def subtract(self, a: float, b: float) -> float:
        return a - b

    def multiply(self, a: float, b: float) -> float:
        return a * b

    def divide(self, a: float, b: float) -> float:
        if b == 0:
            raise ValueError("Division by zero is not allowed")
        return a / b

    def square(self, a: float) -> float:
        return a**2

    def sqrt(self, a: float) -> float:
        if a < 0:
            raise ValueError("Square root of negative number is not allowed")
        return a**0.5

    def max(self, a: float, b: float) -> float:
        return max(a, b)

    def min(self, a: float, b: float) -> float:
        return min(a, b)

    def random(self, a: float, b: float) -> RandomNumber:
        return RandomNumber(a, b)

    def createPositionVector(self, x: float, y: float, z: float) -> Vector3D:
        return Vector3D(x=x, y=y, z=z)

    def getPositionVectorX(self, pos: Vector3D) -> float:
        return pos.x

    def getPositionVectorY(self, pos: Vector3D) -> float:
        return pos.y

    def getPositionVectorZ(self, pos: Vector3D) -> float:
        return pos.z

    def getObjectWidth(self, obj: str) -> float:
        return self.region.objects[obj].dimensions.width

    def getObjectHeight(self, obj: str) -> float:
        return self.region.objects[obj].dimensions.height

    def getObjectDepth(self, obj: str) -> float:
        return self.region.objects[obj].dimensions.depth

    def getObjectMinPosition(self, obj: str) -> Vector3D:
        return self.region.objects[obj].get_min_vertex(self.sol)

    def getObjectMinPositionX(self, obj: str) -> float:
        return self.getObjectMinPosition(obj).x

    def getObjectMinPositionY(self, obj: str) -> float:
        return self.getObjectMinPosition(obj).y

    def getObjectMinPositionZ(self, obj: str) -> float:
        return self.getObjectMinPosition(obj).z

    def getObjectMaxPosition(self, obj: str) -> Vector3D:
        return self.region.objects[obj].get_max_vertex(self.sol)

    def getObjectMaxPositionX(self, obj: str) -> float:
        return self.getObjectMaxPosition(obj).x

    def getObjectMaxPositionY(self, obj: str) -> float:
        return self.getObjectMaxPosition(obj).y

    def getObjectMaxPositionZ(self, obj: str) -> float:
        return self.getObjectMaxPosition(obj).z

    def getDistanceBetweenObjects(self, obj1: str, obj2: str) -> float:
        min1 = np.array(
            [self.getObjectMinPositionX(obj1), self.getObjectMinPositionY(obj1), self.getObjectMinPositionZ(obj1)]
        )
        max1 = np.array(
            [self.getObjectMaxPositionX(obj1), self.getObjectMaxPositionY(obj1), self.getObjectMaxPositionZ(obj1)]
        )
        min2 = np.array(
            [self.getObjectMinPositionX(obj2), self.getObjectMinPositionY(obj2), self.getObjectMinPositionZ(obj2)]
        )
        max2 = np.array(
            [self.getObjectMaxPositionX(obj2), self.getObjectMaxPositionY(obj2), self.getObjectMaxPositionZ(obj2)]
        )
        gap = np.maximum(0, np.maximum(min2 - max1, min1 - max2))
        min_gap = np.linalg.norm(gap)
        if min_gap > 0:
            return min_gap.item()
        else:
            overlap = np.minimum(max1, max2) - np.maximum(min1, min2)
            return -np.min(overlap).item()

    def getDistanceFromFloor(self, obj: str) -> float:
        return self.getObjectMinPositionY(obj)

    def getDistanceFromWall(self, obj: str) -> float:
        return min(
            self.getObjectMinPositionX(obj) - self.getRegionMinPositionX(),
            self.getRegionMaxPositionZ() - self.getObjectMaxPositionZ(obj),
            self.getRegionMaxPositionX() - self.getObjectMaxPositionX(obj),
            self.getObjectMinPositionZ(obj) - self.getRegionMinPositionZ(),
        )

    def getDistanceFromCeiling(self, obj: str) -> float:
        return self.getRegionHeight() - self.getObjectMaxPositionY(obj)

    def getRegionWidth(self) -> float:
        return self.region.shape.width

    def getRegionHeight(self) -> float:
        return self.region.shape.height

    def getRegionDepth(self) -> float:
        return self.region.shape.depth

    def getRegionMinPositionX(self) -> float:
        return self.region.shape.min_vertex.x

    def getRegionMinPositionY(self) -> float:
        return 0.0

    def getRegionMinPositionZ(self) -> float:
        return self.region.shape.min_vertex.y

    def getRegionMaxPositionX(self) -> float:
        return self.region.shape.max_vertex.x

    def getRegionMaxPositionY(self) -> float:
        return self.getRegionHeight()

    def getRegionMaxPositionZ(self) -> float:
        return self.region.shape.max_vertex.y

    def createRotationVector(self, x: float, y: float, z: float) -> Rotation3D:
        return Rotation3D(x=x, y=y, z=z)

    def getRotationVectorX(self, rot: Rotation3D) -> float:
        return rot.x

    def getRotationVectorY(self, rot: Rotation3D) -> float:
        return rot.y

    def getRotationVectorZ(self, rot: Rotation3D) -> float:
        return rot.z

    def getObjectRotation(self, obj: str) -> Rotation3D:
        return self.region.objects[obj].rotation[self.sol]

    def getObjectRotationX(self, obj: str) -> float:
        return self.getObjectRotation(obj).x

    def getObjectRotationY(self, obj: str) -> float:
        return self.getObjectRotation(obj).y

    def getObjectRotationZ(self, obj: str) -> float:
        return self.getObjectRotation(obj).z
