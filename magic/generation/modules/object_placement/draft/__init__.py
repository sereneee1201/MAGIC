# -*- coding: utf-8 -*-

import json
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy

from magic.generation import MagicConfig, MagicLog, MagicScene, Rotation3D, Vector3D
from magic.generation.dsl.constraints import get_constraint_dsl
from magic.generation.dsl.operations import get_operation_dsl
from magic.generation.modules import OUTPUT_GUIDANCE
from magic.generation.modules.object_placement.draft.templates import REGION_DRAFT_TEMPLATE
from magic.generation.modules.object_placement.utils import hang_wall_or_ceiling, resolve_collisions
from magic.utils.dtypes import JsonObject, SDict
from magic.utils.llm import Llm, LlmContent, TemplateFormatter
from magic.utils.retry import auto_retry

get_region_draft_prompt = TemplateFormatter(
    REGION_DRAFT_TEMPLATE,
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


def draft_regions_solution(
    scene: MagicScene, config: MagicConfig, llm: Llm, log: MagicLog
) -> SDict[SDict[LlmContent]]:
    cstr_dsl_str = get_constraint_dsl()
    oper_dsl_str = get_operation_dsl(scene.is_indoor)

    @auto_retry
    def get_region_draft(region_key: str) -> tuple[JsonObject, LlmContent]:
        _llm = deepcopy(llm)
        _llm.clear_messages()
        region = {
            "shape": {
                "min_vertex": dict(zip(["x", "z"], scene.regions[region_key].shape.min_vertex.model_dump().values())),
                "max_vertex": dict(zip(["x", "z"], scene.regions[region_key].shape.max_vertex.model_dump().values())),
                "width": round(scene.regions[region_key].shape.width, 6),
                **({"height": scene.regions[region_key].shape.height} if scene.is_indoor else {}),
                "depth": round(scene.regions[region_key].shape.depth, 6),
            },
            **(
                {
                    "connections": [
                        {
                            "category": conn.obj.category,
                            "dimensions": conn.obj.dimensions.model_dump(),
                            "position": conn.obj.position[-1].model_dump(),
                            "rotation": conn.obj.rotation[-1].model_dump(),
                        }
                        for cname, conn in scene.get_connections_to_region(region_key).items()
                    ]
                }
                if scene.is_indoor
                else {}
            ),
        }
        objects = {
            oname: obj.model_dump(
                include={"category", "supported_from_below", "hanged_on_wall", "hanged_from_ceiling", "dimensions"}
            )
            for oname, obj in scene.regions[region_key].objects.items()
        }
        prompt = get_region_draft_prompt(
            scene_type=scene.scene_type,
            region_type=scene.region_type,
            region_name=scene.regions[region_key].name,
            constraint_dsl=cstr_dsl_str,
            operation_dsl=oper_dsl_str,
            region=json.dumps(region, ensure_ascii=False),
            objects=json.dumps(objects, ensure_ascii=False),
            constraints="\n".join(scene.regions[region_key].constraints),
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
        for oname in scene.regions[region_key].objects.keys():
            if oname not in response["objects"]:
                raise RuntimeError()
            if not isinstance(response["objects"][oname], dict):
                raise RuntimeError()
            for key in ("position", "rotation"):
                if key not in response["objects"][oname]:
                    raise RuntimeError()
                if not isinstance(response["objects"][oname][key], list):
                    raise RuntimeError()
                if len(response["objects"][oname][key]) != 3:
                    raise RuntimeError()
                if not all(isinstance(p, (int, float)) for p in response["objects"][oname][key]):
                    raise RuntimeError()
        return response, llm_output.content

    contents = {}
    region_keys = list(scene.regions.keys())
    with ThreadPoolExecutor(max_workers=config.max_threads) as executor:
        for i, (response, content) in enumerate(executor.map(get_region_draft, region_keys)):
            scene.regions[region_keys[i]].clear_solutions()
            for oname in scene.regions[region_keys[i]].objects.keys():
                pos, rot = hang_wall_or_ceiling(
                    scene.regions[region_keys[i]],
                    oname,
                    Vector3D(
                        x=response["objects"][oname]["position"][0],
                        y=response["objects"][oname]["position"][1],
                        z=response["objects"][oname]["position"][2],
                    ),
                    Rotation3D(
                        x=response["objects"][oname]["rotation"][0],
                        y=response["objects"][oname]["rotation"][1],
                        z=response["objects"][oname]["rotation"][2],
                    ),
                )
                scene.regions[region_keys[i]].objects[oname].position.append(pos)
                scene.regions[region_keys[i]].objects[oname].rotation.append(rot)
            resolved = resolve_collisions(scene.regions[region_keys[i]].objects, scene.regions[region_keys[i]])
            for oname, obj in resolved.items():
                scene.regions[region_keys[i]].objects[oname].position[-1] = obj.position[-1]
            contents[region_keys[i]] = content
    log.save()
    return contents
