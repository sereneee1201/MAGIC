# -*- coding: utf-8 -*-

SCENE_TYPE_TEMPLATE = """<context>
A user prompt <<inputs.prompt>> describing a scene is provided.
The prompt has to be processed to extract useful information about the scene.
One of the key pieces of information is the scene type.
</context>

<objective>
Analyze the content in the prompt and accurately classify the scene into either "indoor" or "outdoor".
Also, provide a comprehensive and thorough reasoning on your answer.
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
{{"reasoning": "<<FILL_IN>>", "scene_type": "indoor/outdoor"}}
</structure>
</response>

<examples>
Prompt: A child's playroom filled with colorful toys and a small tent
Answer: indoor

Prompt: A serene beach with a lifeguard tower and a volleyball court
Answer: outdoor

Prompt: A two-room library with a study area and a collection of rare books
Answer: indoor

Prompt: A city park with a playground and a pond with ducks
Answer: outdoor
</examples>

<inputs>
<prompt>
{prompt}
</prompt>
</inputs>"""
