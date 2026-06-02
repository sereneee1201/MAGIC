# -*- coding: utf-8 -*-

from copy import deepcopy
from os.path import dirname, join
from tempfile import NamedTemporaryFile
from typing import Callable
from uuid import uuid4

import cv2
import numpy as np

from magic.blender import brender
from magic.generation import Rotation3D
from magic.generation.modules import OUTPUT_GUIDANCE
from magic.tools.image_combiner import combine_images
from magic.utils.dtypes import PathLike
from magic.utils.llm import Llm, TemplateFormatter
from magic.utils.misc import format_error, tsprint
from magic.utils.retry import auto_retry

ROTATION_TEMPLATE = """<context>
A 3D object is generated based on the prompt <<inputs.prompt>>.
You are given a tiled image (2x2) showing renderings of the object under 4 different rotations:
[1] In the top-left rendering, the object is rotated 0 degree (does **NOT** necessarily mean it is front-facing).
[2] In the top-right rendering, the object is rotated 90 degrees.
[3] In the bottom-left rendering, the object is rotated 180 degrees.
[4] In the bottom-right rendering, the object is rotated 270 degrees.
</context>

<objective>
Based on your spatial common sense, determine the rotation required (in degrees) to put the object is in upright and front-facing orientation.
The number does **NOT** need to be one of {{0, 90, 180, 270}}.
If no rotation is required or you are not sure about what the correct answer is, return 0.
Also, provide a comprehensive and thorough reasoning on your decision.
</objective>

<style>
JSON
</style>

<tone>
Confident, professional, and clear.
</tone>

<audience>
A human who verifies the correctness of your output.
</audience>

<response>
{output_guidance}

<structure>
{{"reasoning": "<<FILL_IN>>", "rotation": <<FILL_IN>>}}
</structure>
</response>

<inputs>
<prompt>
{prompt}
</prompt>
</inputs>"""


get_rotation_prompt = TemplateFormatter(ROTATION_TEMPLATE, output_guidance=OUTPUT_GUIDANCE, prompt=None)


def correct_rotation_with_vlm(vlm: Llm) -> Callable[[str, PathLike], Rotation3D]:
    @auto_retry
    def correct_one_axis(obj_prompt: str, image: np.ndarray) -> float:
        _vlm = deepcopy(vlm)
        prompt = get_rotation_prompt(prompt=obj_prompt)
        response, _ = _vlm.chat(prompt, temperature=0.0, to_json=True, images=[image])
        if not isinstance(response, dict):
            raise RuntimeError()
        if "reasoning" not in response:
            raise RuntimeError()
        if not isinstance(response["reasoning"], str):
            raise RuntimeError()
        if "rotation" not in response:
            raise RuntimeError()
        if not isinstance(response["rotation"], (int, float)):
            raise RuntimeError()
        return float(response["rotation"])

    def correct(obj_prompt: str, obj_path: PathLike) -> Rotation3D:
        rot_map = {"x": 0.0, "y": 0.0, "z": 0.0}
        rot_order = {
            "x": (90, 0, 0),
            "y": (0, 90, 0),
            "z": (0, 0, 90),
        }
        camera = (75, 0, 165)  # from top-right; (90, 0, 180) from middle
        uid = uuid4().hex[:8]
        for axis, rot in rot_order.items():
            with (
                NamedTemporaryFile(suffix=".png") as tf1,
                NamedTemporaryFile(suffix=".png") as tf2,
                NamedTemporaryFile(suffix=".png") as tf3,
                NamedTemporaryFile(suffix=".png") as tf4,
            ):
                # ----- Generate renders from different angles -----
                render_codes = [
                    "clear()",
                    f'obj = import_obj(r"{obj_path}")',
                    "transform(obj, rotation=({}, {}, {}))".format(*rot_map.values()),
                    "renderer = Renderer()",
                    "center, radius = renderer.compute_bounding_sphere()",
                    f'if not renderer.render_perspective(r"{tf1.name}", center, radius=radius, rotation={camera}, resolution=512): raise RuntimeError()',
                    f"transform(obj, rotation={rot})",
                    f'if not renderer.render_perspective(r"{tf2.name}", center, radius=radius, rotation={camera}, resolution=512): raise RuntimeError()',
                    f"transform(obj, rotation={rot})",
                    f'if not renderer.render_perspective(r"{tf3.name}", center, radius=radius, rotation={camera}, resolution=512): raise RuntimeError()',
                    f"transform(obj, rotation={rot})",
                    f'if not renderer.render_perspective(r"{tf4.name}", center, radius=radius, rotation={camera}, resolution=512): raise RuntimeError()',
                ]
                try:
                    brender(*render_codes, verbose=False)
                except RuntimeError as e:
                    tsprint(f"Error rendering {obj_path} for {axis}-axis: {format_error(e)[0]}")
                    continue
                # ==================================================
                # ----- Combine renders into a single image -----
                try:
                    combined = combine_images(
                        tf1.name,
                        tf2.name,
                        tf3.name,
                        tf4.name,
                        n_rows=2,
                        n_cols=2,
                        output_width=1024,
                        output_height=1024,
                    )
                    cv2.imwrite(join(dirname(obj_path), f"render_{uid}_combined-{axis}.png"), combined)
                except KeyboardInterrupt:
                    raise
                except BaseException as e:
                    tsprint(f"Error combining renders of {obj_path} for {axis}-axis: {format_error(e)[0]}")
                    continue
                # ===============================================
                # ----- Detect rotation from the combined image -----
                try:
                    rot_map[axis] = correct_one_axis(obj_prompt, combined)
                except KeyboardInterrupt:
                    raise
                except BaseException as e:
                    tsprint(f"Error detecting {axis} rotation for {obj_path}: {format_error(e)[0]}")
                    continue
                # ===================================================
        return Rotation3D(x=rot_map["x"], y=rot_map["y"], z=rot_map["z"])

    return correct
