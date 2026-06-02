# -*- coding: utf-8 -*-

import json

from magic.generation import MagicConfig, MagicLog, MagicScene, Rotation3D, Vector2D, Vector3D
from magic.generation.modules import CONNECTION_THICKNESS, OUTPUT_GUIDANCE
from magic.generation.modules.scene_conceptualization.indoor_connections.placement.templates import (
    INDOOR_CONNECTIONS_PLACEMENT_TEMPLATE,
)
from magic.utils.llm import Llm, LlmContent, TemplateFormatter
from magic.utils.retry import auto_retry

get_indoor_doors_placement_prompt = TemplateFormatter(
    INDOOR_CONNECTIONS_PLACEMENT_TEMPLATE,
    output_guidance=OUTPUT_GUIDANCE,
    prompt=None,
    regions=None,
    doors=None,
    windows=None,
)


@auto_retry
def place_indoor_connections(scene: MagicScene, config: MagicConfig, llm: Llm, log: MagicLog) -> LlmContent:
    llm.clear_messages()
    regions = {
        name: {
            "min_vertex": detail.shape.min_vertex.model_dump(),
            "max_vertex": detail.shape.max_vertex.model_dump(),
            "height": detail.shape.height,
        }
        for name, detail in scene.regions.items()
    }
    doors = {
        name: {
            "region_a": detail.region_a,
            "region_b": detail.region_b,
            "category": detail.obj.category,
            "width": detail.obj.dimensions.width,
            "height": detail.obj.dimensions.height,
        }
        for name, detail in scene.connections.items()
        if name.startswith("door")
    }
    windows = {
        name: {
            "region_a": detail.region_a,
            "region_b": detail.region_b,
            "category": detail.obj.category,
            "width": detail.obj.dimensions.width,
            "height": detail.obj.dimensions.height,
        }
        for name, detail in scene.connections.items()
        if name.startswith("window")
    }
    prompt = get_indoor_doors_placement_prompt(
        prompt=scene.design_injected_prompt,
        regions=json.dumps(regions, ensure_ascii=False),
        doors=json.dumps(doors, ensure_ascii=False),
        windows=json.dumps(windows, ensure_ascii=False),
    )
    response, llm_output = llm.chat(prompt, temperature=config.temperature, to_json=True)
    # ----- Validation -----
    if not isinstance(response, dict):
        raise RuntimeError()
    for key in ("doors", "windows"):
        if key not in response:
            raise RuntimeError()
        if not isinstance(response[key], dict):
            raise RuntimeError()
    for conn_name, conn in scene.connections.items():
        prefix = conn_name.split("_")[0]
        if conn_name not in response[f"{prefix}s"]:
            raise RuntimeError()
        if not isinstance(response[f"{prefix}s"][conn_name], dict):
            raise RuntimeError()
        if "center" not in response[f"{prefix}s"][conn_name]:
            raise RuntimeError()
        if not isinstance(response[f"{prefix}s"][conn_name]["center"], list):
            raise RuntimeError()
        if len(response[f"{prefix}s"][conn_name]["center"]) != 2:
            raise RuntimeError()
        if not all(isinstance(c, (int, float)) for c in response[f"{prefix}s"][conn_name]["center"]):
            raise RuntimeError()
        if prefix == "window":
            if "height_above_floor" not in response[f"{prefix}s"][conn_name]:
                raise RuntimeError()
            if not isinstance(response[f"{prefix}s"][conn_name]["height_above_floor"], (int, float)):
                raise RuntimeError()
    # ====== Positioning and Orientation Fix ======
    for conn_name, conn in scene.connections.items():
        prefix = conn_name.split("_")[0]
        center = response[f"{prefix}s"][conn_name]["center"]
        cx, cy = center

        region = scene.regions[conn.region_a]
        min_x, max_x = region.shape.min_vertex.x, region.shape.max_vertex.x
        min_y, max_y = region.shape.min_vertex.y, region.shape.max_vertex.y

        # determine closest wall
        distances = {
            "left": abs(cx - min_x),
            "right": abs(cx - max_x),
            "front": abs(cy - min_y),
            "back": abs(cy - max_y),
        }
        wall = min(distances, key=distances.get)
        distance = min(distances.values())

        # assign orientation and shift
        if wall in ["left", "right"]:
            orientation = "vertical"
            sign = -1 if wall == "left" else 1
            # snap to wall plane, then shift inwards by half thickness
            snapped_cx = min_x if wall == "left" else max_x
            door_shift_x = (snapped_cx - cx) - sign * (CONNECTION_THICKNESS / 2)
            door_shift_y = 0.0
        else:
            orientation = "horizontal"
            sign = -1 if wall == "front" else 1
            snapped_cy = min_y if wall == "front" else max_y
            door_shift_x = 0.0
            door_shift_y = (snapped_cy - cy) - sign * (CONNECTION_THICKNESS / 2)
            
        # compute y-position
        pos_y = scene.connections[conn_name].obj.dimensions.height / 2
        if prefix == "window":
            pos_y += response[f"{prefix}s"][conn_name]["height_above_floor"]

        # apply final position
        scene.connections[conn_name].obj.position.append(
            Vector3D(x=cx + door_shift_x, y=pos_y, z=cy + door_shift_y)
        )
        scene.connections[conn_name].obj.rotation.append(
            Rotation3D(x=0.0, y=90.0 if orientation == "vertical" else 0.0, z=0.0)
        )
        scene.connections[conn_name].shifts = Vector2D(
            x=region.shape.shifts.x + door_shift_x,
            y=region.shape.shifts.y + door_shift_y
        )

    log.save()
    llm.clear_messages()
    return llm_output.content