# -*- coding: utf-8 -*-

from math import radians

import numpy as np
import trimesh
import trimesh.transformations as tf
from numpy._typing import _ArrayLike
from scipy.spatial.transform import Rotation as R

from magic.generation import Dimensions3D, Rotation3D, Vector3D


def create_bbox(dims: Dimensions3D, pos: Vector3D, rot: Rotation3D) -> trimesh.Trimesh:
    Rx = tf.rotation_matrix(radians(-rot.x), [1, 0, 0])
    Ry = tf.rotation_matrix(radians(-rot.y), [0, 1, 0])
    Rz = tf.rotation_matrix(radians(rot.z), [0, 0, 1])
    bbox = trimesh.creation.box(extents=(dims.width, dims.height, dims.depth))
    bbox.apply_transform(tf.concatenate_matrices(Ry, Rz, Rx))
    bbox.apply_translation((pos.x, pos.y, -pos.z))
    return bbox


def rotate_in_lhs(points: _ArrayLike, angles: _ArrayLike, order: str = "xzy", degrees: bool = True):
    angles_rad = np.deg2rad(angles) if degrees else np.asarray(angles)
    angle_map = {"x": angles_rad[0], "y": angles_rad[1], "z": angles_rad[2]}
    combined_matrix = np.eye(3)
    for axis in order:
        theta = angle_map[axis]
        cos_t, sin_t = np.cos(theta), np.sin(theta)
        if axis == "x":
            # CCW rotation around X moves Y towards Z
            rot_matrix = np.array([[1, 0, 0], [0, cos_t, -sin_t], [0, sin_t, cos_t]])
        elif axis == "y":
            # CCW rotation around Y moves Z towards X
            rot_matrix = np.array([[cos_t, 0, sin_t], [0, 1, 0], [-sin_t, 0, cos_t]])
        elif axis == "z":
            # CCW rotation around Z moves X towards Y
            rot_matrix = np.array([[cos_t, -sin_t, 0], [sin_t, cos_t, 0], [0, 0, 1]])
        else:
            raise ValueError(f"Invalid axis '{axis}' in `order`. Must be 'x', 'y', or 'z'.")
        combined_matrix = rot_matrix @ combined_matrix
    rotated = R.from_matrix(combined_matrix).apply(np.atleast_2d(points))
    return rotated.squeeze() if np.asarray(points).ndim == 1 else rotated
