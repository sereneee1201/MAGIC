# -*- coding: utf-8 -*-

from magic.generation import MagicConfig, MagicLog, MagicScene
from magic.generation.modules import OUTPUT_GUIDANCE
from magic.generation.modules.prompt_processing.design_injection.templates import DESIGN_INJECTION_PROMPT
from magic.utils.llm import Llm, LlmContent, TemplateFormatter
from magic.utils.retry import auto_retry

get_design_injection_prompt = TemplateFormatter(
    DESIGN_INJECTION_PROMPT, scene_type=None, region_type=None, output_guidance=OUTPUT_GUIDANCE, prompt=None
)


@auto_retry
def inject_design_to_main_prompt(scene: MagicScene, config: MagicConfig, llm: Llm, log: MagicLog) -> LlmContent:
    llm.clear_messages()
    prompt = get_design_injection_prompt(
        scene_type=scene.scene_type, region_type=scene.region_type, prompt=scene.prompt
    )
    response, llm_output = llm.chat(prompt, temperature=config.temperature, to_json=True)
    if not isinstance(response, dict):
        raise RuntimeError()
    if "expansion" not in response:
        raise RuntimeError()
    scene.design_injected_prompt = response["expansion"]
    log.save()
    llm.clear_messages()
    return llm_output.content
