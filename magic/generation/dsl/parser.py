# -*- coding: utf-8 -*-

from __future__ import annotations

import re

from pydantic import BaseModel

ArgType = int | float | str | bool


class FunctionCall(BaseModel, strict=True):
    name: str
    args: list[FunctionCall | ArgType]


def _check_parentheses(expr: str) -> bool:
    count = 0
    in_single = False
    in_double = False
    escaped = False
    for c in expr:
        if escaped:
            escaped = False
            continue
        if c == "\\":
            escaped = True
            continue
        if c == "'" and not in_double:
            in_single = not in_single
            continue
        if c == '"' and not in_single:
            in_double = not in_double
            continue
        if in_single or in_double:
            continue
        if c == "(":
            count += 1
        elif c == ")":
            count -= 1
            if count < 0:
                return False
    return count == 0


def _parse_arg(arg: str) -> ArgType:
    if (arg.startswith('"') and arg.endswith('"')) or (arg.startswith("'") and arg.endswith("'")):
        return arg[1:-1]  # remove quotes
    match arg.lower():
        case "true":
            return True
        case "false":
            return False
    try:
        return float(arg)
    except ValueError:
        return arg


def _parse_args(string: str) -> list[FunctionCall | ArgType]:
    args = []
    current = ""
    depth = 0
    for i in range(len(string)):
        c = string[i]
        if c == "(":
            current += c
            depth += 1
        elif c == ")":
            if depth == 0:
                if (cur := current.strip()) != "":
                    args.append(_parse_func_or_arg(cur))
                return args
            else:
                current += c
                depth -= 1
        elif c == "," and depth == 0:
            if (cur := current.strip()) != "":
                args.append(_parse_func_or_arg(cur))
            current = ""
        else:
            current += c
    return args


def _parse_func_or_arg(expr: str) -> FunctionCall | ArgType:
    expr = expr.strip()
    if "(" not in expr:
        return _parse_arg(expr)  # return as is if `expr` is just a variable or constant
    result = re.match(r"([a-zA-Z_][a-zA-Z0-9_]*)\s*\(", expr)
    if result is None:
        raise ValueError(f"Invalid function call: {expr}")
    return FunctionCall(name=result.group(1), args=_parse_args(expr[result.end() :]))


def parse_function(expr: str) -> FunctionCall:
    if "(" not in expr:
        raise ValueError(f"Expected a function call, got: {expr}")
    if not _check_parentheses(expr):
        raise ValueError(f"Unmatched parentheses in expression: {expr}")
    ast = _parse_func_or_arg(expr)
    assert isinstance(ast, FunctionCall)
    return ast
