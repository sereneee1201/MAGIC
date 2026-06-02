# -*- coding: utf-8 -*-

REGIONS_EXTRACTION_PROMPT = """<context>
A user prompt <<inputs.prompt>> describing an {scene_type} scene is provided.
The scene consists of one or more {region_type}s.
</context>

<objective>
Based **ONLY** on the provided user prompt, determine the set of region (i.e. {region_type}) names.
The names **MUST** be clear, semantically meaningful, and unique.
The names should be short nouns (e.g., "living room", "kitchen", "bathroom", "hallway", "corridor", "dining area", "bedroom", "office nook", etc.).
Do **NOT** include excess descriptions or adjectives such as "portal" in the names.
You **MUST NOT** hallucinate and **MUST NOT** include {region_type}s that are not mentioned in the original prompt.
If the user prompt specifies the portals, you must preserve this information. You **MUST** preserving "portal <object>" in the descriptions if mentioned.
</objective>

<style>
JSON
</style>

<tone>
Confident, professional, and clear.
</tone>

<audience>
A demanding professional scene designer who validates and checks your output.
</audience>

<response>
{output_guidance}

<structure>
{{"regions": ["<<FILL_IN_REGION_NAME>>", ...]}}
</structure>
</response>

<inputs>
<prompt>
{prompt}
</prompt>
</inputs>"""
