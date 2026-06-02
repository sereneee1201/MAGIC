# -*- coding: utf-8 -*-

"""
Reference: [Blender](https://docs.blender.org/manual/en/latest/render/shader_nodes/shader/principled.html)
"""

from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy

from magic.generation import MagicConfig, MagicLog, MagicScene, ObjectDescription
from magic.generation.modules import OUTPUT_GUIDANCE
from magic.generation.modules.scene_conceptualization.regions_design.templates import REGION_DESIGN_TEMPLATE
from magic.utils.dtypes import JsonObject
from magic.utils.llm import Llm, LlmContent, TemplateFormatter
from magic.utils.maths import clamp
from magic.utils.retry import auto_retry

get_region_design_prompt = TemplateFormatter(
    REGION_DESIGN_TEMPLATE,
    scene_type=None,
    region_type=None,
    region_name=None,
    objective=None,
    output_guidance=OUTPUT_GUIDANCE,
    structure=None,
    prompt=None,
)

def _get_region_design_objective(scene: MagicScene) -> str:
    objective = """\
Based on the provided user prompt, determine the non-empty description (color, material, attributes; "attributes" refers to comma-separated descriptive phrases that are solely about the region's appearance and are independent of other regions) of the region's floor"""
    if scene.is_indoor:
        objective += " and wall."
    else:
        objective += "."
    objective += f"""
A description **MUST** be able to resemble the following sentence: "`color` floor"""
    if scene.is_indoor:
        objective += "/wall"
    objective += ' made of `material` that is `attributes`."'
    return objective


def _get_region_design_structure(scene: MagicScene) -> str:
    structure = f"""\
{{
  "floor": {{"color": "<<FILL_IN>>", "material": "<<FILL_IN>>", "attributes": "<<FILL_IN>>"}}"""
    if scene.is_indoor:
        structure += f""",
  "wall": {{"color": "<<FILL_IN>>", "material": "<<FILL_IN>>", "attributes": "<<FILL_IN>>"}}"""
    structure += f"""
}}"""
    return structure


def design_regions(scene: MagicScene, config: MagicConfig, llm: Llm, log: MagicLog) -> LlmContent:
    @auto_retry
    def design_region(region_name: str, subprompt: str) -> tuple[JsonObject, LlmContent]:
        _llm = deepcopy(llm)
        _llm.clear_messages()
        prompt = get_region_design_prompt(
            scene_type=scene.scene_type,
            region_type=scene.region_type,
            region_name=region_name,
            objective=_get_region_design_objective(scene),
            structure=_get_region_design_structure(scene),
            prompt=subprompt,
        )
        response, llm_output = _llm.chat(prompt, temperature=config.temperature, to_json=True)
        if not isinstance(response, dict):
            raise RuntimeError()
        boundaries = ("floor", "wall") if scene.is_indoor else ("floor",)
        for b in boundaries:
            if b not in response:
                raise RuntimeError()
            if not isinstance(response[b], dict):
                raise RuntimeError()
            if "color" not in response[b]:
                raise RuntimeError()
            if not isinstance(response[b]["color"], str):
                raise RuntimeError()
            if response[b]["color"].strip() == "":
                raise RuntimeError()
            if "material" not in response[b]:
                raise RuntimeError()
            if not isinstance(response[b]["material"], str):
                raise RuntimeError()
            if response[b]["material"].strip() == "":
                raise RuntimeError()
            if "attributes" not in response[b]:
                raise RuntimeError()
            if not isinstance(response[b]["attributes"], str):
                raise RuntimeError()
        return response, llm_output.content

    contents = {}
    region_names = [region.name for region in scene.regions.values()]
    subprompts = [region.subprompt for region in scene.regions.values()]
    region_keys = list(scene.regions.keys())
    with ThreadPoolExecutor(max_workers=config.max_threads) as executor:
        for i, (response, content) in enumerate(executor.map(design_region, region_names, subprompts)):
            scene.regions[region_keys[i]].floor = ObjectDescription(
                color=response["floor"]["color"].strip(),
                material=response["floor"]["material"].strip().replace("made of ", ""),
                attributes=response["floor"]["attributes"].strip().replace("that is ", ""),
            )
            if scene.is_indoor:
                scene.regions[region_keys[i]].wall = ObjectDescription(
                    color=response["wall"]["color"].strip(),
                    material=response["wall"]["material"].strip().replace("made of ", ""),
                    attributes=response["wall"]["attributes"].strip().replace("that is ", ""),
                )
            contents[region_keys[i]] = content
    log.save()
    return content
