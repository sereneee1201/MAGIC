# -*- coding: utf-8 -*-

import json
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy

from magic.generation import AnticipatedObject, MagicConfig, MagicLog, MagicScene
from magic.generation.modules import OUTPUT_GUIDANCE
from magic.generation.modules.scene_conceptualization.regions_objects.parent_objects_name.templates import (
    REGION_PARENT_OBJECTS_NAME_TEMPLATE,
)
from magic.utils.dtypes import JsonObject, SDict
from magic.utils.llm import Llm, LlmContent, TemplateFormatter
from magic.utils.misc import remove_trailing_digits, replace_non_alphanumeric
from magic.utils.retry import auto_retry

get_region_parent_objects_name_prompt = TemplateFormatter(
    REGION_PARENT_OBJECTS_NAME_TEMPLATE,
    scene_type=None,
    region_type=None,
    region_name=None,
    portals=None,
    objective=None,
    output_guidance=OUTPUT_GUIDANCE,
    structure=None,
    prompt=None,
    missing="",
)

def map_portals_to_regions(llm: Llm, region_subprompts: list[str], portals: list[str]):
    prompt = f"""
You are given a list of regions with their descriptions and a list of portals.
Determine which region(s) each portal most likely belongs to based on contextual clues.

- Each region corresponds to one subprompt.
- Output must be a valid **JSON list**, where each element is a list of portals for that region.
- The number of elements in the outer list **MUST** equal the number of region descriptions.
- **All** portals must appear in the output **exactly once**.
- Use **double quotes only** (no single quotes, no comments, no extra text).

Example Output:
[
  ["mirror", "carpet"],
  ["crystal ball"],
  []
]

Region Descriptions: {region_subprompts}
Portals: {portals}
"""

    response, _ = llm.chat(prompt, temperature=0.3)
    result = json.loads(response)

    # validate output structure
    if not isinstance(result, list) or not all(isinstance(x, list) for x in result):
        raise RuntimeError("Response must be a list of lists of portal names.")

    while len(result) < len(region_subprompts):
        result.append([])

    return result

def _get_region_parent_objects_name_objective(scene: MagicScene) -> str:
    objective = f"""\
Based on the user prompt, determine the names (which must be unique) and categories of **all** objects in this region.

For **ALL** objects mentioned in the list of portals:
- They **MUST** be included in your response.
- The "is_portal" field **MUST** be true.
- The names **MUST** include the name listed in portals.
For objects **NOT** mentioned in the list of portals, they **MUST** have "is_portal" field as false.

An object is an individual item that can be picked up or moved, **NOT** a zone or an abstract feature.
If the quantity of an object is mentioned in the prompt, you **MUST** respond with the same quantity of that object.
Moreover, the category of an object **MUST** be semantically meaningful --- do **NOT** generate vague categories including (but **NOT** limited to) "furniture", "fixture", and "component".
Also, determine whether an object should be supported from below (i.e., the bottom of the object is aligned with the top of another object or the floor)"""
    if scene.is_indoor:
        objective += f""", hanged on a wall, and/or hanged from a ceiling.
Note that "supported_from_below" and "hanged_from_ceiling" **MUST NOT** be both true."""
    else:
        objective += "."
    objective += f"""
Do **NOT** include doors, doorframes, windows, and stairs in your response.
Do **NOT** include any portal doors or portal windows.
Double-check that **ALL** objects mentioned in the portal list are included in your response.
Double-check that **ALL** object mentioned in the prompt are included.
."""
    return objective


def _get_region_parent_objects_name_structure(scene: MagicScene) -> str:
    structure = f"""\
{{
  "objects": [
    {{
      "name": "<<FILL_IN_OBJECT_NAME>>",
      "category": "<<FILL_IN>>",
      "supported_from_below": true/false,
      "is_portal": true/false
      """
    if scene.is_indoor:
        structure += f""",
      "hanged_on_wall": true/false,
      "hanged_from_ceiling": true/false"""
    structure += f"""
    }},
    ...
  ]
}}"""
    return structure


def _create_obj_counter(objects: list[SDict[str | list[str]]]) -> SDict[list[int]]:
    obj_counter: defaultdict[str, list[int]] = defaultdict(lambda: [0, 0])
    for obj in objects:
        obj_name = replace_non_alphanumeric(remove_trailing_digits(obj["name"].lower()))
        if obj_name == "":
            continue
        obj_counter[obj_name][0] += 1
    return obj_counter


def get_regions_parent_objects_name(
    scene: MagicScene, config: MagicConfig, llm: Llm, log: MagicLog, portals: list
) -> LlmContent | SDict[LlmContent]:
    @auto_retry
    def get_region_parent_objects_name(region_name: str, subprompt: str, portals: list) -> tuple[JsonObject, LlmContent]:
        _llm = deepcopy(llm)
        _llm.clear_messages()
        prompt = get_region_parent_objects_name_prompt(
            scene_type=scene.scene_type,
            region_type=scene.region_type,
            region_name=region_name,
            portals = portals,
            objective=_get_region_parent_objects_name_objective(scene),
            structure=_get_region_parent_objects_name_structure(scene),
            prompt=subprompt,
            missing="",
        )
        response, llm_output = _llm.chat(prompt, temperature=config.temperature, to_json=True)

        count = 0
        missing = [
            portal for portal in portals
            if portal not in [obj["name"] for obj in response.get("objects", []) if obj.get("is_portal")]
        ]
        while len(missing) != 0 and count < 10:
            print("Missing portals:", missing)
            prompt = get_region_parent_objects_name_prompt(
                scene_type=scene.scene_type,
                region_type=scene.region_type,
                region_name=region_name,
                portals = portals,
                objective=_get_region_parent_objects_name_objective(scene),
                structure=_get_region_parent_objects_name_structure(scene),
                prompt=subprompt,
                missing=", ".join(missing),
            )
            response, llm_output = _llm.chat(prompt, temperature=config.temperature, to_json=True)
            missing = [
                portal for portal in portals
                if portal not in [obj["name"] for obj in response.get("objects", []) if obj.get("is_portal")]
            ]
            count += 1

        if not isinstance(response, dict):
            raise RuntimeError()
        if "objects" not in response:
            raise RuntimeError()
        if not isinstance(response["objects"], list):
            raise RuntimeError()
        for obj in response["objects"]:
            if not isinstance(obj, dict):
                raise RuntimeError()
            if "name" not in obj:
                raise RuntimeError()
            if not isinstance(obj["name"], str):
                raise RuntimeError()
            if "category" not in obj:
                raise RuntimeError()
            if not isinstance(obj["category"], str):
                raise RuntimeError()
            if "is_portal" not in obj:
                raise RuntimeError()
            if "supported_from_below" not in obj:
                raise RuntimeError()
            if not isinstance(obj["supported_from_below"], bool):
                raise RuntimeError()
            if scene.is_indoor:
                for key in ("hanged_on_wall", "hanged_from_ceiling"):
                    if key not in obj:
                        raise RuntimeError()
                    if not isinstance(obj[key], bool):
                        raise RuntimeError()
        return response, llm_output.content

    contents = {}
    region_names = [region.name for region in scene.regions.values()]
    subprompts = [region.object_injected_subprompt for region in scene.regions.values()]
    region_keys = list(scene.regions.keys())
    portals = map_portals_to_regions(llm, subprompts, portals)
    with ThreadPoolExecutor(max_workers=config.max_threads) as executor:
        for i, (response, content) in enumerate(
            executor.map(get_region_parent_objects_name, region_names, subprompts, portals)
        ):  
            obj_counter = _create_obj_counter(response["objects"])
            for obj in response["objects"]:
                obj_name = replace_non_alphanumeric(remove_trailing_digits(obj["name"].lower()))
                if obj_name == "":
                    continue
                cat = replace_non_alphanumeric(remove_trailing_digits(obj["category"].lower()))
                if cat == "":
                    cat = obj_name
                cat = cat.replace("_", " ")
                new_obj = AnticipatedObject(
                    category=cat,
                    supported_from_below=obj["supported_from_below"],
                    is_portal=obj["is_portal"],
                    hanged_on_wall=obj["hanged_on_wall"] if scene.is_indoor else False,
                    hanged_from_ceiling=(
                        obj["hanged_from_ceiling"] and not obj["supported_from_below"] if scene.is_indoor else False
                    ),
                )
                if obj_counter[obj_name][0] == 1:
                    obj_counter[obj_name][1] = 1
                    scene.regions[region_keys[i]].objects[obj_name] = new_obj
                else:
                    obj_counter[obj_name][1] += 1
                    _obj_name = f"{obj_name}_{obj_counter[obj_name][1]}"
                    scene.regions[region_keys[i]].objects[_obj_name] = new_obj
                assert obj_counter[obj_name][1] <= obj_counter[obj_name][0]
            contents[region_keys[i]] = content
    log.save()
    return contents
