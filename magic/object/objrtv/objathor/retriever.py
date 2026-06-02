# -*- coding: utf-8 -*-

"""
Sources:
- [ObjaTHOR](https://github.com/allenai/objathor/tree/511d425dbdde6297ed3c399351a4060ffba99752)
- [Holodeck](https://github.com/allenai/Holodeck/tree/362b8ed948b867b69a72f1f9491f4caa88419bfc)
"""

from os.path import exists, join
from typing import Any, Optional

import compress_json
import compress_pickle
import numpy as np
import torch
import torch.nn.functional as F

from magic.constants import OBJATHOR_ANNOTATIONS_PATH, OBJATHOR_ASSETS_DIR, OBJATHOR_FEATURES_DIR
from magic.models.clip import OpenClip
from magic.models.sbert import SentenceBert
from magic.object.objrtv.base import ObjectRetriever
from magic.object.objrtv.objathor.utils.exporter import objathor_to_obj
from magic.utils.dtypes import PathLike, SDict
from magic.utils.maths import clamp
from magic.utils.misc import tsprint


class ObjathorRetriever(ObjectRetriever):
    def __init__(self, **kwargs: Any) -> None:
        device = kwargs.pop("device", "cpu")
        cache_dir = kwargs.pop("cache_dir", None)
        super().__init__(**kwargs)
        self.__clip = OpenClip("ViT-L-14", pretrained="laion2b_s32b_b82k", device=device, cache_dir=cache_dir)
        self.__sbert = SentenceBert("all-mpnet-base-v2", device=device, cache_dir=cache_dir)
        self.__database: SDict[SDict[Any]] = compress_json.load(OBJATHOR_ANNOTATIONS_PATH)
        clip_features_dict = compress_pickle.load(join(OBJATHOR_FEATURES_DIR, "clip_features.pkl"))
        self.__clip_features = torch.from_numpy(clip_features_dict["img_features"].astype(np.float32))
        self.__clip_features = F.normalize(self.__clip_features.to(self.__clip.device), p=2, dim=-1)
        sbert_features_dict = compress_pickle.load(join(OBJATHOR_FEATURES_DIR, "sbert_features.pkl"))
        self.__sbert_features = torch.from_numpy(sbert_features_dict["text_features"].astype(np.float32))
        self.__sbert_features = F.normalize(self.__sbert_features.to(self.__sbert.device), p=2, dim=-1)
        self.__asset_ids: list[str] = clip_features_dict["uids"]

    def _acquire(self, query: str, output_obj: PathLike, **kwargs: Any) -> tuple[bool, SDict[Any]]:
        retrieved = self.__retrieve(
            query, thresh=kwargs.pop("thresh", None), alpha=kwargs.pop("alpha", None), beta=kwargs.pop("beta", None)
        )
        if len(retrieved) == 0:
            tsprint(f"[{type(self).__name__}] No object retrieved for query: {query}")
            return False, {}
        for asset_idx, score in retrieved:
            uid = self.__asset_ids[asset_idx]
            asset_dir = join(OBJATHOR_ASSETS_DIR, uid)
            if not objathor_to_obj(
                uid,
                output_obj=output_obj,
                rot_y_radian=self.__database[uid]["pose_z_rot_angle"],
                albedo_path=join(asset_dir, "albedo.jpg"),
                emission_path=join(asset_dir, "emission.jpg"),
                normal_path=join(asset_dir, "normal.jpg"),
                roughness=kwargs.pop("roughness", None),
                metallic=kwargs.pop("metallic", None),
            ):
                continue
            if not exists(output_obj):
                continue
            return True, {"uid": uid, "score": score}

    def __retrieve(
        self, query: str, thresh: Optional[float] = None, alpha: Optional[float] = None, beta: Optional[float] = None
    ) -> list[tuple[int, float]]:
        thresh = 0.5 if thresh is None else clamp(thresh, 0.0, 1.0)
        alpha = 100.0 if alpha is None else max(alpha, 0.0)
        beta = 1.0 if beta is None else max(beta, 0.0)
        if alpha == 0.0 and beta == 0.0:
            raise ValueError(f"`alpha` and `beta` must not be zero at the same time")
        clip_similarities = (
            self.__clip(self.__clip.encode_texts([query]), self.__clip_features).max(-1).values
            if alpha != 0
            else torch.zeros((1, self.__sbert_features.size(0)))
        )
        sbert_similarities = (
            self.__sbert(self.__sbert.encode([query]), self.__sbert_features)
            if beta != 0
            else torch.zeros((1, self.__clip_features.size(0)))
        )
        similarities = (alpha * clip_similarities + beta * sbert_similarities) / (alpha + beta)
        similarities = (similarities + 1) / 2  # normalize to [0, 1]
        indices = torch.where(similarities >= thresh)[1]
        results = [(asset_idx.item(), similarities[0, asset_idx].item()) for asset_idx in indices]
        results.sort(key=lambda x: x[1], reverse=True)
        return results
