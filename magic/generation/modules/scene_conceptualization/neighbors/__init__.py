# -*- coding: utf-8 -*-

from magic.generation import MagicConfig, MagicLog, MagicScene
from magic.generation.modules import OUTPUT_GUIDANCE, OUTSIDE_DEF
from magic.generation.modules.scene_conceptualization.neighbors.templates import (
    GENERAL_NEIGHBORS_ESTABLISHMENT_TEMPLATE,
    INDOOR_OUTSIDE_NEIGHBORS_ESTABLISHMENT_TEMPLATE,
)
from magic.utils.dtypes import SDict
from magic.utils.llm import Llm, LlmContent, TemplateFormatter
from magic.utils.retry import auto_retry

get_general_neighbors_prompt = TemplateFormatter(
    GENERAL_NEIGHBORS_ESTABLISHMENT_TEMPLATE,
    scene_type=None,
    region_type=None,
    output_guidance=OUTPUT_GUIDANCE,
    prompt=None,
    regions=None,
)
get_indoor_outside_neighbors_prompt = TemplateFormatter(
    INDOOR_OUTSIDE_NEIGHBORS_ESTABLISHMENT_TEMPLATE,
    scene_type=None,
    region_type=None,
    outside_def=OUTSIDE_DEF,
    output_guidance=OUTPUT_GUIDANCE,
    prompt=None,
    regions=None,
)


@auto_retry
def _establish_general_neighbors(scene: MagicScene, config: MagicConfig, llm: Llm, log: MagicLog) -> LlmContent:
    llm.clear_messages()
    prompt = get_general_neighbors_prompt(
        scene_type=scene.scene_type,
        region_type=scene.region_type,
        prompt=scene.design_injected_prompt,
        regions="\n".join(scene.regions.keys()),
    )
    response, llm_output = llm.chat(prompt, temperature=config.temperature, to_json=True)
    # ----- Validation -----
    if not isinstance(response, dict):
        raise RuntimeError()
    if "neighbors" not in response:
        raise RuntimeError()
    if not isinstance(response["neighbors"], list):
        raise RuntimeError()
    for neighbor in response["neighbors"]:
        if not isinstance(neighbor, dict):
            raise RuntimeError()
        for key in ("region_a", "region_b"):
            if key not in neighbor:
                raise RuntimeError()
            if not isinstance(neighbor[key], str):
                raise RuntimeError()
    # ======================
    for neighbor in response["neighbors"]:
        if neighbor["region_a"] == "outside":
            continue
        if neighbor["region_b"] == "outside":
            continue
        scene.add_neighbor_pair(neighbor["region_a"], neighbor["region_b"])
    log.save()
    llm.clear_messages()
    return llm_output.content


@auto_retry
def _establish_indoor_outside_neighbors(scene: MagicScene, config: MagicConfig, llm: Llm, log: MagicLog) -> LlmContent:
    llm.clear_messages()
    prompt = get_indoor_outside_neighbors_prompt(
        scene_type=scene.scene_type,
        region_type=scene.region_type,
        prompt=scene.design_injected_prompt,
        regions="\n".join(scene.regions.keys()),
    )
    response, llm_output = llm.chat(prompt, temperature=config.temperature, to_json=True)
    # ----- Validation -----
    if not isinstance(response, dict):
        raise RuntimeError()
    if "to_outside" not in response:
        raise RuntimeError()
    if not isinstance(response["to_outside"], list):
        raise RuntimeError()
    for region_name in response["to_outside"]:
        if not isinstance(region_name, str):
            raise RuntimeError()
    # ======================
    for region_name in response["to_outside"]:
        scene.add_neighbor_pair(region_name, "__outside__")
    log.save()
    llm.clear_messages()
    return llm_output.content


@auto_retry
def establish_neighbors(scene: MagicScene, config: MagicConfig, llm: Llm, log: MagicLog) -> SDict[LlmContent]:
    contents = {}
    if scene.n_regions > 1:
        contents["general_neighbors"] = _establish_general_neighbors(scene, config, llm, log)
        if not scene.check_all_regions_have_neighbor():
            raise RuntimeError("Not all regions have at least one neighbor")
    if scene.is_indoor:
        contents["indoor_outside_neighbors"] = _establish_indoor_outside_neighbors(scene, config, llm, log)
    return contents
