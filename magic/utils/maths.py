# -*- coding: utf-8 -*-

from typing import Iterable

import numpy as np


def clamp(num: float, a: float, b: float) -> float:
    return max(a, min(num, b))


def sigmoid(x: np.floating) -> np.floating:
    return 1 / (1 + np.exp(-x))


def get_scale(orig_dims: Iterable[float], new_dims: Iterable[float], preserve_ratio: bool = True) -> list[float]:
    orig_dims: np.ndarray = np.array(orig_dims)
    new_dims: np.ndarray = np.array(new_dims)
    if (os := orig_dims.shape) != (ns := new_dims.shape):
        raise ValueError(f"Shapes of `orig_dims` and `new_dims` must be equal, got {os} and {ns} respectively")
    scales = new_dims / orig_dims
    if preserve_ratio:
        scales.fill(scales.min())
    return scales.tolist()
