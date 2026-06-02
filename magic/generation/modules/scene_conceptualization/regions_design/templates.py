# -*- coding: utf-8 -*-

REGION_DESIGN_TEMPLATE = """<context>
A user prompt <<inputs.prompt>> describing an {scene_type} region (i.e., {region_type}) named "{region_name}" is provided.
</context>

<objective>
{objective}
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
{structure}
</structure>
</response>

<inputs>
<prompt>
{prompt}
</prompt>
</inputs>"""
