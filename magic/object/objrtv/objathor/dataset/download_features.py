# -*- coding: utf-8 -*-

from magic.object.objrtv.objathor.dataset import DEFAULT_DSC, DatasetSaveConfig, download_parse_args, load_features_dir


def download_features(version: str = DEFAULT_DSC.VERSION, base_path: str = DEFAULT_DSC.BASE_PATH) -> None:
    dsc = DatasetSaveConfig(VERSION=version, BASE_PATH=base_path)
    print(f"Features downloaded to {load_features_dir(dsc)}\n")


def _cli() -> None:
    args = download_parse_args("Download features from the dataset")
    download_features(args.version, args.path)


if __name__ == "__main__":
    _cli()
