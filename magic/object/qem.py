# -*- coding: utf-8 -*-

import tempfile
from typing import Optional

import numpy as np
import open3d as o3d
import trimesh
from open3d.geometry import TriangleMesh  # type: ignore
from pydantic import BaseModel
from scipy.spatial import cKDTree
from scipy.spatial.distance import directed_hausdorff
from trimesh import Trimesh


class QemResult(BaseModel, validate_assignment=True, strict=True):
    final_faces: int
    face_pct_change: float
    rms_error: float
    hausdorff_dist: float


def _compute_rms_and_hausdorff(
    ori_points: np.ndarray, sim_points: np.ndarray, eps: float = 1e-10
) -> tuple[float, float]:
    min_bounds = ori_points.min(axis=0)
    max_bounds = ori_points.max(axis=0)
    center = (min_bounds + max_bounds) / 2
    scale = (max_bounds - min_bounds).max() / 2
    ori_points_norm = (ori_points - center) / (scale + eps)
    sim_points_norm = (sim_points - center) / (scale + eps)

    # compute RMS error on normalized points
    tree = cKDTree(ori_points_norm)
    distances, _ = tree.query(sim_points_norm, k=1)
    rms_error = np.sqrt(np.mean(np.square(distances))).item()

    # compute Hausdorff distance on normalized points
    d1 = directed_hausdorff(ori_points_norm, sim_points_norm)[0]
    d2 = directed_hausdorff(sim_points_norm, ori_points_norm)[0]
    hausdorff_dist = max(d1, d2)

    return rms_error, hausdorff_dist


def _normalize_points(points: np.ndarray, eps: float = 1e-10) -> tuple[np.ndarray, np.ndarray, float]:
    min_bounds = points.min(axis=0)
    max_bounds = points.max(axis=0)
    center = (min_bounds + max_bounds) / 2
    scale = (max_bounds - min_bounds).max() / 2
    points_norm = (points - center) / (scale + eps)
    return points_norm, center, scale + eps


def _denormalize_points(points_norm: np.ndarray, center: np.ndarray, scale: float) -> np.ndarray:
    return points_norm * scale + center


def _qem_once(tmesh: Trimesh, n_faces: int, ori_vertices: np.ndarray) -> tuple[TriangleMesh, QemResult]:
    with tempfile.NamedTemporaryFile(suffix=".obj") as tf:
        tmesh.export(tf.name)
        omesh: TriangleMesh = o3d.io.read_triangle_mesh(tf.name)
    sim_omesh = omesh.simplify_quadric_decimation(n_faces)
    rms_error, hausdorff_dist = _compute_rms_and_hausdorff(ori_vertices, np.asarray(sim_omesh.vertices))
    final_faces = len(sim_omesh.triangles)
    face_pct_change = (final_faces - len(tmesh.faces)) / len(tmesh.faces)
    return sim_omesh, QemResult(
        final_faces=final_faces,
        face_pct_change=face_pct_change,
        rms_error=rms_error,
        hausdorff_dist=hausdorff_dist,
    )


def qem(
    input_obj: str,
    output_obj: str,
    max_faces: Optional[int] = None,
    rms_thresh: Optional[float] = None,
    max_iters: Optional[int] = None,
    eps: float = 1e-5,
) -> QemResult:
    if max_faces is None and rms_thresh is None:
        raise ValueError("`max_faces` and `rms_thresh` cannot be None at the same time")
    ori_tmesh: Trimesh = trimesh.load(input_obj, process=False)
    ori_vertices_norm, center, scale = _normalize_points(np.asarray(ori_tmesh.vertices))
    ori_tmesh_norm = Trimesh(
        vertices=ori_vertices_norm,
        faces=ori_tmesh.faces,
        face_normals=ori_tmesh.face_normals,
        vertex_normals=ori_tmesh.vertex_normals,
        visual=ori_tmesh.visual,
        process=False,
    )
    best_sim_omesh_norm, best_result = None, None
    if max_faces is not None:
        max_faces = max(max_faces, 4)
        best_sim_omesh_norm, best_result = _qem_once(ori_tmesh_norm, max_faces, ori_vertices_norm)
    if rms_thresh is not None and (best_result is None or abs(best_result.rms_error - rms_thresh) > eps):
        max_iters = 5 if max_iters is None else max(max_iters, 1)
        low = 4
        high = len(ori_tmesh.faces) if best_result is None else best_result.final_faces
        n_iters = 0
        best_error_diff = None
        while low <= high and n_iters < max_iters:
            mid = (low + high) // 2
            sim_omesh_norm, result = _qem_once(ori_tmesh_norm, mid, ori_vertices_norm)
            error_diff = result.rms_error - rms_thresh
            if abs(error_diff) <= eps:
                best_sim_omesh_norm, best_result = sim_omesh_norm, result
                break
            else:
                if (
                    best_error_diff is None
                    or (best_error_diff > 0 and error_diff < best_error_diff)
                    or (best_error_diff < 0 and error_diff < 0 and error_diff > best_error_diff)
                ):
                    if result.final_faces >= 4:
                        best_sim_omesh_norm, best_result = sim_omesh_norm, result
                        best_error_diff = error_diff
                if result.rms_error < rms_thresh:
                    high = mid - 1
                else:
                    low = mid + 1
            n_iters += 1
    if best_result is None:
        best_sim_omesh_norm, best_result = _qem_once(ori_tmesh_norm, len(ori_tmesh.faces), ori_vertices_norm)
    sim_vertices = _denormalize_points(np.asarray(best_sim_omesh_norm.vertices), center, scale)
    best_sim_omesh_norm.vertices = o3d.utility.Vector3dVector(sim_vertices)
    o3d.io.write_triangle_mesh(output_obj, best_sim_omesh_norm)
    return best_result


def _cli():
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("input", help="Input .obj file")
    parser.add_argument("output", help="Output .obj file")
    parser.add_argument("-f", "--max_faces", type=int, default=None, help="Target number of faces")
    parser.add_argument("-r", "--rms_thresh", type=float, default=None, help="Target RMS error")
    parser.add_argument("-m", "--max_iters", type=int, default=5, help="Max binary search iterations")
    args = parser.parse_args()
    result = qem(args.input, args.output, args.max_faces, args.rms_thresh, args.max_iters)
    print(result)


if __name__ == "__main__":
    _cli()
