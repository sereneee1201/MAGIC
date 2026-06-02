# -*- coding: utf-8 -*-

INDOOR_CONNECTIONS_PLACEMENT_TEMPLATE = """<context>
A user prompt <<inputs.prompt>> describing an indoor scene is provided.
The positions of all regions (i.e., rooms) are shown in <<inputs.regions>>.
The connections between pairs of regions are shown in <<inputs.connections>>, in which keys "region_a" and "region_b" together indicate the two regions that a connection object connects.
</context>

<objective>
For each connection, generate its center [x, y] on a two-dimensional Cartesian coordinate plane.
If the connection object is a window, further generate its height above the floor (from the floor to the bottom of the window).
**All** provided connection names **MUST** be included **as is**.
A connection object (no matter it is a door or window) **MUST NOT** collide with any other connection objects.
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
  "doors": {{
    "<<USE_PROVIDED_DOOR_NAME>>": {{
      "center": [<<FILL_IN_X>>, <<FILL_IN_Y>>]
    }},
    ...
  }},
  "windows": {{
    "<<USE_PROVIDED_WINDOW_NAME>>": {{
      "center": [<<FILL_IN_X>>, <<FILL_IN_Y>>],
      "height_above_floor": <<FILL_IN>>
    }},
    ...
  }}
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

<connections>
<doors>
{doors}
</doors>

<windows>
{windows}
</windows>
</connections>
</inputs>"""
