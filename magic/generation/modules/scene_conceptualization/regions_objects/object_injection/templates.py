# -*- coding: utf-8 -*-

REGION_OBJECT_INJECTION_PROMPT = """<context>
A user prompt <<inputs.prompt>> describing an {scene_type} region (i.e., {region_type}) named "{region_name}" is provided.
However, the prompt is not comprehensive enough to be used directly for scene generation.
Therefore, new content has to be generated and injected to expand and upsample the prompt.
</context>

<objective>
Based on the provided user prompt, creatively expand it into **one** longer, more comprehensive, and more detailed paragraph by injecting:
- numerous new objects that are relevant to the {region_type};
- appearance and description of each new object;
- object-object relations (i.e., how objects relate to each other); and
- object-region relations (i.e., how objects relate to the {region_type}).
Objects that are mentioned in the original prompt **MUST** be included.
If an object is described as a portal, you **MUST** preserve the object as "portal <object>" **UNLESS** it is a door or window.
Do **NOT** include any portal doors or portal windows.
Do **NOT** include any objects that might split the region into multiple areas. (eg. walls)
</objective>

<style>
JSON
</style>

<tone>
Creative and imaginative while strictly adhering to the user's requirements.
</tone>

<audience>
A demanding professional scene designer who checks your output.
</audience>

<response>
{output_guidance}

<structure>
{{"expansion": "<<FILL_IN>>"}}
</structure>
</response>

<inputs>
<prompt>
{prompt}
</prompt>
</inputs>"""
