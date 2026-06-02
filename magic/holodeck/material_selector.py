# -*- coding: utf-8 -*-

"""
Source: [Holodeck](https://github.com/allenai/Holodeck/blob/362b8ed948b867b69a72f1f9491f4caa88419bfc/ai2holodeck/generation/rooms.py#L355)
"""

import os

import compress_json
import compress_pickle
import torch
from torch import Tensor
from tqdm import tqdm

from magic.constants import HOLODECK_BASE_DIR
from magic.models.clip import OpenClip


class MaterialSelector(object):
    def __init__(self, clip: OpenClip) -> None:
        self.__clip = clip
        materials = compress_json.load(os.path.join(HOLODECK_BASE_DIR, "materials", "material-database.json"))
        self.__materials = materials["Wall"] + materials["Wood"] + materials["Fabric"]
        self.__clip_features = self.__load_features().to(self.__clip.device)

    def __call__(self, query: str) -> str:
        clip_similarity = self.__clip(self.__clip.encode_texts(query), self.__clip_features)
        results = [
            (sim.item(), os.path.join(HOLODECK_BASE_DIR, "materials", "images", f"{self.__materials[idx]}.png"))
            for idx, sim in enumerate(clip_similarity.squeeze())
        ]
        results.sort(reverse=True)
        return results[0][1]

    def __load_features(self) -> Tensor:
        pkl_path = os.path.join(HOLODECK_BASE_DIR, "materials", "material_feature_clip.pkl")
        try:
            return compress_pickle.load(pkl_path)
        except FileNotFoundError:
            clip_features = []
            for material in tqdm(self.__materials, desc="Precomputing CLIP features for materials"):
                clip_features.append(
                    self.__clip.encode_images(
                        os.path.join(HOLODECK_BASE_DIR, "materials", "images", f"{material}.png")
                    )
                )
            clip_features = torch.vstack(clip_features)
            compress_pickle.dump(clip_features, pkl_path)
            return clip_features
