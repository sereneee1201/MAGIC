# -*- coding: utf-8 -*-

import json

from magic.generation import MagicConfig, MagicLog, MagicScene, RegionShape, Vector2D
from magic.generation.modules import OUTPUT_GUIDANCE, OUTSIDE_DEF
from magic.generation.modules.scene_conceptualization.regions_shape.templates import REGIONS_SHAPE_TEMPLATE
from magic.utils.llm import Llm, LlmContent, TemplateFormatter
from magic.utils.retry import auto_retry

get_regions_shape_prompt = TemplateFormatter(
    REGIONS_SHAPE_TEMPLATE, context=None, objective=None, output_guidance=OUTPUT_GUIDANCE, structure=None, inputs=None
)


def _get_regions_shape_context(scene: MagicScene) -> str:
    context = f"""\
A user prompt <<inputs.prompt>> describing an {scene.scene_type} scene is provided.
Names of all regions (i.e., {scene.region_type}s) are provided in <<inputs.regions>>.
All neighbor pairs among regions are described in <<inputs.neighbors>>."""
    if scene.is_indoor:
        context += f"""
The connections among all regions are shown in <<inputs.connections>>."""
    context += f"""
Note that "__outside__" is {OUTSIDE_DEF}.
Also, the dimensions [width, height, depth] of all objects in each region are shown in <<inputs.objects>>."""
    return context


def _get_regions_shape_objective(scene: MagicScene) -> str:
    objective = f"""\
For each region"""
    if scene.is_indoor:
        objective += ' (except "__outside__")'
    objective += """, generate a pair of vertices [min_vertex, max_vertex] representing the projection of the region's axis-aligned bounding box on a two-dimensional Cartesian coordinate plane"""
    if scene.is_indoor:
        objective += ", as well as the height (which **MUST** be greater than 0) of the region"
    objective += """.
**All** provided region names **MUST** be included **as is**.
Each region **MUST** be sufficiently large to accommodate all objects within it with room for navigation.
Each region **MUST** be touching at least one other region.
Each region **MUST NOT** overlap with any other region."""
    return objective


def _get_regions_shape_structure(scene: MagicScene) -> str:
    structure = f"""\
{{
  "<<USE_PROVIDED_REGION_NAME>>": {{
    "min_vertex": [<<FILL_IN_X>>, <<FILL_IN_Y>>],
    "max_vertex": [<<FILL_IN_X>>, <<FILL_IN_Y>>]"""
    if scene.is_indoor:
        structure += f""",
    "height": <<FILL_IN>>"""
    structure += f"""
  }},
  ...
}}"""
    return structure


def _get_regions_shape_inputs(scene: MagicScene) -> str:
    region_names = "\n".join(scene.regions.keys())
    neighbors = [pair.model_dump() for pair in scene.neighbors.values()]
    inputs = f"""\
<prompt>
{scene.design_injected_prompt}
</prompt>

<regions>
{region_names}
</regions>

<neighbors>
{json.dumps(neighbors, ensure_ascii=False)}
</neighbors>"""
    if scene.is_indoor:
        connections = {
            conn_name: {
                "region_a": detail.region_a,
                "region_b": detail.region_b,
                "category": detail.obj.category,
                "width": detail.obj.dimensions.depth,
                "height": detail.obj.dimensions.height,
            }
            for conn_name, detail in scene.connections.items()
        }
        inputs += f"""

<connections>
{json.dumps(connections, ensure_ascii=False)}
</connections>"""
    objects = {
        region_name: {
            obj_name: [obj_detail.dimensions.width, obj_detail.dimensions.height, obj_detail.dimensions.depth]
            for obj_name, obj_detail in region_detail.objects.items()
        }
        for region_name, region_detail in scene.regions.items()
    }
    inputs += f"""

<objects>
{json.dumps(objects, ensure_ascii=False)}
</objects>"""
    return inputs


@auto_retry
def get_regions_shape(scene: MagicScene, config: MagicConfig, llm: Llm, log: MagicLog) -> LlmContent:
    llm.clear_messages()
    prompt = get_regions_shape_prompt(
        context=_get_regions_shape_context(scene),
        objective=_get_regions_shape_objective(scene),
        structure=_get_regions_shape_structure(scene),
        inputs=_get_regions_shape_inputs(scene),
    )
    response, llm_output = llm.chat(prompt, temperature=config.temperature, to_json=True)
    if not isinstance(response, dict):
        raise RuntimeError()
    for region_name in scene.regions:
        if region_name not in response:
            raise RuntimeError()
        if not isinstance(response[region_name], dict):
            raise RuntimeError()
        for key in ("min_vertex", "max_vertex"):
            if key not in response[region_name]:
                raise RuntimeError()
            if not isinstance(response[region_name][key], list):
                raise RuntimeError()
            if len(response[region_name][key]) != 2:
                raise RuntimeError()
            if not all(isinstance(coord, (int, float)) for coord in response[region_name][key]):
                raise RuntimeError()
        if scene.is_indoor:
            if "height" not in response[region_name]:
                raise RuntimeError()
            if not isinstance(response[region_name]["height"], (int, float)):
                raise RuntimeError()
            if response[region_name]["height"] <= 0:
                raise RuntimeError()
        region_shape = RegionShape(
            min_vertex=Vector2D(x=response[region_name]["min_vertex"][0], y=response[region_name]["min_vertex"][1]),
            max_vertex=Vector2D(x=response[region_name]["max_vertex"][0], y=response[region_name]["max_vertex"][1]),
        )
        if scene.is_indoor:
            region_shape.height = response[region_name]["height"]
        scene.regions[region_name].shape = region_shape
    log.save()
    llm.clear_messages()
    return llm_output.content
