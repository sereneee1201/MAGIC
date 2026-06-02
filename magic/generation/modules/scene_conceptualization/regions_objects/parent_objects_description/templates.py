# -*- coding: utf-8 -*-

REGION_PARENT_OBJECTS_DESCRIPTION_TEMPLATE = """<context>
A user prompt <<inputs.prompt>> describing an {scene_type} region (i.e., {region_type}) named "{region_name}" is provided.
This region consists of objects listed in <<inputs.objects>>.
</context>

<objective>
Based on the provided user prompt, determine the non-empty description (color, material, attributes; "attributes" refers to comma-separated descriptive phrases that are solely about the object's appearance and are independent of other objects) of each object.
A description **MUST** be able to resemble the following sentence: "`color` <<OBJECT_NAME>> made with `material` that is `attributes`."
**All** provided object names **MUST** be included **as is**.
Do **NOT** respond with objects that are not provided.
If you expect several objects to be identical, their descriptions (color + material + attributes) **MUST** also be identical.
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
  "<<USE_PROVIDED_OBJECT_NAME>>": {{
    "color": "<<FILL_IN>>",
    "material": "<<FILL_IN>>",
    "attributes": "<<FILL_IN>>"
  }},
  ...
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
