# -*- coding: utf-8 -*-

from typing import Callable

from magic.generation.dsl.constraints import ConstraintDsl
from magic.generation.dsl.operations import OperationDsl
from magic.generation.dsl.parser import ArgType, FunctionCall, parse_function
from magic.utils.misc import colored_error, format_error, tsprint


def is_constraint_satisfied(ast_or_cstr: FunctionCall | str, cstr_dsl: ConstraintDsl, oper_dsl: OperationDsl) -> bool:
    def process_arg(arg: FunctionCall | ArgType):
        if isinstance(arg, FunctionCall):
            supportive = getattr(oper_dsl, arg.name, None)
            if not isinstance(supportive, Callable):
                raise ValueError(f"Unknown supportive function: {arg.name}")
            return supportive(*[process_arg(a) for a in arg.args])
        return arg

    ast = parse_function(ast_or_cstr) if isinstance(ast_or_cstr, str) else ast_or_cstr
    assertive = getattr(cstr_dsl, ast.name, None)
    if not isinstance(assertive, Callable):
        raise ValueError(f"Unknown assertive function: {ast.name}")
    try:
        is_satisfied = assertive(*[process_arg(arg) for arg in ast.args])
    except (TypeError, ValueError) as e:
        tsprint(colored_error(), f"Failed to validate solution for constraint {ast.model_dump()}:", format_error(e)[0])
        is_satisfied = False
    if not isinstance(is_satisfied, bool):
        raise RuntimeError(f"Assertive function '{ast.name}' returned a non-bool value: {is_satisfied}")
    return is_satisfied
