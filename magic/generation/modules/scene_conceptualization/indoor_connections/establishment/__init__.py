# -*- coding: utf-8 -*-

import json

from magic.generation import AnticipatedObject, Dimensions3D, MagicConfig, MagicLog, MagicScene, ObjectDescription
from magic.generation.modules import CONNECTION_THICKNESS, OUTPUT_GUIDANCE, OUTSIDE_DEF
from magic.generation.modules.scene_conceptualization.indoor_connections.establishment.templates import (
    INDOOR_CONNECTIONS_CATEGORY_TEMPLATE,
    INDOOR_CONNECTIONS_DESCRIPTION_TEMPLATE,
    INDOOR_CONNECTIONS_DIMENSIONS_TEMPLATE,
    INDOOR_CONNECTIONS_TEMPLATE,
)
from magic.utils.dtypes import SDict
from magic.utils.llm import Llm, LlmContent, TemplateFormatter
from magic.utils.maths import clamp
from magic.utils.retry import auto_retry

get_indoor_connections_prompt = TemplateFormatter(
    INDOOR_CONNECTIONS_TEMPLATE,
    scene_type=None,
    region_type=None,
    outside_def=OUTSIDE_DEF,
    output_guidance=OUTPUT_GUIDANCE,
    prompt=None,
    doors=None,
    p_windows=None,
    regions=None,
    neighbors=None,
    error="",
)
get_indoor_connections_category_prompt = TemplateFormatter(
    INDOOR_CONNECTIONS_CATEGORY_TEMPLATE,
    scene_type=None,
    region_type=None,
    outside_def=OUTSIDE_DEF,
    output_guidance=OUTPUT_GUIDANCE,
    prompt=None,
    doors=None,
    windows=None,
    p_windows=None,
    error="",
)
get_indoor_connections_description_prompt = TemplateFormatter(
    INDOOR_CONNECTIONS_DESCRIPTION_TEMPLATE,
    scene_type=None,
    region_type=None,
    outside_def=OUTSIDE_DEF,
    output_guidance=OUTPUT_GUIDANCE,
    prompt=None,
    doors=None,
    windows=None,
)
get_indoor_connections_dimensions_prompt = TemplateFormatter(
    INDOOR_CONNECTIONS_DIMENSIONS_TEMPLATE,
    scene_type=None,
    region_type=None,
    outside_def=OUTSIDE_DEF,
    output_guidance=OUTPUT_GUIDANCE,
    prompt=None,
    doors=None,
    windows=None,
)


@auto_retry
def _get_indoor_connections(scene: MagicScene, config: MagicConfig, llm: Llm, log: MagicLog, doors: list, p_windows: list) -> LlmContent:
    llm.clear_messages()
    neighbors = [pair.model_dump() for pair in scene.neighbors.values()]
    prompt = get_indoor_connections_prompt(
        scene_type=scene.scene_type,
        region_type=scene.region_type,
        prompt=scene.design_injected_prompt,
        doors=doors,
        p_windows=p_windows,
        regions="\n".join([*scene.regions.keys(), "__outside__"]),
        neighbors=json.dumps(neighbors, ensure_ascii=False),
        error=""
    )
    response, llm_output = llm.chat(prompt, temperature=config.temperature, to_json=True)
    # ----- Validation -----
    count = 0
    while (len(response["doors"]) != len(doors) or len(response["windows"]) < len(p_windows)) and count < 10:
        error = f"Expected {len(doors)} doors and at least {len(p_windows)} windows."
        print(error)
        prompt = get_indoor_connections_prompt(
            scene_type=scene.scene_type,
            region_type=scene.region_type,
            prompt=scene.design_injected_prompt,
            doors=doors,
            p_windows=p_windows,
            regions="\n".join([*scene.regions.keys(), "__outside__"]),
            neighbors=json.dumps(neighbors, ensure_ascii=False),
            error=error
        )
        response, llm_output = llm.chat(prompt, temperature=config.temperature, to_json=True)
        count += 1

    if not isinstance(response, dict):
        raise RuntimeError()
    if "doors" not in response:
        raise RuntimeError()
    if not isinstance(response["doors"], list):
        raise RuntimeError()
    for door in response["doors"]:
        if not isinstance(door, dict):
            raise RuntimeError()
        if "region_a" not in door:
            raise RuntimeError()
        if not isinstance(door["region_a"], str):
            raise RuntimeError()
        if "region_b" not in door:
            raise RuntimeError()
        if not isinstance(door["region_b"], str):
            raise RuntimeError()
    if "windows" not in response:
        raise RuntimeError()
    if not isinstance(response["windows"], list):
        raise RuntimeError()
    for window in response["windows"]:
        if not isinstance(window, dict):
            raise RuntimeError()
        if "region_a" not in window:
            raise RuntimeError()
        if not isinstance(window["region_a"], str):
            raise RuntimeError()
        if "region_b" not in window:
            raise RuntimeError()
        if not isinstance(window["region_b"], str):
            raise RuntimeError()
    # ======================
    for door in response["doors"]:
        scene.add_door(door["region_a"], door["region_b"])
    for window in response["windows"]:
        scene.add_window(window["region_a"], window["region_b"])
    log.save()
    llm.clear_messages()
    return llm_output.content


@auto_retry
def _get_indoor_connections_category(scene: MagicScene, config: MagicConfig, llm: Llm, log: MagicLog, p_windows: list) -> LlmContent:
    llm.clear_messages()
    error = f"{len(p_windows)} windows are expected to be labelled as portals: {p_windows}"
    doors = {
        name: {"region_a": detail.region_a, "region_b": detail.region_b}
        for name, detail in scene.connections.items()
        if name.startswith("door")
    }
    windows = {
        name: {"region_a": detail.region_a, "region_b": detail.region_b}
        for name, detail in scene.connections.items()
        if name.startswith("window")
    }
    prompt = get_indoor_connections_category_prompt(
        scene_type=scene.scene_type,
        region_type=scene.region_type,
        prompt=scene.design_injected_prompt,
        doors=json.dumps(doors, ensure_ascii=False),
        windows=json.dumps(windows, ensure_ascii=False),
        p_windows=p_windows,
        error=error
    )
    response, llm_output = llm.chat(prompt, temperature=config.temperature, to_json=True)
    p_window_count = 0
    for conn_name in scene.connections:
        if not conn_name.startswith("window"):
            continue
        if response["windows"][conn_name]["is_portal"] == True:
            p_window_count += 1

    count = 0
    while count < 10 and p_window_count != len(p_windows):
        error = f"{len(p_windows)} windows are expected to be labelled as portals: {p_windows}"
        prompt = get_indoor_connections_category_prompt(
            scene_type=scene.scene_type,
            region_type=scene.region_type,
            prompt=scene.design_injected_prompt,
            doors=json.dumps(doors, ensure_ascii=False),
            windows=json.dumps(windows, ensure_ascii=False),
            p_windows=p_windows,
            error=error
        )
        response, llm_output = llm.chat(prompt, temperature=config.temperature, to_json=True)
        p_window_count = 0
        for conn_name in scene.connections:
            if not conn_name.startswith("window"):
                continue
            if response["windows"][conn_name]["is_portal"] == True:
                p_window_count += 1
        count += 1
            
    # ----- Validation -----
    if not isinstance(response, dict):
        raise RuntimeError()
    for key in ("doors", "windows"):
        if key not in response:
            raise RuntimeError()
        if not isinstance(response[key], dict):
            raise RuntimeError()
    for conn_name in scene.connections:
        prefix = conn_name.split("_")[0]
        if conn_name not in response[f"{prefix}s"]:
            raise RuntimeError()
        if not isinstance(response[f"{prefix}s"][conn_name], dict):
            raise RuntimeError()
        if response[f"{prefix}s"][conn_name] == None:
            raise RuntimeError()
    # ======================
    for conn_name in scene.connections:
        prefix = conn_name.split("_")[0]
        scene.connections[conn_name].obj = AnticipatedObject(category=response[f"{prefix}s"][conn_name]["category"].strip())
        scene.connections[conn_name].obj.is_portal = response[f"{prefix}s"][conn_name]["is_portal"]
    log.save()
    llm.clear_messages()
    return llm_output.content


@auto_retry
def _get_indoor_connections_description(scene: MagicScene, config: MagicConfig, llm: Llm, log: MagicLog) -> LlmContent:
    llm.clear_messages()
    doors = {
        name: {"region_a": detail.region_a, "region_b": detail.region_b, "category": detail.obj.category}
        for name, detail in scene.connections.items()
        if name.startswith("door")
    }
    windows = {
        name: {"region_a": detail.region_a, "region_b": detail.region_b, "category": detail.obj.category}
        for name, detail in scene.connections.items()
        if name.startswith("window")
    }
    prompt = get_indoor_connections_description_prompt(
        scene_type=scene.scene_type,
        region_type=scene.region_type,
        prompt=scene.design_injected_prompt,
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
    for conn_name in scene.connections:
        prefix = conn_name.split("_")[0]
        if conn_name not in response[f"{prefix}s"]:
            raise RuntimeError()
        if not isinstance(response[f"{prefix}s"][conn_name], dict):
            raise RuntimeError()
        if "color" not in response[f"{prefix}s"][conn_name]:
            raise RuntimeError()
        if not isinstance(response[f"{prefix}s"][conn_name]["color"], str):
            raise RuntimeError()
        if response[f"{prefix}s"][conn_name]["color"].strip() == "":
            raise RuntimeError()
        if "material" not in response[f"{prefix}s"][conn_name]:
            raise RuntimeError()
        if not isinstance(response[f"{prefix}s"][conn_name]["material"], str):
            raise RuntimeError()
        if response[f"{prefix}s"][conn_name]["material"].strip() == "":
            raise RuntimeError()
        if "attributes" not in response[f"{prefix}s"][conn_name]:
            raise RuntimeError()
        if not isinstance(response[f"{prefix}s"][conn_name]["attributes"], str):
            raise RuntimeError()

    # ======================
    for conn_name in scene.connections:
        prefix = conn_name.split("_")[0]
        scene.connections[conn_name].obj.description = ObjectDescription(
            color=response[f"{prefix}s"][conn_name]["color"].strip(),
            material=response[f"{prefix}s"][conn_name]["material"].strip().replace("made with ", ""),
            attributes=response[f"{prefix}s"][conn_name]["attributes"].strip().replace("that is ", ""),
        )
    log.save()
    llm.clear_messages()
    return llm_output.content


@auto_retry
def _get_indoor_connections_dimensions(scene: MagicScene, config: MagicConfig, llm: Llm, log: MagicLog) -> LlmContent:
    llm.clear_messages()
    doors = {
        name: {"region_a": detail.region_a, "region_b": detail.region_b, "category": detail.obj.category}
        for name, detail in scene.connections.items()
        if name.startswith("door")
    }
    windows = {
        name: {"region_a": detail.region_a, "region_b": detail.region_b, "category": detail.obj.category}
        for name, detail in scene.connections.items()
        if name.startswith("window")
    }
    prompt = get_indoor_connections_dimensions_prompt(
        scene_type=scene.scene_type,
        region_type=scene.region_type,
        prompt=scene.design_injected_prompt,
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
    for conn_name in scene.connections:
        prefix = conn_name.split("_")[0]
        if conn_name not in response[f"{prefix}s"]:
            raise RuntimeError()
        if not isinstance(response[f"{prefix}s"][conn_name], list):
            raise RuntimeError()
        if len(response[f"{prefix}s"][conn_name]) != 2:
            raise RuntimeError()
        if not all(isinstance(d, (int, float)) for d in response[f"{prefix}s"][conn_name]):
            raise RuntimeError()
        if response[f"{prefix}s"][conn_name][0] <= 0:
            raise RuntimeError()
        if response[f"{prefix}s"][conn_name][1] <= 0:
            raise RuntimeError()
    # ======================
    for conn_name in scene.connections:
        prefix = conn_name.split("_")[0]
        scene.connections[conn_name].obj.dimensions = Dimensions3D(
            width=response[f"{prefix}s"][conn_name][0],
            height=response[f"{prefix}s"][conn_name][1],
            depth=CONNECTION_THICKNESS,
        )
    log.save()
    llm.clear_messages()
    return llm_output.content


def establish_indoor_connections(scene: MagicScene, config: MagicConfig, llm: Llm, log: MagicLog, doors: list, p_windows: list) -> SDict[LlmContent]:
    contents = {}
    contents["indoor_connections"] = _get_indoor_connections(scene, config, llm, log, doors, p_windows)
    contents["indoor_connections_name"] = _get_indoor_connections_category(scene, config, llm, log, p_windows)
    contents["indoor_connections_description"] = _get_indoor_connections_description(scene, config, llm, log)
    contents["indoor_connections_dimensions"] = _get_indoor_connections_dimensions(scene, config, llm, log)
    return contents
