# -*- coding: utf-8 -*-

import subprocess
from functools import lru_cache
from os.path import isfile, join

from magic.utils.misc import tsprint


@lru_cache(maxsize=1)
def has_unity() -> bool:
    cmd = ["Unity", "-version"]
    try:
        result = subprocess.run(cmd, shell=False, capture_output=True)
        return result.returncode == 0
    except FileNotFoundError:
        return False


def build_scene(project_dir: str, scene_idx: str, verbose: bool = True) -> None:
    if not has_unity():
        raise RuntimeError("Unity is not installed or not found in the system path")
    script = join(project_dir, "Assets", "Scripts", f"SceneBuilder_{scene_idx}.cs")
    if not isfile(script):
        raise FileNotFoundError(f"Failed to locate {script}")
    log_path = join(project_dir, f"SceneBuilder_{scene_idx}.log")
    cmd = [
        "Unity",
        "-batchmode",
        "-quit",
        "-projectPath",
        str(project_dir),
        "-executeMethod",
        f"SceneBuilder_{scene_idx}.BuildScene",
        "-logFile",
        log_path,
    ]
    if verbose:
        tsprint(f"Running command: {' '.join(cmd)}\n")
    try:
        result = subprocess.run(
            cmd, shell=False, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, check=True
        )
    except subprocess.CalledProcessError as e:
        raise RuntimeError(
            f"Failed to run Unity script:\n{e.stdout}\n\nPlease check {log_path} for more details\n"
        ) from e
    else:
        if verbose:
            tsprint(f"Unity script output:\n{result.stdout}\n")
    return result
