# -*- coding: utf-8 -*-

CONSTRAINT_VALIDATION_TEMPLATE = """<context>
<<dsl>> shows a domain-specific language (DSL) that is designed to describe any scene, inside which any object has non-zero width, height, and depth.
<<inputs.constraints>> shows a set of constraints (1-based indexing) powered by the DSL.
Each constraint begins with an assertive function under <<dsl.constraints>>, and the parameters of that function are filled with real numbers, strings, and/or supportive functions under <<dsl.operations>>.
</context>

<objective>
{objective}
</objective>

<style>
JSON
</style>

<tone>
Confident, professional, and clear.
</tone>

<audience>
An expert on the DSL who checks your output.
</audience>

<response>
{output_guidance}

<structure>
{structure}
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
<constraints>
{constraints}
</constraints>
</inputs>"""
