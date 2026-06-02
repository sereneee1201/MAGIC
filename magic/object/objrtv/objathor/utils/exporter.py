# -*- coding: utf-8 -*-

import os
import shutil
from math import pi
from os import getcwd
from os.path import abspath, dirname, exists, join
from tempfile import NamedTemporaryFile
from typing import Optional
from uuid import uuid4

import compress_pickle
import numpy as np
from trimesh import Trimesh
from trimesh.transformations import concatenate_matrices, rotation_matrix
from trimesh.visual.texture import TextureVisuals

from magic.blender import brender
from magic.constants import OBJATHOR_ASSETS_DIR
from magic.object.objrtv.objathor.utils.asset import has_asset
from magic.utils.dtypes import PathLike
from magic.utils.misc import format_error, tsprint


def _rotate(mesh: Trimesh, rot_y_radian: Optional[float] = None) -> None:
    rot_y_radian = (-rot_y_radian or 0.0) + pi
    Rx = rotation_matrix(0.0, [-1, 0, 0])
    Ry = rotation_matrix(rot_y_radian, [0, -1, 0])
    Rz = rotation_matrix(0.0, [0, 0, 1])
    mesh.apply_transform(concatenate_matrices(Rz, Ry, Rx))


def _normalize(mesh: Trimesh) -> None:
    size = mesh.bounds[1] - mesh.bounds[0]
    size[size == 0.0] = 1.0
    scale_factors = 1.0 / size
    mesh.vertices *= scale_factors


def objathor_to_obj(
    uid: str,
    output_obj: Optional[PathLike] = None,
    rot_y_radian: Optional[float] = None,
    albedo_path: Optional[PathLike] = None,
    emission_path: Optional[PathLike] = None,
    normal_path: Optional[PathLike] = None,
    roughness: Optional[float] = None,
    metallic: Optional[float] = None,
) -> bool:
    if not has_asset(uid):
        tsprint(f"[objathor_to_obj] Asset {uid} not found in ObjaTHOR database")
        return False
    output_obj = join(abspath(getcwd()), f"{uid}.obj") if output_obj is None else output_obj
    output_dir = dirname(output_obj)
    if output_dir != "" and not exists(output_dir):
        os.makedirs(output_dir)

    # extract data
    data = compress_pickle.load(join(join(OBJATHOR_ASSETS_DIR, uid), f"{uid}.pkl.gz"))
    vertices = np.array([[v["x"], v["y"], v["z"]] for v in data["vertices"]])
    faces = np.array(data["triangles"]).reshape(-1, 3)
    normals = np.array([[n["x"], n["y"], n["z"]] for n in data["normals"]])
    uvs = np.array([[uv["x"], uv["y"]] for uv in data["uvs"]])

    # build mesh
    mesh = Trimesh(vertices=vertices, faces=faces, vertex_normals=normals, visual=TextureVisuals(uv=uvs))
    mesh.vertices -= mesh.bounds.mean(axis=0)
    _rotate(mesh, rot_y_radian=rot_y_radian)
    mesh.export(output_obj)
    os.remove(join(output_dir, "material_0.png"))
    os.remove(join(output_dir, "material.mtl"))
    if not exists(output_obj):
        tsprint(f"[objathor_to_obj] Trimesh failed to export {output_obj}")
        return False

    # postprocess using Blender
    tuid = uuid4().hex[:8]
    with (
        NamedTemporaryFile(prefix=f"tmp_{tuid}_albedo_", suffix=".jpg") as tf1,
        NamedTemporaryFile(prefix=f"tmp_{tuid}_emission_", suffix=".jpg") as tf2,
        NamedTemporaryFile(prefix=f"tmp_{tuid}_normal_", suffix=".jpg") as tf3,
    ):
        tf1.close(); tf2.close(); tf3.close();
        if albedo_path is not None:
            if exists(albedo_path):
                shutil.copy(albedo_path, tf1.name)
                _albedo_path = f'r"{tf1.name}"'
            else:
                tsprint(f"[objathor_to_obj] Albedo texture {albedo_path} does not exist, skipping")
                _albedo_path = "None"
        else:
            _albedo_path = "None"
        if emission_path is not None:
            if exists(emission_path):
                shutil.copy(emission_path, tf2.name)
                _emission_path = f'r"{tf2.name}"'
            else:
                tsprint(f"[objathor_to_obj] Emission texture {emission_path} does not exist, skipping")
                _emission_path = "None"
        else:
            _emission_path = "None"
        if normal_path is not None:
            if exists(normal_path):
                shutil.copy(normal_path, tf3.name)
                _normal_path = f'r"{tf3.name}"'
            else:
                tsprint(f"[objathor_to_obj] Normal texture {normal_path} does not exist, skipping")
                _normal_path = "None"
        else:
            _normal_path = "None"
        blender_codes = [
            "clear()",
            f'obj = import_obj(r"{output_obj}")',
            "builder = Builder()",
            f"builder.add_material(obj, albedo_path={_albedo_path}, emission_path={_emission_path}, normal_path={_normal_path}, roughness={roughness}, metallic={metallic})",
            f'if not export_obj(r"{output_obj}", obj=obj): raise RuntimeError()',
        ]
        try:
            brender(*blender_codes, verbose=False)
        except RuntimeError as e:
            tsprint(f"[objathor_to_obj] Blender failed to export {output_obj}: {format_error(e)[0]}")
            return False

    return exists(output_obj)
