# -*- coding: utf-8 -*-

REGION_CORRECTIONS_TEMPLATE = """<context>
The details of an {scene_type} region (i.e., {region_type}) named "{region_name}" are provided in <<inputs.region>>.
<<inputs.objects>> shows objects that are currently placed in the region.
Also, in this system, a constraint is constructed based on <<dsl>> where it begins with an assertive function under <<dsl.constraints>>, and the parameters of that function are filled with real numbers, strings, and/or supportive functions under <<dsl.operations>>.
</context>

<objective>
You are given a number of unsatisfied constraints in <<inputs.unsatisfied_constraints>>.
Your task is to 
(1) identify one or more objects that require corrections in their position and/or rotation and 
(2) compute a new optimal position and/or rotation for each of the target objects such that the constraint is satisfied.
Unless otherwise specified, each object **MUST** be placed within the region.
Ensure **NO* objects block the connections (eg. do not place objects in front of doors)
Moreover, unless otherwise specified, each object **MUST NOT** collide with any other objects --- please check carefully if the updated position and/or rotation yields any collisions and avoid them.
**ONLY** respond with objects that require correction.
Do **NOT** directly use arithmetic expression as your final solution --- compute it before you respond.
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

<unsatisfied_constraints>
{constraints}
</unsatisfied_constraints>
</inputs>"""
