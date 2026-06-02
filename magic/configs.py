# -*- coding: utf-8 -*-

from typing import Annotated

from pydantic import BaseModel, DirectoryPath, Field

from magic.constants import DATASET_DIR


class DatasetConfig(BaseModel, validate_assignment=True, strict=True):
    temperature: Annotated[float, Field(ge=0.0, le=2.0)] = 0.5
    n_prompts: Annotated[int, Field(ge=1)] = 20
    max_retries: Annotated[int, Field(ge=0)] = 5
    max_threads: Annotated[int, Field(ge=1)] = 2
    max_object_number: Annotated[int, Field(ge=1)] = 10
    parent_dir: DirectoryPath = DATASET_DIR
    verbose: bool = True
