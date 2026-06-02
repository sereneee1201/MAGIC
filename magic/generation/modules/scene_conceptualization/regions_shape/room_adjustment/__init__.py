# -*- coding: utf-8 -*-

import json

from magic.generation import MagicConfig, MagicLog, MagicScene, Vector2D
from magic.generation.modules import CONNECTION_THICKNESS, OUTPUT_GUIDANCE
from magic.generation.modules.scene_conceptualization.regions_shape.room_adjustment.templates import (
    ROOMS_ADJUSTMENT_TEMPLATE,
)
from magic.utils.llm import Llm, LlmContent, TemplateFormatter
from magic.utils.retry import auto_retry

get_rooms_adjustment_prompt = TemplateFormatter(
    ROOMS_ADJUSTMENT_TEMPLATE,
    wall_thickness=round(CONNECTION_THICKNESS / 2, 6),
    connection_thickness=CONNECTION_THICKNESS,
    output_guidance=OUTPUT_GUIDANCE,
    rooms=None,
)


@auto_retry
def adjust_rooms(scene: MagicScene, config: MagicConfig, llm: Llm, log: MagicLog) -> LlmContent:
    llm.clear_messages()
    rooms = {
        name: {"min_vertex": detail.shape.min_vertex.model_dump(), "max_vertex": detail.shape.max_vertex.model_dump()}
        for name, detail in scene.regions.items()
    }
    prompt = get_rooms_adjustment_prompt(rooms=json.dumps(rooms, ensure_ascii=False))
    response, llm_output = llm.chat(prompt, temperature=config.temperature, to_json=True)
    if not isinstance(response, dict):
        raise RuntimeError()
    for region_name in scene.regions:
        if region_name not in response:
            raise RuntimeError()
        if not isinstance(response[region_name], dict):
            raise RuntimeError()
        if "reasoning" not in response[region_name]:
            raise RuntimeError()
        if not isinstance(response[region_name]["reasoning"], str):
            raise RuntimeError()
        if "shifts" not in response[region_name]:
            raise RuntimeError()
        if not isinstance(response[region_name]["shifts"], list):
            raise RuntimeError()
        if len(response[region_name]["shifts"]) != 2:
            raise RuntimeError()
        if not all(isinstance(s, (int, float)) for s in response[region_name]["shifts"]):
            raise RuntimeError()
        scene.regions[region_name].shape.shifts = Vector2D(
            x=response[region_name]["shifts"][0], y=response[region_name]["shifts"][1]
        )
    log.save()
    llm.clear_messages()
    return llm_output.content
