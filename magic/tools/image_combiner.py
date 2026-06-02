# -*- coding: utf-8 -*-

import os
import sys
from typing import Iterable

import cv2
import numpy as np


def _preprocess_images(images: Iterable[np.ndarray | str]) -> list[np.ndarray]:
    imgs = []
    for img in images:
        if isinstance(img, str):
            img = cv2.imread(img)
            if img is None:
                raise ValueError(f"Could not read image from path: {img}")
        elif not isinstance(img, np.ndarray):
            raise TypeError(f"Expected image to be a numpy array or a file path, got {type(img)}")
        imgs.append(img)
    return imgs


def combine_images(
    *images: np.ndarray | str, n_rows: int, n_cols: int, output_width: int, output_height: int
) -> np.ndarray:
    imgs = _preprocess_images(images)
    if (n_cells := n_rows * n_cols) < len(imgs):
        raise ValueError(f"`n_rows` * `n_cols` must not be less than len(`images`), got {n_cells}")
    cell_width, cell_height = output_width // n_cols, output_height // n_rows
    cell_ratio = cell_width / cell_height
    combined = np.zeros((output_height, output_width, 3), dtype=np.uint8)
    for idx, img in enumerate(imgs):
        # compute the target size of the image
        h, w = img.shape[:2]
        img_ratio = w / h
        if img_ratio > cell_ratio:  # image is wider than cell
            new_width = cell_width
            new_height = min(round(cell_width / img_ratio), cell_height)
        else:
            new_width = min(round(cell_height * img_ratio), cell_width)
            new_height = cell_height

        # resize the image
        if (w, h) != (new_width, new_height):
            interpolation = cv2.INTER_AREA if new_width < w or new_height < h else cv2.INTER_CUBIC
            img = cv2.resize(img, (new_width, new_height), interpolation=interpolation)

        # center the resized image on a specific cell
        row, col = idx // n_cols, idx % n_cols
        y_offset, x_offset = (cell_height - new_height) // 2, (cell_width - new_width) // 2
        start_row, start_col = row * cell_height + y_offset, col * cell_width + x_offset
        combined[start_row : start_row + new_height, start_col : start_col + new_width] = img
    return combined


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("images", nargs="+", help="Paths to input images")
    parser.add_argument("-o", "--output", default="combined.jpg", help="Output image path")
    parser.add_argument("-r", "--rows", type=int, required=True, help="Number of rows in grid layout")
    parser.add_argument("-c", "--cols", type=int, required=True, help="Number of columns in grid layout")
    parser.add_argument("-W", "--width", type=int, required=True, help="Output image width")
    parser.add_argument("-H", "--height", type=int, required=True, help="Output image height")
    args = parser.parse_args()

    try:
        combined = combine_images(
            *args.images, n_rows=args.rows, n_cols=args.cols, output_width=args.width, output_height=args.height
        )
    except ValueError as e:
        print(f"Error: {e}")
        return -1
    os.makedirs(os.path.dirname(args.output) or ".", exist_ok=True)
    if not cv2.imwrite(args.output, combined):
        print(f"Error: Could not write to '{args.output}'.")
        return -1
    print(f"Combined image saved to '{args.output}'.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
