# -*- coding: utf-8 -*-

from typing import Annotated, Any, ParamSpec, TypeVar

import numpy as np
from PIL import Image
from pydantic import StringConstraints

T = TypeVar("T")
P = ParamSpec("P")
R = TypeVar("R")
ElapsedTime = str
SDict = dict[str, T]
JsonObject = Any
YamlObject = Any
PathLike = str
Url = str
ImgLike = Image.Image | np.ndarray | Url | PathLike

NonEmptyStr = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
