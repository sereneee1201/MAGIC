# -*- coding: utf-8 -*-

import json
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from typing import Any

from magic.generation import MagicConfig, MagicLog, MagicScene, Vector3D
from magic.generation.modules import OUTPUT_GUIDANCE
from magic.generation.modules.object_placement.lights.templates import REGION_LIGHTS_TEMPLATE
from magic.utils.dtypes import JsonObject, SDict
from magic.utils.llm import Llm, LlmContent, TemplateFormatter
from magic.utils.retry import auto_retry

get_region_lights_prompt = TemplateFormatter(
    REGION_LIGHTS_TEMPLATE,
    scene_type=None,
    region_type=None,
    region_name=None,
    output_guidance=OUTPUT_GUIDANCE,
    region=None,
)


def get_regions_lights(scene: MagicScene, config: MagicConfig, llm: Llm, log: MagicLog) -> SDict[LlmContent]:
    @auto_retry
    def get_region_lights(region_name: str, region: SDict[Any]) -> tuple[JsonObject, LlmContent]:
        _llm = deepcopy(llm)
        _llm.clear_messages()
        prompt = get_region_lights_prompt(
            scene_type=scene.scene_type,
            region_type=scene.region_type,
            region_name=region_name,
            region=json.dumps(region, ensure_ascii=False),
        )
        response, llm_output = _llm.chat(prompt, temperature=config.temperature, to_json=True)
        if not isinstance(response, dict):
            raise RuntimeError()
        if "reasoning" not in response:
            raise RuntimeError()
        if not isinstance(response["reasoning"], str):
            raise RuntimeError()
        if "lights" not in response:
            raise RuntimeError()
        if not isinstance(response["lights"], list):
            raise RuntimeError()
        for light in response["lights"]:
            if not isinstance(light, list):
                raise RuntimeError()
            if len(light) != 3:
                raise RuntimeError()
            if not all(isinstance(p, (int, float)) for p in light):
                raise RuntimeError()
        return response, llm_output.content

    contents = {}
    region_names = [region.name for region in scene.regions.values()]
    region_keys = list(scene.regions.keys())
    regions = [
        {
            "shape": {
                "min_vertex": dict(zip(["x", "z"], scene.regions[key].shape.min_vertex.model_dump().values())),
                "max_vertex": dict(zip(["x", "z"], scene.regions[key].shape.max_vertex.model_dump().values())),
                "width": scene.regions[key].shape.width,
                **({"height": scene.regions[key].shape.height} if scene.is_indoor else {}),
                "depth": scene.regions[key].shape.depth,
            },
            "objects": {
                obj_name: {
                    "dimensions": obj.dimensions.model_dump(),
                    "position": obj.position[-1].model_dump(),
                    "rotation": obj.rotation[-1].model_dump(),
                }
                for obj_name, obj in scene.regions[key].objects.items()
            },
        }
        for key in region_keys
    ]
    with ThreadPoolExecutor(max_workers=config.max_threads) as executor:
        for i, (response, content) in enumerate(executor.map(get_region_lights, region_names, regions)):
            scene.regions[region_keys[i]].lights.clear()
            for light in response["lights"]:
                scene.regions[region_keys[i]].lights.append(Vector3D(x=light[0], y=light[1], z=light[2]))
            contents[region_keys[i]] = content
    log.save()
    return contents
