# -*- coding: utf-8 -*-

REGION_DRAFT_TEMPLATE = """<context>
Inside an {scene_type} scene, one region (i.e., {region_type}) named "{region_name}" is described in <<inputs.region>>.
The doors are shown in <<inputs.connections>> and must be kept open and unblocked.
The portals are shown in <<inputs.objects>> with the attribute "is_portal" set to true and must also be kept open and unblocked.
The details of objects that are needed to be placed in the region are provided in <<inputs.objects>>.
Moreover, <<inputs.constraints>> shows a set of positional and rotational constraints (each one is constructed based on <<dsl>> where each syntactically correct constraint begins with an assertive function under <<dsl.constraints>> and the parameters of that function are filled with real numbers, strings, and/or supportive functions under <<dsl.operations>>) that the objects must satisfy when placed in the region.
</context>

<objective>
**All** objects in <<inputs.objects>> MUST appear exactly as named. No object may be omitted, renamed, or merged.
For every object, "position" MUST be exactly [x, y, z] and "rotation" MUST be exactly [rx, ry, rz]
Compute the **optimal** center position (in world space) and rotation (in object space) of **all** objects in <<inputs.objects>> so that **all** constraints in <<inputs.constraints>> are satisfied.
Unless otherwise specified, each object **MUST** be placed within the region and **MUST NOT** collide with any other objects.
**ALL** objects must be placed so that there is a path from the portals and doors to any point in the region without colliding with any objects.
**ALL** provided object names **MUST** be included as-is.
**ALL** wall objects must be placed against a wall without partitioning the region.
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

<structure>
{{
  "reasoning": "<<FILL_IN>>",
  "objects": {{
    "<<USE_PROVIDED_OBJECT_NAME>>": {{
      "position": [<<FILL_IN_OPTIMAL_POSITION_X>>, <<FILL_IN_OPTIMAL_POSITION_Y>>, <<FILL_IN_OPTIMAL_POSITION_Z>>],
      "rotation": [<<FILL_IN_OPTIMAL_ROTATION_X>>, <<FILL_IN_OPTIMAL_ROTATION_Y>>, <<FILL_IN_OPTIMAL_ROTATION_Z>>]
    }},
    ...
  }}
}}
</structure>
</response>

<dsl>
<constraints>
{constraint_dsl}
</constraints>

<operations>
{operation_dsl}
</operations>
</dsl>

<inputs>
<region>
{region}
</region>

<objects>
{objects}
</objects>

<constraints>
{constraints}
</constraints>
</inputs>"""
