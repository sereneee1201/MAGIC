# -*- coding: utf-8 -*-

ROOMS_ADJUSTMENT_TEMPLATE = """<context>
All rooms inside an indoor scene are described in <<inputs.rooms>>.
Since the four walls of each room will be extended **outward** by a thickness of {wall_thickness} meter, the axis-aligned bounding box of each room **MUST** be horizontally (x-axis) and/or vertically (y-axis) shifted accordingly such that the minimum distance between two rooms without thickness is {connection_thickness} meter (or 0 (i.e., barely touching) if thickness is taken into account).
</context>

<objective>
For each room, determine a suitable pair of shifts [shift_x, shift_y].
Also, provide a comprehensive and thorough reasoning on your decision.
**All** provided room names **MUST** be included **as is**.
It is very important that after shifting, a room **MUST NOT** collide with any other room.
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
  "<<USE_PROVIDED_ROOM_NAME>>": {{"reasoning": "<<FILL_IN>>", "shifts": [<<FILL_IN_SHIFT_X>>, <<FILL_IN_SHIFT_Y>>]}},
  ...
}}
</structure>
</response>

<inputs>
<rooms>
{rooms}
</rooms>
</inputs>"""
