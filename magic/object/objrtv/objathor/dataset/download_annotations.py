# -*- coding: utf-8 -*-

from magic.object.objrtv.objathor.dataset import (
    DEFAULT_DSC,
    DatasetSaveConfig,
    download_parse_args,
    load_annotations_path,
)


def download_annotations(version: str = DEFAULT_DSC.VERSION, base_path: str = DEFAULT_DSC.BASE_PATH) -> None:
    dsc = DatasetSaveConfig(VERSION=version, BASE_PATH=base_path)
    print(f"Annotations downloaded to {load_annotations_path(dsc)}\n")


def _cli() -> None:
    args = download_parse_args("Download annotations from the dataset repository.")
    download_annotations(args.version, args.path)


if __name__ == "__main__":
    _cli()
