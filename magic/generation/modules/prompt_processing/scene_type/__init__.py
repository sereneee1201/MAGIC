# -*- coding: utf-8 -*-

from typing import ClassVar

from pydantic import BaseModel, field_validator

from magic.generation import MagicConfig, MagicLog, MagicScene
from magic.generation.modules import OUTPUT_GUIDANCE
from magic.generation.modules.prompt_processing.scene_type.templates import SCENE_TYPE_TEMPLATE
from magic.utils.dtypes import NonEmptyStr
from magic.utils.llm import Llm, LlmContent, TemplateFormatter
from magic.utils.retry import auto_retry


class SceneType(BaseModel, validate_assignment=True, strict=True):
    scene_type: NonEmptyStr
    _permitted: ClassVar[set[str]] = {"indoor", "outdoor", "mixed"}

    @field_validator("scene_type", mode="after")
    @classmethod
    def lower_scene_type(cls, v: NonEmptyStr):
        lowered = v.lower()
        if lowered not in cls._permitted:
            raise ValueError(f"Unknown scene type '{v}'. Must be one of {cls._permitted}.")
        return lowered


get_scene_type_prompt = TemplateFormatter(SCENE_TYPE_TEMPLATE, output_guidance=OUTPUT_GUIDANCE, prompt=None)


@auto_retry
def classify_scene(scene: MagicScene, config: MagicConfig, llm: Llm, log: MagicLog) -> LlmContent:
    llm.clear_messages()
    prompt = get_scene_type_prompt(prompt=scene.prompt)
    response, llm_output = llm.chat(prompt, temperature=0.0, to_json=True)
    if not isinstance(response, dict):
        raise RuntimeError()
    if "reasoning" not in response:
        raise RuntimeError()
    if "scene_type" not in response:
        raise RuntimeError()
    scene.scene_type = SceneType(scene_type=response["scene_type"]).scene_type
    log.save()
    llm.clear_messages()
    return llm_output.content
