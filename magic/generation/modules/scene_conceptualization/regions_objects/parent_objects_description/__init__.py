# -*- coding: utf-8 -*-

import json
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy

from magic.generation import MagicConfig, MagicLog, MagicScene, ObjectDescription
from magic.generation.modules import OUTPUT_GUIDANCE
from magic.generation.modules.scene_conceptualization.regions_objects.parent_objects_description.templates import (
    REGION_PARENT_OBJECTS_DESCRIPTION_TEMPLATE,
)
from magic.utils.dtypes import JsonObject, SDict
from magic.utils.llm import Llm, LlmContent, TemplateFormatter
from magic.utils.maths import clamp
from magic.utils.retry import auto_retry

get_region_parent_objects_description_prompt = TemplateFormatter(
    REGION_PARENT_OBJECTS_DESCRIPTION_TEMPLATE,
    scene_type=None,
    region_type=None,
    region_name=None,
    output_guidance=OUTPUT_GUIDANCE,
    prompt=None,
    objects=None,
)


def get_regions_parent_objects_description(
    scene: MagicScene, config: MagicConfig, llm: Llm, log: MagicLog
) -> SDict[LlmContent]:
    @auto_retry
    def get_region_parent_objects_description(
        region_name: str, subprompt: str, objects: list[str]
    ) -> tuple[JsonObject, LlmContent]:
        _llm = deepcopy(llm)
        _llm.clear_messages()
        prompt = get_region_parent_objects_description_prompt(
            scene_type=scene.scene_type,
            region_type=scene.region_type,
            region_name=region_name,
            prompt=subprompt,
            objects=json.dumps(objects, ensure_ascii=False),
        )
        response, llm_output = _llm.chat(prompt, temperature=config.temperature, to_json=True)
        if not isinstance(response, dict):
            raise RuntimeError()
        for obj_name in objects:
            if obj_name not in response:
                raise RuntimeError()
            if "color" not in response[obj_name]:
                raise RuntimeError()
            if not isinstance(response[obj_name]["color"], str):
                raise RuntimeError()
            if response[obj_name]["color"].strip() == "":
                raise RuntimeError()
            if "material" not in response[obj_name]:
                raise RuntimeError()
            if not isinstance(response[obj_name]["material"], str):
                raise RuntimeError()
            if response[obj_name]["material"].strip() == "":
                raise RuntimeError()
            if "attributes" not in response[obj_name]:
                raise RuntimeError()
            if not isinstance(response[obj_name]["attributes"], str):
                raise RuntimeError()
        return response, llm_output.content

    contents = {}
    region_names = [region.name for region in scene.regions.values()]
    subprompts = [region.object_injected_subprompt for region in scene.regions.values()]
    region_keys = list(scene.regions.keys())
    objects = [list(scene.regions[key].objects.keys()) for key in region_keys]
    with ThreadPoolExecutor(max_workers=config.max_threads) as executor:
        for i, (response, content) in enumerate(
            executor.map(get_region_parent_objects_description, region_names, subprompts, objects)
        ):
            for obj_name in objects[i]:
                scene.regions[region_keys[i]].objects[obj_name].description = ObjectDescription(
                    color=response[obj_name]["color"].strip(),
                    material=response[obj_name]["material"].strip().replace("made with ", ""),
                    attributes=response[obj_name]["attributes"].strip().replace("that is ", ""),
                )
            contents[region_keys[i]] = content
    log.save()
    return contents
