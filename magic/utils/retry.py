# -*- coding: utf-8 -*-

import time
from typing import Any, Callable

from magic.utils.dtypes import P, R
from magic.utils.misc import colored_error, format_error, tsprint

_max_retries = 10


def set_max_retries(max_retries: int) -> None:
    if not isinstance(max_retries, int) or max_retries < 0:
        raise ValueError("`max_retries` must be a non-negative integer.")
    global _max_retries
    _max_retries = max_retries


def get_max_retries() -> int:
    return _max_retries


def auto_retry(func: Callable[P, R], delay: float = 10.0) -> Callable[P, R]:
    max_retries = get_max_retries()

    def inner(*args: Any, **kwargs: Any) -> R:
        for r in range(max_retries + 1):
            try:
                return func(*args, **kwargs)
            except KeyboardInterrupt:
                raise
            except BaseException as e:
                if r == max_retries:
                    raise
                err = "\n|\nv\n".join(format_error(e))
                tsprint(colored_error(), f"Auto-retrying {func.__name__}:", err, end="\n\n")
                time.sleep(delay)
                continue

    return inner
