# -*- coding: utf-8 -*-

import json
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from typing import Any

from magic.generation import MagicConfig, MagicLog, MagicScene, Rotation3D, Vector3D
from magic.generation.dsl.checker import is_constraint_satisfied
from magic.generation.dsl.constraints import ConstraintDsl, get_constraint_dsl
from magic.generation.dsl.operations import OperationDsl, get_operation_dsl
from magic.generation.modules import OUTPUT_GUIDANCE
from magic.generation.modules.object_placement.corrections.templates import REGION_CORRECTIONS_TEMPLATE
from magic.generation.modules.object_placement.utils import hang_wall_or_ceiling, resolve_collisions
from magic.utils.dtypes import JsonObject, SDict
from magic.utils.llm import Llm, LlmContent, TemplateFormatter
from magic.utils.retry import auto_retry

get_region_corrections_prompt = TemplateFormatter(
    REGION_CORRECTIONS_TEMPLATE,
    scene_type=None,
    region_type=None,
    region_name=None,
    output_guidance=OUTPUT_GUIDANCE,
    constraint_dsl=None,
    operation_dsl=None,
    region=None,
    objects=None,
    constraints=None,
)


def get_regions_corrections(scene: MagicScene, config: MagicConfig, llm: Llm, log: MagicLog):
    cstr_dsl_str = get_constraint_dsl()
    oper_dsl_str = get_operation_dsl(scene.is_indoor)

    def get_region_corrections(region_key: str) -> tuple[SDict[SDict[list[Any]]], dict[int, list[LlmContent]]]:
        _updated_objects: defaultdict[str, SDict[list[Any]]] = defaultdict(lambda: {"position": [], "rotation": []})
        _contents = defaultdict(list)
        _llm = deepcopy(llm)
        _llm.clear_messages()
        _region = deepcopy(scene.regions[region_key])
        oper_dsl = OperationDsl()
        cstr_dsl = ConstraintDsl(oper_dsl)
        cstr_dsl.set_region_(_region)
        cstr_dsl.set_solution_index_(-1)
        region_dict = {
            "shape": {
                "min_vertex": dict(zip(["x", "z"], _region.shape.min_vertex.model_dump().values())),
                "max_vertex": dict(zip(["x", "z"], _region.shape.max_vertex.model_dump().values())),
                "width": round(_region.shape.width, 6),
                **({"height": _region.shape.height} if scene.is_indoor else {}),
                "depth": round(_region.shape.depth, 6),
            },
            **(
                {
                    "connections": [
                        {
                            "category": conn.obj.category,
                            "dimensions": conn.obj.dimensions.model_dump(),
                            "position": conn.obj.position[0].model_dump(),
                            "rotation": conn.obj.rotation[0].model_dump(),
                        }
                        for conn_name, conn in scene.get_connections_to_region(region_key).items()
                    ]
                }
                if scene.is_indoor
                else {}
            ),
        }

        @auto_retry
        def get_region_correction(constraints: list[str]) -> tuple[JsonObject, LlmContent]:
            _llm.clear_messages()
            tmp_objects = {
                oname: {
                    "dimensions": obj.dimensions.model_dump(),
                    "position": obj.position[-1].model_dump(),
                    "rotation": obj.rotation[-1].model_dump(),
                }
                for oname, obj in _region.objects.items()
            }
            prompt = get_region_corrections_prompt(
                scene_type=scene.scene_type,
                region_type=scene.region_type,
                region_name=_region.name,
                constraint_dsl=cstr_dsl_str,
                operation_dsl=oper_dsl_str,
                region=json.dumps(region_dict, ensure_ascii=False),
                objects=json.dumps(tmp_objects, ensure_ascii=False),
                constraints="\n".join(constraints),
            )
            response, llm_output = _llm.chat(prompt, temperature=config.temperature, to_json=True)
            if not isinstance(response, dict):
                raise RuntimeError()
            if "reasoning" not in response:
                raise RuntimeError()
            if not isinstance(response["reasoning"], str):
                raise RuntimeError()
            if "objects" not in response:
                raise RuntimeError()
            if not isinstance(response["objects"], dict):
                raise RuntimeError()
            for oname, new_sol in response["objects"].items():
                if not isinstance(oname, str):
                    raise RuntimeError()
                if oname not in _region.objects:
                    raise RuntimeError()
                for key in ("position", "rotation"):
                    if key not in new_sol:
                        raise RuntimeError()
                    if not isinstance(new_sol[key], list):
                        raise RuntimeError()
                    if len(new_sol[key]) != 3:
                        raise RuntimeError()
                    if not all(isinstance(item, (int, float)) for item in new_sol[key]):
                        raise RuntimeError()
            _llm.clear_messages()
            return response, llm_output.content

        def correct(constraints: list[str], t: int) -> None:
            response, content = get_region_correction(constraints)
            for oname, new_sol in response["objects"].items():
                new_pos, new_rot = hang_wall_or_ceiling(
                    _region,
                    oname,
                    Vector3D(x=new_sol["position"][0], y=new_sol["position"][1], z=new_sol["position"][2]),
                    Rotation3D(x=new_sol["rotation"][0], y=new_sol["rotation"][1], z=new_sol["rotation"][2]),
                )
                _region.objects[oname].position.append(new_pos)
                _region.objects[oname].rotation.append(new_rot)
            _contents[t].append(content)

        for t in range(config.max_solution_corrections):
            next_constraints: list[str] = []
            for cstr in _region.constraints:
                if is_constraint_satisfied(cstr, cstr_dsl, oper_dsl):
                    continue
                next_constraints.append(cstr)
                if len(next_constraints) < config.n_constraints_per_round:
                    continue
                correct(next_constraints, t)
                next_constraints.clear()
            else:
                if len(next_constraints) > 0:
                    correct(next_constraints, t)

            # record the final updated solution of each object at the end of each iteration
            for oname, obj in _region.objects.items():
                _updated_objects[oname]["position"].append(obj.position[-1])
                _updated_objects[oname]["rotation"].append(obj.rotation[-1])

            # end early if all constraints are satisfied
            if all(is_constraint_satisfied(cstr, cstr_dsl, oper_dsl) for cstr in _region.constraints):
                break

        return _updated_objects, _contents

    contents = {}
    region_keys = list(scene.regions.keys())
    with ThreadPoolExecutor(max_workers=config.max_threads) as executor:
        for i, (updated_objects, content) in enumerate(executor.map(get_region_corrections, region_keys)):
            scene.regions[region_keys[i]].clear_solutions(keep_draft=True)
            for oname, new_sols in updated_objects.items():
                scene.regions[region_keys[i]].objects[oname].position.extend(new_sols["position"])
                scene.regions[region_keys[i]].objects[oname].rotation.extend(new_sols["rotation"])
            contents[region_keys[i]] = content
    log.save()
    return contents
