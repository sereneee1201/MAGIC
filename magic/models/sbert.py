# -*- coding: utf-8 -*-

from functools import cached_property
from typing import Optional

import torch
from sentence_transformers import SentenceTransformer
from torch import Tensor


class SentenceBert(object):
    def __init__(
        self, model_name: str = "all-mpnet-base-v2", device: Optional[str] = None, cache_dir: Optional[str] = None
    ) -> None:
        self.__device = "cpu" if device is None else device
        self.__model = SentenceTransformer(model_name, device=self.__device, cache_folder=cache_dir)

    def __call__(self, emb_1: Tensor, emb_2: Tensor) -> Tensor:
        if (d := emb_1.dim()) != 2:
            raise ValueError(f"Number of dimensions of `emb_1` must be 2, got {d}")
        if (d := emb_2.dim()) != 2:
            raise ValueError(f"Number of dimensions of `emb_2` must be 2, got {d}")
        return (emb_1 @ emb_2.T).clamp(-1.0, 1.0)  # dimensions: (N, D) @ (M, D) -> (N, M)

    @torch.inference_mode()
    def encode(self, sentences: list[str]) -> Tensor:
        return self.__model.encode(
            sentences,
            convert_to_tensor=True,
            normalize_embeddings=True,
            show_progress_bar=False,
            device=self.device,
        ).detach()

    @property
    def device(self) -> str:
        return self.__device

    @cached_property
    def dim(self) -> int:
        return self.encode("").size(dim=-1)
