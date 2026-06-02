# -*- coding: utf-8 -*-

REGION_PARENT_OBJECTS_RELATIONS_TEMPLATE = """<context>
A user prompt <<inputs.prompt>> describing an {scene_type} region (i.e., {region_type}) named "{region_name}" is provided.
This region consists of objects listed in <<inputs.objects>>.
</context>

<objective>
Based on the provided user prompt, for every pair of objects, generate 3-tuples of [objectA, relation, objectB] which encode different relations between that pair of objects.
`objectA` and `objectB` are object names; `relation` is a phrase or an incomplete sentence (numerical values can be optionally included) that describes how `objectA` is physically related to `objectB` according to `relation`.
In other words, a 3-tuple should be able to resemble the following sentence: "`objectA` is `relation` `objectB`."
**All** provided object names **MUST** be included **as is**.
Do **NOT** respond with objects that are not provided.
</objective>

<style>
JSON
</style>

<tone>
Creative and imaginative while trying your best to maintain realism and physical plausibility.
However, you **MUST** strictly adhere to the user's requirements, and thus realism can be broken if the user requires so.
</tone>

<audience>
A demanding professional scene designer who validates and checks your output.
</audience>

<response>
{output_guidance}

<structure>
{{
  "relations": [
    ["<<USE_PROVIDED_OBJECT_NAME>>", "<<FILL_IN_RELATION>>", "<<USE_PROVIDED_OBJECT_NAME>>"],
    ...
  ]
}}
</structure>
</response>

<inputs>
<prompt>
{prompt}
</prompt>

<objects>
{objects}
</objects>
</inputs>"""
