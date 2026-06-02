# -*- coding: utf-8 -*-

import ast
import os
import random
import re
import sys
import time
from collections.abc import Callable
from typing import Any, Optional

import numpy as np
import torch
from tqdm import tqdm

from magic.utils.dtypes import ElapsedTime, P, R, SDict


def tsprint(*values: object, sep: Optional[str] = " ", end: Optional[str] = "\n") -> None:
    with tqdm.external_write_mode(nolock=False):
        sys.stdout.write(sep.join(map(str, values)))
        sys.stdout.write(end)
        sys.stdout.flush()


def format_elapsed_time(time_elapsed: float) -> ElapsedTime:
    from math import floor

    if time_elapsed < 0:
        raise ValueError(f"`time_elapsed` must not be less than 0, got {time_elapsed}")
    d = int(time_elapsed // 86400)
    time_elapsed -= d * 86400
    h = int(time_elapsed // 3600)
    time_elapsed -= h * 3600
    m = int(time_elapsed // 60)
    time_elapsed -= m * 60
    s = floor(time_elapsed)
    time_elapsed -= s
    ms = f"{time_elapsed:.3f}".split(".")[1]
    return f"{f'{d}:' if d > 0 else ''}{h:02d}:{m:02d}:{s:02d}.{ms}"


class Timer(object):
    def __init__(self) -> None:
        self.__start_time: Optional[float] = None

    def __enter__(self) -> "Timer":
        self.__start_time = time.perf_counter()
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        self.__start_time = None

    def get(self) -> float:
        return time.perf_counter() - self.__start_time

    @staticmethod
    def decorator(func: Callable[P, R]) -> Callable[P, tuple[R, float]]:
        from functools import wraps
        from typing import Any, cast

        @wraps(func)
        def inner(*args: Any, **kwargs: Any) -> tuple[R, float]:
            start_time = time.perf_counter()
            returned = func(*args, **kwargs)
            end_time = time.perf_counter()
            return returned, end_time - start_time

        return cast(Callable[P, tuple[R, float]], inner)


def get_datetime(format: str = r"%Y%m%d-%H%M%S") -> str:
    from datetime import datetime

    return datetime.now().strftime(format)


def format_error(error: BaseException) -> tuple[str, str]:
    import traceback

    return f"{error.__class__.__module__}.{error.__class__.__name__}: {str(error)}", traceback.format_exc()


def colored_error() -> str:
    from termcolor import colored

    return colored(f"[ERROR@{get_datetime()}]", color="red", attrs=["bold"])


def generate_random_hash(max_length: Optional[int] = None) -> str:
    import hashlib

    return hashlib.sha3_256(os.urandom(256)).hexdigest()[:max_length]


def bytes_to_base64(b: bytes) -> str:
    import base64

    return base64.b64encode(b).decode("utf-8")


def remove_trailing_digits(text: str) -> str:
    return re.sub(r"(_*\d+)+$", "", text.strip())


def replace_non_alphanumeric(text: str, new: str = "_") -> str:
    return re.sub(r"[^a-zA-Z0-9]", new, text.strip())


def parse_cli_kwargs(kwargs: Optional[list[str]]) -> SDict[Any]:
    output = {}
    if kwargs is not None:
        for kwarg in kwargs:
            key, value = kwarg.split("=", maxsplit=1)
            key, value = key.strip(), value.strip()
            try:
                value = ast.literal_eval(value)
            except (ValueError, SyntaxError):
                if value == "True":
                    value = True
                elif value == "False":
                    value = False
                elif value == "None":
                    value = None
                else:
                    value = value.strip("'\"")
            output[key] = value
    return output


def is_cuda(device: str) -> bool:
    return device.lower().startswith("cuda")


def has_cuda() -> bool:
    return torch.cuda.is_available()


def get_device() -> tuple[str, Optional[str]]:
    if torch.backends.mps.is_available() and torch.backends.mps.is_built():
        return "mps", None
    if has_cuda():
        return "cuda", torch.cuda.get_device_name()
    return "cpu", None


def next_available_in_dict(d: SDict[Any], key: str) -> str:
    i = 1
    while (k := f"{key}_{i}") in d:
        i += 1
    return k


def fix_seed(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)
    torch.backends.cudnn.deterministic = True
    torch.backends.cudnn.benchmark = False
