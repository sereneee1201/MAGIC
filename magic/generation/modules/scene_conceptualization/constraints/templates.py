# -*- coding: utf-8 -*-

REGION_CONSTRAINTS_TEMPLATE = """<context>
The details of an {scene_type} region (i.e., {region_type}) named "{region_name}" are provided in <<inputs.region>>.
In <<inputs.region>> under "object_relations", each 3-tuple [objectA, relation, objectB] encodes how `objectA` is physically related to `objectB` according to `relation`.
</context>

<objective>
{objective}
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

When filling in ObjectName in the DSL, you **MUST** enclose the string with single quotation marks.

<structure>
{{
  "reasoning": "<<FILL_IN>>",
  "constraints": {{
    "positional": ["<<FILL_IN_POSITIONAL_CONSTRAINT>>", ...],
    "rotational": ["<<FILL_IN_ROTATIONAL_CONSTRAINT>>", ...]
  }}
}}
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
<region>
{region}
</region>
</inputs>"""
