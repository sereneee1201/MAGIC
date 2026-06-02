# -*- coding: utf-8 -*-

from pathlib import Path
from typing import Annotated, Any, Optional

from pydantic import BaseModel, DirectoryPath, Field, FilePath

from magic.constants import DATASET_DIR
from magic.utils.dtypes import NonEmptyStr


class MagicDatasetConfig(BaseModel, validate_assignment=True):
    llm: NonEmptyStr = "normal_llm"
    temperature: Annotated[float, Field(ge=0.0, le=2.0)] = 0.7
    max_n_per_object: Annotated[int, Field(ge=1)] = 5
    n_rooms: Optional[Annotated[int, Field(ge=1)]] = None
    n_prompts: Annotated[int, Field(ge=1)] = 10
    max_retries: Annotated[int, Field(ge=0)] = 10
    max_threads: Annotated[int, Field(ge=1)] = 4
    parent_dir: DirectoryPath = Path(DATASET_DIR)
    verbose: bool = True


class DatapointRoom(BaseModel, validate_assignment=True):
    adjectives: list[NonEmptyStr] = []
    description: Optional[NonEmptyStr] = None
    objects_list: list[NonEmptyStr] = []
    objects_desc: dict[NonEmptyStr, NonEmptyStr] = {}
    object_relations: list[tuple[NonEmptyStr, NonEmptyStr, NonEmptyStr]] = []
    summary: Optional[NonEmptyStr] = None


class DatapointConnection(BaseModel, validate_assignment=True):
    region_a: NonEmptyStr
    region_b: NonEmptyStr
    conn_type: Optional[NonEmptyStr] = None
    description: Optional[NonEmptyStr] = None


class DatapointPrompts(BaseModel, validate_assignment=True):
    full: NonEmptyStr
    humanized: Optional[NonEmptyStr] = None
    sentence: Optional[NonEmptyStr] = None
    pct_change_humanized: Optional[Annotated[float, Field(ge=-1.0, le=1.0)]] = None
    pct_change_sentence: Optional[Annotated[float, Field(ge=-1.0, le=1.0)]] = None


class MagicDatapoint(BaseModel, validate_assignment=True):
    buildings: NonEmptyStr
    config: Optional[MagicDatasetConfig] = None
    log_path: Optional[FilePath] = None
    n_rooms: Annotated[int, Field(ge=1)] = 1
    rooms: dict[NonEmptyStr, DatapointRoom] = {}
    connections: list[DatapointConnection] = []
    summaries: dict[NonEmptyStr, NonEmptyStr] = {}
    prompts: Optional[DatapointPrompts] = None
    conversations: dict[NonEmptyStr, Any] = {}

    def save(self) -> None:
        if self.log_path is None:
            raise RuntimeError(f"`log_path` must not be None")
        with open(self.log_path, "w", encoding="utf-8") as f:
            f.write(self.model_dump_json(indent=2))
