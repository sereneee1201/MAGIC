# -*- coding: utf-8 -*-

REGION_PARENT_OBJECTS_DIMENSIONS_TEMPLATE = """<context>
A user prompt <<inputs.prompt>> describing an {scene_type} region (i.e., {region_type}) named "{region_name}" is provided.
This region consists of objects listed in <<inputs.objects>>.
</context>

<objective>
For each object, generate a 3-tuple [width, height, depth] to represent the reasonable dimensions of the object.
**All** provided object names **MUST** be included **as is**.
Do **NOT** respond with objects that are not provided.
Do **NOT** generate zero for any dimension.
If you expect several objects to be identical, their dimensions **MUST** also be identical.
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
{{"<<USE_PROVIDED_OBJECT_NAME>>": [<<FILL_IN_WIDTH>>, <<FILL_IN_HEIGHT>>, <<FILL_IN_DEPTH>>], ...}}
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
