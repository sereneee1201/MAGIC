# -*- coding: utf-8 -*-

from magic.object.objrtv.objathor.dataset import (
    DEFAULT_DSC,
    DatasetSaveConfig,
    download_parse_args,
    load_holodeck_base,
)


def download_holodeck_base(base_path: str = DEFAULT_DSC.BASE_PATH) -> None:
    dsc = DatasetSaveConfig(VERSION="2023_09_23", BASE_PATH=base_path)
    print(f"Holodeck base downloaded to {load_holodeck_base(dsc)}\n")


def _cli() -> None:
    args = download_parse_args("Download files needed to run Holodeck.")
    download_holodeck_base(args.path)


if __name__ == "__main__":
    _cli()
