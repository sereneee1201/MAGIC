# -*- coding: utf-8 -*-

from PIL import Image


def get_default_albedo_map(width: int = 1, height: int = 1) -> Image.Image:
    return Image.new("RGB", (width, height), (255, 255, 255))


def get_default_emission_map(width: int = 1, height: int = 1) -> Image.Image:
    return Image.new("RGB", (width, height), (0, 0, 0))


def get_default_normal_map(width: int = 1, height: int = 1) -> Image.Image:
    return Image.new("RGB", (width, height), (128, 128, 255))
