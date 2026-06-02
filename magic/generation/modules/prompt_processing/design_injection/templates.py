# -*- coding: utf-8 -*-

DESIGN_INJECTION_PROMPT = """<context>
A user prompt <<inputs.prompt>> describing an {scene_type} scene is provided.
However, the prompt is not comprehensive enough to be used directly for scene generation.
Therefore, new content has to be generated and injected to expand and upsample the prompt.
</context>

<objective>
Based on the provided user prompt, creatively expand it into **one** longer, more comprehensive, and more detailed paragraph by injecting:
- main theme (including design concepts, color scheme, material choices, patterns and textures, etc.) of the entire space as well as each {region_type};
- design principles (including balance, rhythm, emphasis, contrast, harmony and unity, proportion and scale, etc.) of the entire space as well as each {region_type};
- ambience (i.e., the overall atmosphere or mood) of the entire space as well as each {region_type};
- purpose and functionality of the entire space as well as each {region_type}; and
- flow and circulation (i.e., how people move through the space).
You **MUST** keep objects that are mentioned in the original prompt and the **number** of these objects unchanged.
If the user prompt specifies certain objects as portals (e.g., a wardrobe, mirror, painting), you **MUST** preserve the object as "portal <object>" (with descriptions if specified). 
You **MUST** also ensure that the object descriptions in the original prompt are kept.
Do **NOT** include objects that are not mentioned in the original prompt.
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
