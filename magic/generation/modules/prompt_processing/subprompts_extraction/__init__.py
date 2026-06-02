# -*- coding: utf-8 -*-

import json

from magic.generation import MagicConfig, MagicLog, MagicScene
from magic.generation.modules import OUTPUT_GUIDANCE
from magic.generation.modules.prompt_processing.subprompts_extraction.templates import SUBPROMPTS_EXTRACTION_PROMPT
from magic.utils.llm import Llm, LlmContent, TemplateFormatter
from magic.utils.retry import auto_retry

get_subprompts_extraction_prompt = TemplateFormatter(
    SUBPROMPTS_EXTRACTION_PROMPT,
    scene_type=None,
    region_type=None,
    output_guidance=OUTPUT_GUIDANCE,
    structure=None,
    prompt=None,
)


def _get_regions_extraction_structure(scene: MagicScene) -> str:
    regions = {region_name: "<<FILL_IN>>" for region_name in scene.regions}
    return f"""\
{{"regions": {json.dumps(regions, ensure_ascii=False)}}}"""


@auto_retry
def extract_subprompts(scene: MagicScene, config: MagicConfig, llm: Llm, log: MagicLog) -> LlmContent:
    llm.clear_messages()
    prompt = get_subprompts_extraction_prompt(
        scene_type=scene.scene_type,
        region_type=scene.region_type,
        structure=_get_regions_extraction_structure(scene),
        prompt=scene.design_injected_prompt,
    )
    response, llm_output = llm.chat(prompt, temperature=config.temperature, to_json=True)
    # ----- Validation -----
    if not isinstance(response, dict):
        raise RuntimeError()
    if "regions" not in response:
        raise RuntimeError()
    if not isinstance(response["regions"], dict):
        raise RuntimeError()
    for region_name in scene.regions:
        if region_name not in response["regions"]:
            raise RuntimeError()
        if not isinstance(response["regions"][region_name], str):
            raise RuntimeError()
        if response["regions"][region_name].strip() == "":
            raise RuntimeError()
    # ======================
    for region_name in scene.regions:
        scene.regions[region_name].subprompt = response["regions"][region_name].strip()
    log.save()
    llm.clear_messages()
    return llm_output.content
