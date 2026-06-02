# -*- coding: utf-8 -*-

from typing import Literal, Optional

from magic.generation import MagicConfig, Region
from magic.generation.dsl.parser import FunctionCall, parse_function
from magic.generation.modules import OUTPUT_GUIDANCE
from magic.generation.modules.scene_conceptualization.constraints.validation.templates import (
    CONSTRAINT_VALIDATION_TEMPLATE,
)
from magic.utils.dtypes import JsonObject, SDict
from magic.utils.llm import Llm, LlmContent, TemplateFormatter
from magic.utils.retry import auto_retry


def check_constraint(
    constraint: str,
    region: Region,
    cstr_dsl_signature: SDict[tuple[list[type | str], None]],
    oper_dsl_signature: SDict[tuple[list[type | str], type | str]],
) -> bool:
    def validate_constraint(ast: FunctionCall, is_outermost=True) -> Optional[type | str]:
        func, args = ast.name, ast.args
        signature = cstr_dsl_signature if is_outermost else oper_dsl_signature
        if func not in signature:
            raise ValueError(f"{'Assertive' if is_outermost else 'Supportive'} function '{func}' does not exist")
        arg_types, ret_type = signature[func]
        if len(args) != len(arg_types):
            raise ValueError(f"{func} expects {len(arg_types)} arguments, got {len(args)}")
        if not is_outermost and ret_type is None:
            raise ValueError(f"Supportive function '{func}' should return a value, but it does not")
        for i, (arg, expected_type) in enumerate(zip(args, arg_types)):
            result_type = validate_constraint(arg, is_outermost=False) if isinstance(arg, FunctionCall) else type(arg)
            if result_type != expected_type:
                raise ValueError(f"Argument {i+1} of '{func}' should be {expected_type}, got {result_type}")
            if result_type == str and arg not in region.objects:
                raise ValueError(f"Object '{arg}' does not exist in region '{region.name}'")
        return ret_type

    for c in ("+", "-", "*", "/", "=", "<", ">"):
        if c in constraint:
            return False
    try:
        ast = parse_function(constraint)
    except ValueError:
        return False
    try:
        if validate_constraint(ast) is not None:
            raise ValueError("Assertive function should return None")
    except ValueError:
        return False
    return True


get_constraint_validation_prompt = TemplateFormatter(
    CONSTRAINT_VALIDATION_TEMPLATE,
    objective=None,
    output_guidance=OUTPUT_GUIDANCE,
    structure=None,
    constraint_dsl=None,
    operation_dsl=None,
    constraints=None,
)


def _get_constraint_validation_objective(problem: Literal["nonsensical", "redundant", "contradicted"]) -> str:
    match problem:
        case "nonsensical":
            objective = """\
Analyze the constraints in <<inputs.constraints>> and determine if there are nonsensical constraints.
A constraint is considered nonsensical if it is physically possible to be satisfied, but it does not make any sense (or is completely useless) in the context of the scene.
For example, `mustEqualTo(getObjectMinPositionX('obj1'), getRegionMaxPositionX())` is a nonsensical constraint because having the minimum X coordinate of 'obj1' equal to the maximum X coordinate of the region implies that 'obj1' is placed outside the region, which is not a valid position for any object and thus making no sense.
If a constraint is considered nonsensical, append its index to the "problems" list, together with a comprehensive and thorough reasoning on your decision."""
        case "redundant":
            objective = """\
Analyze the constraints in <<inputs.constraints>> and determine if there are redundant subsets.
A set of constraints is considered redundant if they share the same physical requirement for the same set of objects.
In other words, keeping only one constraint in this set while removing others will **NOT** change the overall physical meaning of the scene.
For example, `mustLessThan(getObjectMaxPositionX('obj1'), getObjectMinPositionX('obj2'))` and `mustGreaterThan(getObjectMinPositionX('obj2'), getObjectMaxPositionX('obj1'))` constitute a redundant set of constraints, because they share the same physical requirement that 'obj1' must be placed to the left of 'obj2'.
If a set of constraints is considered redundant, append their indexes to the "problems" list, together with a comprehensive and thorough reasoning on your decision."""
        case "contradicted":
            objective = """\
Analyze the constraints in <<inputs.constraints>> and determine if there are contradictory subsets.
A set of constraints is considered contradictory if it is **physically impossible** to satisfy all of them simultaneously.
In other words, satisfying one constraint in this set implies that other constraints in the same set can **never** be satisfied.
For example, `mustLessThan(getObjectMaxPositionX('obj1'), getObjectMinPositionX('obj2'))` and `mustLessThan(getObjectMaxPositionX('obj2'), getObjectMinPositionX('obj1'))` constitute a contradictory set of constraints, because if 'obj1' is placed to the left of 'obj2', then 'obj2' can never be placed to the left of 'obj1'.
If a set of constraints is considered contradictory, append their indexes to the "problems" list, together with a comprehensive and thorough reasoning on your decision."""
        case _:
            raise ValueError(f'Invalid problem "{problem}"')
    return objective


def _get_constraint_validation_structure(problem: Literal["nonsensical", "redundant", "contradicted"]) -> str:
    if problem == "nonsensical":
        structure = f"""\
{{
  "problems": [
    {{"reasoning": "<<FILL_IN>>", "index": <<FILL_IN>>}},
    ...
  ]
}}"""
    elif problem in {"redundant", "contradicted"}:
        structure = f"""\
{{
  "problems": [
    {{"reasoning": "<<FILL_IN>>", "indexes": [<<FILL_IN>>, ...]}},
    ...
  ]
}}"""
    else:
        raise ValueError(f'Invalid problem "{problem}"')
    return structure


@auto_retry
def modify_constraints(
    config: MagicConfig,
    llm: Llm,
    cstr_dsl: str,
    oper_dsl: str,
    constraints: list[str],
    problem: Literal["nonsensical", "redundant", "contradicted"],
) -> tuple[JsonObject, LlmContent]:
    llm.clear_messages()
    prompt = get_constraint_validation_prompt(
        objective=_get_constraint_validation_objective(problem),
        structure=_get_constraint_validation_structure(problem),
        constraint_dsl=cstr_dsl,
        operation_dsl=oper_dsl,
        constraints="\n".join(f"{i} - {c}" for i, c in enumerate(constraints, start=1)),
    )
    response, llm_output = llm.chat(prompt, temperature=config.temperature, to_json=True)
    if not isinstance(response, dict):
        raise RuntimeError()
    if "problems" not in response:
        raise RuntimeError()
    if not isinstance(response["problems"], list):
        raise RuntimeError()
    for group in response["problems"]:
        if not isinstance(group, dict):
            raise RuntimeError()
        if "reasoning" not in group:
            raise RuntimeError()
        if not isinstance(group["reasoning"], str):
            raise RuntimeError()
        if problem == "nonsensical":
            if "index" not in group:
                raise RuntimeError()
            if not (group["index"] is None or isinstance(group["index"], int)):
                raise RuntimeError()
        elif problem in {"redundant", "contradicted"}:
            if "indexes" not in group:
                raise RuntimeError()
            if not isinstance(group["indexes"], list):
                raise RuntimeError()
            if not all(isinstance(i, int) for i in group["indexes"]):
                raise RuntimeError()
    return response, llm_output.content
