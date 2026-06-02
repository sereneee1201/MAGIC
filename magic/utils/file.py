# -*- coding: utf-8 -*-

import json
import os
from collections.abc import Iterator
from os import makedirs
from os.path import dirname, exists
from pathlib import Path
from typing import Any, Optional

import numpy as np
from PIL import Image

from magic.utils.dtypes import ImgLike, JsonObject, PathLike, YamlObject


def load_text_file(path: str) -> str:
    with open(path, encoding="utf-8") as file:
        return file.read()


def read_text_file(file_path: str, remove_spaces: bool = False, remove_empty: bool = False) -> Iterator[str]:
    with open(file_path, encoding="utf-8") as f:
        for line in f:
            line = line.rstrip("\n")
            line = line.strip() if remove_spaces else line
            if remove_empty and line == "":
                continue
            yield line


def _replace_env_var(data: Any) -> Any:
    if isinstance(data, dict):
        return {k: _replace_env_var(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [_replace_env_var(item) for item in data]
    elif isinstance(data, str) and data.startswith("$"):
        return os.environ.get(data[1:].split()[0], None)
    return data


def load_json(path: str, replace_env_var: bool = False) -> JsonObject:
    with open(path, encoding="utf-8") as file:
        data = json.load(file)
    return _replace_env_var(data) if replace_env_var else data


def save_json(data: Any, path: str, indent: Optional[int] = None) -> None:
    output_dir = dirname(path)
    if output_dir != "" and not exists(output_dir):
        makedirs(output_dir)
    with open(path, "w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False, indent=indent)


def load_yaml(path: str, safe: bool = True, replace_env_var: bool = False) -> YamlObject:
    import yaml

    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f) if safe else yaml.unsafe_load(f)
    return _replace_env_var(data) if replace_env_var else data


def save_yaml(data: Any, path: str, safe: bool = True) -> None:
    import yaml

    output_dir = dirname(path)
    if output_dir != "" and not exists(output_dir):
        makedirs(output_dir)
    func = yaml.safe_dump if safe else yaml.dump
    with open(path, "w") as f:
        func(data, f, indent=2, allow_unicode=True)


def find_files(target_dir, pattern: str = "*.*") -> Iterator[str]:
    return map(str, Path(target_dir).rglob(pattern))


def get_available_path(path: PathLike) -> Path:
    path: Path = Path(path)
    if not path.exists():
        return path
    if path.is_dir():
        base, ext = path, ""
    else:
        base, ext = path.with_suffix(""), path.suffix
    i = 2
    new_path = Path(f"{base}_{i}{ext}")
    while new_path.exists():
        i += 1
        new_path = Path(f"{base}_{i}{ext}")
    return new_path


def load_image_to_pillow(img: ImgLike) -> Image.Image:
    if isinstance(img, Image.Image):
        img = img
    elif isinstance(img, np.ndarray):
        img = Image.fromarray(img)
    elif isinstance(img, str):
        if img.startswith("http://") or img.startswith("https://"):
            import requests

            img = Image.open(requests.get(img, stream=True).raw)
        else:
            img = Image.open(img)
    else:
        raise ValueError(f'Unsupported image type "{type(img)}"')
    return img.convert("RGB")
