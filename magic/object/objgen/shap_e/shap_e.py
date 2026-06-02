# -*- coding: utf-8 -*-

import warnings

warnings.filterwarnings("ignore", message=".*PyTorch.*", module=r"shap_e\.models\.stf\.renderer")
warnings.filterwarnings("ignore", category=FutureWarning, module=r"shap_e\.models\.nn\.checkpoint")

from os import makedirs
from os.path import dirname, exists
from typing import Optional

import numpy as np
import torch
from shap_e.diffusion.gaussian_diffusion import diffusion_from_config
from shap_e.diffusion.sample import sample_latents
from shap_e.models.download import load_config, load_model
from shap_e.models.nn.camera import DifferentiableCameraBatch, DifferentiableProjectiveCamera
from shap_e.models.transmitter.base import Transmitter, VectorDecoder
from shap_e.rendering.mesh import TriMesh
from shap_e.rendering.torch_mesh import TorchMesh
from shap_e.util.collections import AttrDict
from torch import Tensor


class ShapE(object):
    def __init__(self, device: Optional[str] = None, cache_dir: Optional[str] = None) -> None:
        self.__device = "cpu" if device is None else device
        self.__xm: Transmitter | VectorDecoder = load_model("transmitter", device=device, cache_dir=cache_dir)
        self.__model = load_model("text300M", device=self.__device, cache_dir=cache_dir)
        self.__diffusion = diffusion_from_config(load_config("diffusion", cache_dir=cache_dir))

    @torch.inference_mode()
    def __call__(
        self,
        prompt: str,
        output_obj: str,
        *,
        steps: int = 64,
        guidance_scale: float = 15.0,
        sigma_min: float = 1e-3,
        sigma_max: float = 160.0,
        s_churn: float = 0.0,
    ) -> bool:
        try:
            latent = sample_latents(
                batch_size=1,
                model=self.__model,
                diffusion=self.__diffusion,
                guidance_scale=guidance_scale,
                model_kwargs=dict(texts=[prompt]),
                clip_denoised=True,
                use_fp16=True,
                use_karras=True,
                karras_steps=steps,
                sigma_min=sigma_min,
                sigma_max=sigma_max,
                s_churn=s_churn,
                progress=False,
            )[0]
            mesh = self.__decode_latent_mesh(latent).tri_mesh()
            self.__write_obj(mesh, output_obj)
        except KeyboardInterrupt:
            raise
        except BaseException as e:
            print(f"[{type(self).__name__}] Error generating object {output_obj}: {e}")
            return False
        return exists(output_obj)

    @torch.inference_mode()
    def __create_pan_cameras(self, size: int) -> DifferentiableCameraBatch:
        origins = []
        xs = []
        ys = []
        zs = []
        for theta in np.linspace(0, 2 * np.pi, num=20):
            z = np.array([np.sin(theta), np.cos(theta), -0.5])
            z /= np.sqrt(np.sum(z**2))
            origin = -z * 4
            x = np.array([np.cos(theta), -np.sin(theta), 0.0])
            y = np.cross(z, x)
            origins.append(origin)
            xs.append(x)
            ys.append(y)
            zs.append(z)
        return DifferentiableCameraBatch(
            shape=(1, len(xs)),
            flat_camera=DifferentiableProjectiveCamera(
                origin=torch.from_numpy(np.stack(origins, axis=0)).float().to(self.device),
                x=torch.from_numpy(np.stack(xs, axis=0)).float().to(self.device),
                y=torch.from_numpy(np.stack(ys, axis=0)).float().to(self.device),
                z=torch.from_numpy(np.stack(zs, axis=0)).float().to(self.device),
                width=size,
                height=size,
                x_fov=0.7,
                y_fov=0.7,
            ),
        )

    @torch.inference_mode()
    def __decode_latent_mesh(self, latent: Tensor) -> TorchMesh:
        xm = self.__xm
        decoded = xm.renderer.render_views(
            AttrDict(cameras=self.__create_pan_cameras(2)),
            params=(xm.encoder if isinstance(xm, Transmitter) else xm).bottleneck_to_params(latent[None]),
            options=AttrDict(rendering_mode="stf", render_with_direction=False),
        )
        return decoded.raw_meshes[0]

    def __write_obj(self, mesh: TriMesh, output_path: str) -> str:
        def rotate(coord: list[float]) -> list[float]:
            return [coord[0], coord[2], -coord[1]]

        if mesh.has_vertex_colors():
            vertex_colors = np.stack([mesh.vertex_channels[x] for x in "RGB"], axis=1)
            vertices = [
                "v {} {} {} {} {} {}".format(*rotate(coord), *color)
                for coord, color in zip(mesh.verts.tolist(), vertex_colors.tolist())
            ]
        else:
            vertices = ["v {} {} {}".format(*rotate(coord)) for coord in mesh.verts.tolist()]
        faces = ["f {} {} {}".format(tri[0] + 1, tri[1] + 1, tri[2] + 1) for tri in mesh.faces.tolist()]

        output_dir = dirname(output_path)
        if output_dir != "" and not exists(output_dir):
            makedirs(output_dir)
        with open(output_path, "w") as f:
            f.write("\n".join(vertices))
            f.write("\n")
            f.write("\n".join(faces))
            f.write("\n")
        return output_path

    @property
    def device(self) -> str:
        return self.__device
