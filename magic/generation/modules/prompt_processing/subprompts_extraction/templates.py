# -*- coding: utf-8 -*-

SUBPROMPTS_EXTRACTION_PROMPT = """<context>
A user prompt <<inputs.prompt>> describing an {scene_type} scene is provided.
The scene consists of one or more {region_type}s.
</context>

<objective>
Based **ONLY** on the provided user prompt, for each region (i.e., {region_type}), extract sentences (and put them in one paragraph, i.e., one string) from the prompt that are **ONLY** related to that region.
Sentences **MUST** be extracted **as is** from the prompt, without any modifications.
Region names are provided in <<structure>> under the "regions" key.
**All** provided region names **MUST** be included **as is**.
You **MUST NOT** hallucinate and **MUST NOT** generate any new {region_type}s.
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
The output **MUST** have the following structure including the "regions" key.
<structure>
{structure}
</structure>
</response>

<inputs>
<prompt>
{prompt}
</prompt>
</inputs>"""
