# -*- coding: utf-8 -*-

INDOOR_CONNECTIONS_TEMPLATE = """<context>
A user prompt <<inputs.prompt>> describing an {scene_type} scene is provided.
Names of all regions (i.e., {region_type}s) are provided in <<inputs.regions>>.
Note that "__outside__" is {outside_def}.
All doors connected to outdoor (i.e., "__outside__") are listed in {doors}.
All neighbor pairs among regions are described in <<inputs.neighbors>>.
A pair of neighbors is defined as two regions that **MUST** be adjacent to each other
(but adjacency does **NOT** imply that a door or window exists).
From previous generation, we have this error: "{error}". (Empty string if no error.)
These connections **MUST** be included: {doors}, {p_windows}.
</context>

<objective>
According to the prompt, extract: 
(1) **only** pairs of neighbor regions that the user prompt explicitly states are connected by a door.
(2) **only** pairs of neighbor regions that the user prompt explicitly states are connected by a window.  
**ONLY** connections listed in {doors} can connect to "__outside__".

Rules:
- A connection is valid **only if** the user explicitly uses the word "door" or "window" in the prompt
  OR if the connection should be placed **ON THE WALL** logically.  
- There might **NOT** be any doors or windows in the scene — do **NOT** hallucinate any if unspecified.  
- If multiple doors connect the same pair of regions, list multiple connections.  
- **All** provided region names **MUST** be included **as is**.  
- The same pair of regions can appear multiple times if required in the user prompt.
- Double check that the number of connections between any region and ""__outside__" is equal to the number of doors in {doors}.
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
  "doors": [
    {{"region_a": "<<USE_PROVIDED_REGION_NAME>>", "region_b": "<<USE_PROVIDED_REGION_NAME>>"}},
    ...
  ],
  "windows": [
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

<neighbors>
{neighbors}
</neighbors>
</inputs>"""

INDOOR_CONNECTIONS_CATEGORY_TEMPLATE = """<context>
A user prompt <<inputs.prompt>> describing an {scene_type} scene is provided.
The connections between pairs of regions (i.e., {region_type}s) are shown in <<inputs.connections>>.
Note that "__outside__" is {outside_def}.
Note that {error}.
</context>

<objective>
Based on the provided information, for each connection, determine the category of the object that will be used to realize the connection.
The category should be a short phrase.
**All** provided connection names **MUST** be included **as is**.
Based on the prompt "<<inputs.prompt>>", also determine whether each connection is a portal.
The connection is a potal only if it is **EXPLICITLY** stated in the prompt to be a portal (e.g. "portal window")
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
  "doors": {{"<<USE_PROVIDED_DOOR_NAME>>": {{"category": "<<FILL_IN_DOOR_CATEGORY>>", "is_portal": True/False}}, ...}},
  "windows": {{"<<USE_PROVIDED_WINDOW_NAME>>": {{"category": "<<FILL_IN_DOOR_CATEGORY>>", "is_portal": True/False}}, ...}}
}}
</structure>
</response>

<inputs>
<prompt>
{prompt}
</prompt>

<connections>
<doors>
{doors}
</doors>

<windows>
{windows}
</windows>
</connections>
</inputs>"""

INDOOR_CONNECTIONS_DESCRIPTION_TEMPLATE = """<context>
A user prompt <<inputs.prompt>> describing an {scene_type} scene is provided.
The connections between pairs of regions (i.e., {region_type}s) are shown in <<inputs.connections>>.
Note that "__outside__" is {outside_def}.
</context>

<objective>
Based on the provided information, for each connection, determine the non-empty description (color, material, attributes; "attributes" refers to comma-separated descriptive phrases that are solely about the object's appearance and are independent of other objects) of the connection object being used.
A description **MUST** be able to resemble the following sentence: "`color` <<CONNECTION_CATEGORY>> made with `material` that is `attributes`."
**All** provided connection names **MUST** be included **as is**.
Doors may have different descriptions even if they connect the same pair of regions.
If you expect several doors to be identical, their descriptions (color + material + attributes) **MUST** also be identical.
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
  "doors": {{
    "<<USE_PROVIDED_DOOR_NAME>>": {{
      "color": "<<FILL_IN>>",
      "material": "<<FILL_IN>>",
      "attributes": "<<FILL_IN>>"
    }},
    ...
  }},
  "windows": {{
    "<<USE_PROVIDED_WINDOW_NAME>>": {{
      "color": "<<FILL_IN>>",
      "material": "<<FILL_IN>>",
      "attributes": "<<FILL_IN>>"
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

<connections>
<doors>
{doors}
</doors>

<windows>
{windows}
</windows>
</connections>
</inputs>"""

INDOOR_CONNECTIONS_DIMENSIONS_TEMPLATE = """<context>
A user prompt <<inputs.prompt>> describing an {scene_type} scene is provided.
The connections between pairs of regions (i.e., {region_type}s) are shown in <<inputs.connections>>.
Note that "__outside__" is {outside_def}.
</context>

<objective>
Based on the provided information, for each connection, generate a 2-tuple [width, height] to represent the dimensions of the connection object being used.
**All** provided connection names **MUST** be included **as is**.
Do **NOT** generate zero for any dimension.
If you expect several doors to be identical, their dimensions **MUST** also be identical.
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
  "doors": {{"<<USE_PROVIDED_DOOR_NAME>>": [<<FILL_IN_WIDTH>>, <<FILL_IN_HEIGHT>>], ...}},
  "windows": {{"<<USE_PROVIDED_WINDOW_NAME>>": [<<FILL_IN_WIDTH>>, <<FILL_IN_HEIGHT>>], ...}}
}}
</structure>
</response>

<inputs>
<prompt>
{prompt}
</prompt>

<connections>
<doors>
{doors}
</doors>

<windows>
{windows}
</windows>
</connections>
</inputs>"""
