# -*- coding: utf-8 -*-

GENERAL_NEIGHBORS_ESTABLISHMENT_TEMPLATE = """<context>
A user prompt <<inputs.prompt>> describing an {scene_type} scene is provided.
Names of all regions (i.e., {region_type}s) are provided in <<inputs.regions>>.
</context>

<objective>
Generate **all** pairs of neighbors in the scene.
A pair of neighbors is defined as two regions that **MUST** be adjacent to each other (but does **NOT** necessarily mean that they must be connected by a door).
Each provided region **MUST** have at least one neighbor, altoghether forming one connected graph (i.e., no isolated region).
**All** provided region names **MUST** be included **as is**.
</objective>

<style>
JSON
</style>

<tone>
Creative and imaginative while strictly adhering to the user's requirements.
</tone>

<audience>
A demanding professional scene designer who validates and checks your output.
</audience>

<response>
{output_guidance}

<structure>
{{
  "neighbors": [
    {{"region_a": "<<USE_PROVIDED_REGION_NAME>>", "region_b": "<<USE_PROVIDED_REGION_NAME>>"}},
    ...
  ]
}}
</structure>
</response>

<inputs>
<prompt>
{prompt}
</prompt>

<regions>
{regions}
</regions>
</inputs>"""

INDOOR_OUTSIDE_NEIGHBORS_ESTABLISHMENT_TEMPLATE = """<context>
A user prompt <<inputs.prompt>> describing an {scene_type} scene is provided.
Names of all regions (i.e., {region_type}s) are provided in <<inputs.regions>>.
</context>

<objective>
Decide which regions should be connected to the outside world ({outside_def}).
At least one region **MUST** be connected to the outside world, but **NOT** all regions need to be connected to the outside world.
Provided region names **MUST** be included **as is**.
</objective>

<style>
JSON
</style>

<tone>
Creative and imaginative while strictly adhering to the user's requirements.
</tone>

<audience>
A demanding professional scene designer who validates and checks your output.
</audience>

<response>
{output_guidance}

<structure>
{{"to_outside": ["<<USE_PROVIDED_REGION_NAME>>", ...]}}
</structure>
</response>

<inputs>
<prompt>
{prompt}
</prompt>

<regions>
{regions}
</regions>
</inputs>"""
