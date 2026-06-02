# -*- coding: utf-8 -*-

from tempfile import NamedTemporaryFile
from typing import Any, Optional
from uuid import uuid4

from magic.blender import brender
from magic.object.objgen.base import ObjectGenerator
from magic.object.objgen.shap_e.shap_e import ShapE
from .object.qem import qem
from magic.utils.dtypes import PathLike
from magic.utils.file import exists
from magic.utils.misc import format_error, tsprint


class ShapEGenerator(ObjectGenerator):
    def __init__(self, device: Optional[str] = None, cache_dir: Optional[str] = None, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.__model = ShapE(device=device, cache_dir=cache_dir)

    def _acquire(self, prompt: str, output_obj: PathLike, **kwargs: Any) -> bool:
        qem_n_faces = kwargs.pop("qem_n_faces", None)
        qem_rms_thresh = kwargs.pop("qem_rms_thresh", None)
        qem_max_iters = kwargs.pop("qem_max_iters", None)
        roughness = kwargs.pop("roughness", None)
        metallic = kwargs.pop("metallic", None)
        if not self.__model(prompt, output_obj, **kwargs):
            tsprint(f"[{type(self).__name__}] Error generating object {output_obj}")
            return False
        # ----- QEM -----
        if qem_n_faces is not None or qem_rms_thresh is not None:
            try:
                qem(
                    output_obj,
                    output_obj,
                    max_faces=qem_n_faces,
                    rms_thresh=qem_rms_thresh,
                    max_iters=qem_max_iters,
                )
            except KeyboardInterrupt:
                raise
            except BaseException as e:
                tsprint(f"[{type(self).__name__}] QEM failed for object {output_obj}: {format_error(e)[0]}")
        # ===============
        self.__bake_texture(output_obj, roughness=roughness, metallic=metallic)
        return exists(output_obj)

    def __bake_texture(
        self, obj_path: PathLike, roughness: Optional[float] = None, metallic: Optional[float] = None
    ) -> bool:
        with NamedTemporaryFile(prefix=f"tmp_{uuid4().hex[:8]}_albedo_", suffix=".png") as tf:
            bake_codes = [
                "clear()",
                f'obj = import_obj(r"{obj_path}", load_vertex_colors=True)',
                "builder = Builder()",
                f'if not builder.bake_vertex_colors_to_albedo(obj, r"{tf.name}"): raise RuntimeError()',
                f'builder.add_material(obj, albedo_path=r"{tf.name}", roughness={roughness}, metallic={metallic})',
                f'if not export_obj(r"{obj_path}", obj=obj): raise RuntimeError()',
            ]
            try:
                brender(*bake_codes, verbose=False)
            except RuntimeError as e:
                tsprint(f"[{type(self).__name__}] Error baking texture for object {obj_path}: {format_error(e)[0]}")
                return False
