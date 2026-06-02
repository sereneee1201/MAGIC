# -*- coding: utf-8 -*-

from magic.object.objrtv.objathor.dataset import DEFAULT_DSC, DatasetSaveConfig, download_parse_args, load_assets_path


def download_assets(version: str = DEFAULT_DSC.VERSION, base_path: str = DEFAULT_DSC.BASE_PATH) -> None:
    dsc = DatasetSaveConfig(VERSION=version, BASE_PATH=base_path)
    print(f"Assets downloaded to {load_assets_path(dsc)}\n")


def _cli() -> None:
    args = download_parse_args("Download assets from the dataset")
    download_assets(args.version, args.path)


if __name__ == "__main__":
    _cli()
