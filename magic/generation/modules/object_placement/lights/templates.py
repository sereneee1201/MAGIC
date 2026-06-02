# -*- coding: utf-8 -*-

REGION_LIGHTS_TEMPLATE = """<context>
The details of an {scene_type} region (i.e., {region_type}) named "{region_name}" are provided in <<inputs.region>>.
In <<inputs.region>> under "objects", the "position" (x, y, z) associated with each object represents the center of the object's oriented bounding box.
</context>

<objective>
For each lighting unit (i.e., object made for illumination) under "objects" in <<inputs.region>>, generate the position in world space of a light source that matches the light-emitting component of the object.
If there are no lighting units, return an empty list.
Also, provide a comprehensive and thorough reasoning on your decisions.
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

Round off decimal numbers to six decimal places.

<structure>
{{"reasoning": "<<FILL_IN>>", "lights": [[<<FILL_IN_X>>, <<FILL_IN_Y>>, <<FILL_IN_Z>>], ...]}}
</structure>
</response>

<inputs>
<region>
{region}
</region>
</inputs>"""
