# -*- coding: utf-8 -*-

import json
import random
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from typing import Any

from magic.generation import MagicConfig, MagicLog, MagicScene
from magic.generation.dsl.constraints import get_constraint_dsl, get_constraint_dsl_signature
from magic.generation.dsl.operations import get_operation_dsl, get_operation_dsl_signature
from magic.generation.modules import OUTPUT_GUIDANCE
from magic.generation.modules.scene_conceptualization.constraints.templates import REGION_CONSTRAINTS_TEMPLATE
from magic.generation.modules.scene_conceptualization.constraints.validation import (
    check_constraint,
    modify_constraints,
)
from magic.utils.dtypes import JsonObject, SDict
from magic.utils.llm import Llm, LlmContent, TemplateFormatter
from magic.utils.retry import auto_retry

get_region_constraints_prompt = TemplateFormatter(
    REGION_CONSTRAINTS_TEMPLATE,
    scene_type=None,
    region_type=None,
    region_name=None,
    objective=None,
    output_guidance=OUTPUT_GUIDANCE,
    constraint_dsl=None,
    operation_dsl=None,
    region=None,
)


def _get_region_constraints_objective(scene: MagicScene) -> str:
    objective = f"""\
Using the domain-specific language (DSL) in <<dsl>> that is designed to describe any scenes, for each object under "objects" in <<inputs.region>>, generate **all** positional and rotational constraints that (1) the object **MUST** possess based on "object_relations" in <<inputs.region>> and (2) should possess based on your spatial common sense.
Each constraint **MUST** begin with an assertive function under <<dsl.constraints>>, and the parameters of that function **MUST** be filled with real numbers, strings, and/or supportive functions under <<dsl.operations>>.
An example of a syntactically correct constraint is "mustEqualTo(getObjectMinPositionY('coffee_cup'), getObjectMaxPositionY('table'))".
A sufficient set of carefully crafted and syntactically correct constraints (without invalid or redundant constraints) **MUST** be generated such that the (relative) position and rotation of each object can be determined (not deterministic though, so the use of random numbers is allowed).
Without any rotation, each object's forward vector points towards the positive z-axis, and the upward vector points towards the positive y-axis.
Moreover, an object with "supported_from_below" marked as true **MUST** be placed on some surface (i.e., the bottom of the object is aligned with the top of another object or the floor, and thus at least one extra constraint **MUST** be generated to make sure that the object is properly placed on a surface)"""
    if scene.is_indoor:
        objective += """, "hanged_on_wall" marked as true **MUST** be placed on a wall, and "hanged_from_ceiling" marked as true **MUST** be hanged from the ceiling."""
    else:
        objective += "."
    objective += f"""
Furthermore, while you do **NOT** need to explicitly generate constraints to require that an object should be placed within its assigned region, you **MUST** generate constraints to make sure that 
(1) no two objects collide with each other 
(2) entrances and exits (especially connections such as doors) are **NOT** blocked by any objects 
Most importantly, a generated constraint **MUST NOT** contradict with any other constraints.
**All** provided object and region names **MUST** be included **as is**.
Also, provide a comprehensive and thorough reasoning on your decisions."""
    return objective


@auto_retry
def _get_regions_constraints(scene: MagicScene, config: MagicConfig, llm: Llm, log: MagicLog) -> SDict[LlmContent]:
    cstr_dsl_str = get_constraint_dsl()
    oper_dsl_str = get_operation_dsl(is_indoor=scene.is_indoor)
    cstr_dsl_signature = get_constraint_dsl_signature()
    oper_dsl_signature = get_operation_dsl_signature()

    @auto_retry
    def get_region_constraints(region_name: str, region: SDict[Any]) -> tuple[JsonObject, LlmContent]:
        _llm = deepcopy(llm)
        _llm.clear_messages()
        prompt = get_region_constraints_prompt(
            scene_type=scene.scene_type,
            region_type=scene.region_type,
            region_name=region_name,
            objective=_get_region_constraints_objective(scene),
            constraint_dsl=cstr_dsl_str,
            operation_dsl=oper_dsl_str,
            region=json.dumps(region, ensure_ascii=False),
        )
        response, llm_output = _llm.chat(prompt, temperature=config.temperature, to_json=True)
        if not isinstance(response, dict):
            raise RuntimeError()
        if "reasoning" not in response:
            raise RuntimeError()
        if not isinstance(response["reasoning"], str):
            raise RuntimeError()
        if "constraints" not in response:
            raise RuntimeError()
        if not isinstance(response["constraints"], dict):
            raise RuntimeError()
        for key in ("positional", "rotational"):
            if key not in response["constraints"]:
                raise RuntimeError()
            if not isinstance(response["constraints"][key], list):
                raise RuntimeError()
            for cstr in response["constraints"][key]:
                if not isinstance(cstr, str):
                    raise RuntimeError()
        return response, llm_output.content

    contents = {}
    region_names = [region.name for region in scene.regions.values()]
    region_keys = list(scene.regions.keys())
    regions = [
        {
            "shape": {
                "width": round(scene.regions[key].shape.width, 6),
                **({"height": scene.regions[key].shape.height} if scene.is_indoor else {}),
                "depth": round(scene.regions[key].shape.depth, 6),
            },
            "objects": {
                obj_name: {
                    "dimensions": obj.dimensions.model_dump(),
                    "supported_from_below": obj.supported_from_below,
                    **(
                        {"hanged_on_wall": obj.hanged_on_wall, "hanged_from_ceiling": obj.hanged_from_ceiling}
                        if scene.is_indoor
                        else {}
                    ),
                }
                for obj_name, obj in scene.regions[key].objects.items()
            },
            "object_relations": scene.regions[key].object_relations,
            **(
                {
                    "connections": [
                        {"category": conn.obj.category, "dimensions": conn.obj.dimensions.model_dump()}
                        for conn_name, conn in scene.get_connections_to_region(key).items()
                    ]
                }
                if scene.is_indoor
                else {}
            ),
        }
        for key in region_keys
    ]
    with ThreadPoolExecutor(max_workers=config.max_threads) as executor:
        for i, (response, content) in enumerate(executor.map(get_region_constraints, region_names, regions)):
            scene.regions[region_keys[i]].clear_constraints()
            appeared_cstr = set()
            total_cstr, good_cstr = 0, 0
            for key in ("positional", "rotational"):
                for cstr in response["constraints"][key]:
                    cstr = cstr.strip()
                    if cstr in appeared_cstr:
                        continue
                    appeared_cstr.add(cstr)
                    total_cstr += 1
                    if check_constraint(cstr, scene.regions[region_keys[i]], cstr_dsl_signature, oper_dsl_signature):
                        scene.regions[region_keys[i]].constraints.append(cstr)
                        good_cstr += 1
            scene.regions[region_keys[i]].cstr_syntax_passing_rate = good_cstr / total_cstr if total_cstr > 0 else 0.0
            contents[region_keys[i]] = content
    log.save()
    return contents


def _modify_regions_constraints(
    scene: MagicScene, config: MagicConfig, llm: Llm, log: MagicLog, problem: str
) -> SDict[LlmContent]:
    contents = {}
    cstr_dsl_str = get_constraint_dsl()
    oper_dsl_str = get_operation_dsl(scene.is_indoor)
    match problem:
        case "nonsensical":
            tgt_region_names = [
                name
                for name in scene.regions.keys()
                if not scene.regions[name].no_nonsensical_cstr and len(scene.regions[name].constraints) > 1
            ]
        case "redundant":
            tgt_region_names = [
                name
                for name in scene.regions.keys()
                if not scene.regions[name].no_redundant_cstr and len(scene.regions[name].constraints) > 1
            ]
        case "contradicted":
            tgt_region_names = [
                name
                for name in scene.regions.keys()
                if not scene.regions[name].no_contradicted_cstr and len(scene.regions[name].constraints) > 1
            ]
        case _:
            raise ValueError(f"Invalid problem '{problem}'")
    if len(tgt_region_names) == 0:
        return contents
    with ThreadPoolExecutor(max_workers=config.max_threads) as executor:
        for i, future in enumerate(
            [
                executor.submit(
                    modify_constraints,
                    config,
                    deepcopy(llm),
                    cstr_dsl_str,
                    oper_dsl_str,
                    scene.regions[name].constraints,
                    problem,
                )
                for name in tgt_region_names
            ]
        ):
            response, content = future.result()
            region = scene.regions[tgt_region_names[i]]
            problems = response["problems"]
            to_remove = set()
            for item in problems:
                if problem == "nonsensical":
                    if isinstance(item["index"], int):
                        index = item["index"] - 1
                        to_remove.add(index)
                elif problem in {"redundant", "contradicted"}:
                    indexes = item["indexes"]
                    indexes = [idx - 1 for idx in indexes]
                    if len(indexes) > 1:
                        to_remove.update(random.sample(indexes, k=len(indexes) - 1))
            if problem == "nonsensical":
                region.cstr_nonsense_passing_rates.append(1 - len(to_remove) / len(region.constraints))
            elif problem == "redundant":
                region.cstr_redundancy_passing_rates.append(1 - len(to_remove) / len(region.constraints))
            elif problem == "contradicted":
                region.cstr_contradiction_passing_rates.append(1 - len(to_remove) / len(region.constraints))
            if len(to_remove) == 0:
                if problem == "nonsensical":
                    region.no_nonsensical_cstr = True
                elif problem == "redundant":
                    region.no_redundant_cstr = True
                elif problem == "contradicted":
                    region.no_contradicted_cstr = True
            else:
                for idx in sorted(to_remove, reverse=True):
                    region.constraints.pop(idx)
            contents[tgt_region_names[i]] = content
    log.save()
    return contents


def get_regions_constraints(scene: MagicScene, config: MagicConfig, llm: Llm, log: MagicLog) -> SDict[Any]:
    contents = {}
    contents["constraints_generation"] = _get_regions_constraints(scene, config, llm, log)

    contents["constraints_redundancy_validation"] = red_val = []
    for _ in range(config.max_constraint_modifications):
        red_val.append(_modify_regions_constraints(scene, config, llm, log, "redundant"))
    contents["constraints_contradiction_validation"] = con_val = []
    for _ in range(config.max_constraint_modifications):
        con_val.append(_modify_regions_constraints(scene, config, llm, log, "contradicted"))
    for region in scene.regions.values():
        _allowed_collision: set[tuple[str, str]] = set()
        _allowed_outside: set[str] = set()
        for cstr in region.constraints:
            if cstr.startswith("allowCollide("):
                try:
                    args = cstr[cstr.index("(") + 1 : cstr.index(")")].split(",")
                except ValueError:
                    continue
                if len(args) != 2:
                    continue
                obj1, obj2 = args[0].strip(" '\""), args[1].strip(" '\"")
                if obj1 not in region.objects or obj2 not in region.objects:
                    continue
                if obj1 == obj2:
                    continue
                _allowed_collision.add(tuple(sorted((obj1, obj2))))
            elif cstr.startswith("allowOutside("):
                try:
                    obj = cstr[cstr.index("(") + 1 : cstr.index(")")].strip(" '\"")
                except ValueError:
                    continue
                if obj not in region.objects:
                    continue
                _allowed_outside.add(obj)
        region.allowed_collision = _allowed_collision
        region.allowed_outside = _allowed_outside
    log.save()
    return contents
