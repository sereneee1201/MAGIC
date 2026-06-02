# -*- coding: utf-8 -*-

from collections import defaultdict

from magic.generation import MagicConfig, MagicLog, MagicScene, Region
from magic.generation.modules import OUTPUT_GUIDANCE
from magic.generation.modules.prompt_processing.regions_extraction.templates import REGIONS_EXTRACTION_PROMPT
from magic.utils.llm import Llm, LlmContent, TemplateFormatter
from magic.utils.misc import remove_trailing_digits, replace_non_alphanumeric
from magic.utils.retry import auto_retry

get_regions_extraction_prompt = TemplateFormatter(
    REGIONS_EXTRACTION_PROMPT, scene_type=None, region_type=None, output_guidance=OUTPUT_GUIDANCE, prompt=None
)


@auto_retry
def extract_regions(scene: MagicScene, config: MagicConfig, llm: Llm, log: MagicLog) -> LlmContent:
    llm.clear_messages()
    prompt = get_regions_extraction_prompt(
        scene_type=scene.scene_type, region_type=scene.region_type, prompt=scene.prompt
    )
    response, llm_output = llm.chat(prompt, temperature=config.temperature, to_json=True)
    # ----- Validation -----
    if not isinstance(response, dict):
        raise RuntimeError()
    if "regions" not in response:
        raise RuntimeError()
    if not isinstance(response["regions"], list):
        raise RuntimeError()
    for region_name in response["regions"]:
        if not isinstance(region_name, str):
            raise RuntimeError()
    # ======================
    region_counter: defaultdict[str, int] = defaultdict(int)
    for region_name in response["regions"]:
        region_name = replace_non_alphanumeric(remove_trailing_digits(region_name).lower())
        if region_name == "":
            continue
        region_counter[region_name] += 1
    for region_name, count in region_counter.items():
        if count > 1:
            for i in range(1, count + 1):
                scene.regions[f"{region_name}_{i}"] = Region(name=region_name.replace("_", " "))
        else:
            scene.regions[region_name] = Region(name=region_name.replace("_", " "))
    log.save()
    llm.clear_messages()
    return llm_output.content
