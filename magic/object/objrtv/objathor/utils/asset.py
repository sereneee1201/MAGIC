# -*- coding: utf-8 -*-

from os.path import isdir, join
from typing import Any

from magic.constants import OBJATHOR_ASSETS_DIR
from magic.utils.dtypes import SDict


def has_asset(uid: str) -> bool:
    return isdir(join(OBJATHOR_ASSETS_DIR, uid))


def get_asset_metadata(obj_data: SDict[Any]) -> SDict[Any]:
    if "assetMetadata" in obj_data:
        return obj_data["assetMetadata"]
    elif "thor_metadata" in obj_data:
        return obj_data["thor_metadata"]["assetMetadata"]
    else:
        raise ValueError(f'Cannot find key "assetMetadata" in `obj_data`: {obj_data}')


def get_asset_size(obj_data: SDict[Any]) -> SDict[float]:
    bbox_info = get_asset_metadata(obj_data)["boundingBox"]
    if "x" in bbox_info:
        return bbox_info
    elif "size" in bbox_info:
        return bbox_info["size"]
    return
    return {f"dim_{k}": bbox_info["max"][k] - bbox_info["min"][k] for k in ("x", "y", "z")}
