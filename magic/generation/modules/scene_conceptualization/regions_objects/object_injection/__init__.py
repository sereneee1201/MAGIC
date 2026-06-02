# -*- coding: utf-8 -*-

from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy

from magic.generation import MagicConfig, MagicLog, MagicScene
from magic.generation.modules import OUTPUT_GUIDANCE
from magic.generation.modules.scene_conceptualization.regions_objects.object_injection.templates import (
    REGION_OBJECT_INJECTION_PROMPT,
)
from magic.utils.dtypes import JsonObject, SDict
from magic.utils.llm import Llm, LlmContent, TemplateFormatter
from magic.utils.retry import auto_retry

get_region_object_injection_prompt = TemplateFormatter(
    REGION_OBJECT_INJECTION_PROMPT,
    scene_type=None,
    region_type=None,
    region_name=None,
    output_guidance=OUTPUT_GUIDANCE,
    prompt=None,
)


def inject_regions_object(scene: MagicScene, config: MagicConfig, llm: Llm, log: MagicLog) -> SDict[LlmContent]:
    @auto_retry
    def inject_region_object(region_name: str, subprompt: str) -> tuple[JsonObject, LlmContent]:
        _llm = deepcopy(llm)
        _llm.clear_messages()
        prompt = get_region_object_injection_prompt(
            scene_type=scene.scene_type, region_type=scene.region_type, region_name=region_name, prompt=subprompt
        )
        response, llm_output = _llm.chat(prompt, temperature=config.temperature, to_json=True)
        if not isinstance(response, dict):
            raise RuntimeError()
        if "expansion" not in response:
            raise RuntimeError()
        if not isinstance(response["expansion"], str):
            raise RuntimeError()
        return response, llm_output.content

    contents = {}
    region_names = [region.name for region in scene.regions.values()]
    subprompts = [region.subprompt for region in scene.regions.values()]
    region_keys = list(scene.regions.keys())
    with ThreadPoolExecutor(max_workers=config.max_threads) as executor:
        for i, (response, content) in enumerate(executor.map(inject_region_object, region_names, subprompts)):
            scene.regions[region_keys[i]].object_injected_subprompt = response["expansion"]
            contents[region_keys[i]] = content
    log.save()
    return content
