# -*- coding: utf-8 -*-

import subprocess
from functools import lru_cache
from os.path import abspath, dirname, isfile, join

from magic.utils.misc import tsprint


@lru_cache(maxsize=1)
def has_blender() -> bool:
    cmd = ["blender", "-v"]
    try:
        result = subprocess.run(cmd, shell=False, capture_output=True)
        return result.returncode == 0
    except FileNotFoundError:
        return False


def brender(*codes: str, verbose: bool = True) -> subprocess.CompletedProcess:
    if not has_blender():
        raise RuntimeError("Blender is not installed or not found in the system path")
    script = join(abspath(dirname(__file__)), "brender.py")
    if not isfile(script):
        raise FileNotFoundError(f"Failed to locate {script}")
    cmd = ["blender", "-b", "-P", script, "--", *codes]
    if verbose:
        tsprint(f"Running command: {cmd}\n")
    try:
        result = subprocess.run(
            cmd, shell=False, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, check=True
        )
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"Failed to run Blender script:\n{e.stdout}\n") from e
    else:
        if verbose:
            tsprint(f"Blender script output:\n{result.stdout}\n")
    return result


def _cli() -> None:
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("codes", nargs="+", type=str)
    args = parser.parse_args()
    brender(*args.codes)


if __name__ == "__main__":
    _cli()
