# -*- coding: utf-8 -*-

import shutil
import time
import ast
import copy
from glob import glob
from os import makedirs
from pathlib import Path
from typing import Any, Optional

from termcolor import colored
from tqdm import tqdm

from magic.constants import PACKAGE_NAME
from magic.generation import GenerationMode, MagicConfig, MagicLog, MagicScene
from magic.generation.composition import MagicComposition
from magic.generation.modules.baseline import get_baseline
from magic.generation.modules.object_placement import *
from magic.generation.modules.prompt_processing import *
from magic.generation.modules.scene_conceptualization import *
from magic.generation.modules.system import get_sys_prompt
from magic.models.clip import OpenClip
from magic.unity.main import MagicUnity
from magic.utils.dtypes import SDict
from magic.utils.file import get_available_path, load_json, load_yaml, read_text_file
from magic.utils.llm import JsonParser, Llm, LlmConfig
from magic.utils.misc import (
    Timer,
    colored_error,
    fix_seed,
    format_elapsed_time,
    format_error,
    get_datetime,
    get_device,
    parse_cli_kwargs,
    tsprint,
)
from magic.utils.retry import set_max_retries, auto_retry
from magic.generation.flood_fill import blockage_eval



class Magic(object):
    def __init__(self, config: MagicConfig, llm_bag: SDict[LlmConfig], scene_idx: str, portals: list, doors: list, p_windows: list) -> None:
        self.__config = config
        self.__sys_prompt = get_sys_prompt()
        self.scene_idx = scene_idx
        self.portals = ast.literal_eval(portals[0])
        self.doors = ast.literal_eval(doors[0])
        self.p_windows = ast.literal_eval(p_windows[0])
        json_parser = JsonParser(llm=Llm(llm_bag[config.normal_llm], verbose=config.verbose))
        self.__normal_llm = Llm(
            llm_bag[config.normal_llm], sys_prompt=self.__sys_prompt, json_parser=json_parser, verbose=config.verbose
        )
        self.__reasoning_llm = Llm(
            llm_bag[config.reasoning_llm],
            sys_prompt=self.__sys_prompt,
            json_parser=json_parser,
            verbose=config.verbose,
        )
        self.__vlm = Llm(
            llm_bag[config.vlm], sys_prompt=self.__sys_prompt, json_parser=json_parser, verbose=config.verbose
        )
        self.__suffix = f"_{suf}" if (suf := config.suffix) is not None else ""
        self.__output_dir: Optional[Path] = None

    def __call__(self, inp: str | MagicLog) -> MagicLog:
        now = get_datetime()
        self.__output_dir = self.config.parent_dir / f"{PACKAGE_NAME}_{now}{self.__suffix}"
        self.__output_dir = get_available_path(self.__output_dir)
        makedirs(self.__output_dir)
        log_path = self.__output_dir / f"output_{self.scene_idx}.json"
        open(log_path, "w", encoding="utf-8").close()
        if isinstance(inp, str):
            scene = MagicScene(prompt=inp)
            log = MagicLog(
                timestamp=now,
                config=self.config,
                output_dir=self.__output_dir,
                log_path=log_path,
                scene=scene,
            )
        elif isinstance(inp, MAgicLog):
            log = inp
            log.timestamp = now
            log.config = self.config
            log.output_dir = self.__output_dir
            log.log_path = log_path
            log.duration.clear()
            log.evaluation.clear()
            log.modules.clear()
            scene = log.scene
            if scene is None:
                raise ValueError("The input log does not contain a scene")
        else:
            raise TypeError(f"Expected a string (i.e., prompt) or MagicLog, got {type(inp)}")
        log.save()
        if self.config.gen_mode.value >= GenerationMode.FROM_COMPOSE.value:
            return log
        if self.config.verbose:
            tsprint(f"{colored('System:', color='light_grey')} {self.__sys_prompt}\n")
        start_time = time.perf_counter()

        if self.config.gen_mode == GenerationMode.BASELINE:
            log.modules.append(self.__baseline(scene, log))
            log.save()
        else:
            if self.config.gen_mode.value <= GenerationMode.BEFORE_OBJECT_PLACEMENT.value:
                log.meshes.clear()
                with Timer() as timer:
                    # ----- Prompt Processing Module -----
                    tsprint(colored("Module:", color="blue", attrs=["bold"]), "Prompt Processing\n")
                    log.modules.append(self.__classify_scene(scene, log))
                    log.save()
                    log.modules.append(self.__extract_regions(scene, log))
                    log.save()
                    log.modules.append(self.__inject_design_to_main_prompt(scene, log))
                    log.save()
                    log.modules.append(self.__extract_subprompts(scene, log))
                    log.save()
                    # ====================================
                    log.duration["prompt_processing"] = timer.get()
                    log.save()
                with Timer() as timer:
                    # ----- Scene Conceptualization Module -----
                    tsprint(colored("Module:", color="blue", attrs=["bold"]), "Scene Conceptualization\n")
                    log.modules.append(self.__design_regions(scene, log))
                    log.save()
                    log.modules.append(self.__get_regions_objects(scene, log, self.portals))
                    log.save()
                    log.modules.append(self.__establish_neighbors(scene, log))
                    log.save()
                    if scene.is_indoor:
                        log.modules.append(self.__establish_indoor_connections(scene, log, self.doors, self.p_windows))
                        log.save()
                    log.modules.append(self.__get_regions_shape(scene, log))
                    log.save()
                    if scene.is_indoor:
                        log.modules.append(self.__adjust_rooms(scene, log))
                        log.save()
                        log.modules.append(self.__place_indoor_connections(scene, log))
                        log.save()
                    if self.config.new_constraints:
                        log.modules.append(self.__get_regions_constraints(scene, log))
                        log.save()
                    # ==========================================
                    log.duration["scene_conceptualization"] = timer.get()
                    log.save()
                if self.config.gen_mode == GenerationMode.BEFORE_OBJECT_PLACEMENT:
                    return log
            with Timer() as timer:
                # ----- Object Placement Module -----
                tsprint(colored("Module:", color="blue", attrs=["bold"]), "Object Placement\n")
                self.__object_placement_draft(scene, log)
                log.save()
                # ===================================
                if self.config.new_draft or self.config.max_solution_corrections > 0:
                    log.modules.append(self.__get_regions_lights(scene, log))
                    log.save()
                # ===================================
                log.duration["object_placement"] = timer.get()
                log.save()

        log.duration["scene_synthesis"] = duration = time.perf_counter() - start_time
        log.save()
        if self.config.verbose:
            tsprint(f"The scene ({log.log_path}) is generated in {format_elapsed_time(duration)}\n")
        return log

    def __baseline(self, scene: MagicScene, log: MagicLog) -> SDict[Any]:
        if self.config.verbose:
            tsprint(colored("Module:", color="blue", attrs=["bold"]), "Baseline\n")
        with Timer() as timer:
            solver = getattr(self, self.config.solution_llm)
            assert isinstance(solver, Llm)
            content = get_baseline(scene, self.config, solver, log)
            record = {"baseline": {"content": content, "duration": timer.get()}}
        return record

    def __classify_scene(self, scene: MagicScene, log: MagicLog) -> SDict[Any]:
        if self.config.verbose:
            tsprint(colored("Submodule:", color="blue"), "classify scene\n")
        with Timer() as timer:
            content = classify_scene(scene, self.config, self.normal_llm, log)
            record = {"scene_type": {"content": content, "duration": timer.get()}}
        return record

    def __extract_regions(self, scene: MagicScene, log: MagicLog) -> SDict[Any]:
        if self.config.verbose:
            tsprint(colored("Submodule:", color="blue"), "extract regions\n")
        with Timer() as timer:
            content = extract_regions(scene, self.config, self.normal_llm, log)
            record = {"regions_extraction": {"content": content, "duration": timer.get()}}
        return record

    def __inject_design_to_main_prompt(self, scene: MagicScene, log: MagicLog) -> SDict[Any]:
        with Timer() as timer:
            if self.config.inject_design:
                if self.config.verbose:
                    tsprint(colored("Submodule:", color="blue"), "inject design to main prompt\n")
                content = inject_design_to_main_prompt(scene, self.config, self.normal_llm, log)
            else:
                scene.design_injected_prompt = scene.prompt
                content = {}
            record = {"design_injection": {"content": content, "duration": timer.get()}}
        return record

    def __extract_subprompts(self, scene: MagicScene, log: MagicLog) -> SDict[Any]:
        if self.config.verbose:
            tsprint(colored("Submodule:", color="blue"), "extract subprompts\n")
        with Timer() as timer:
            content = extract_subprompts(scene, self.config, self.normal_llm, log)
            record = {"subprompts_extraction": {"content": content, "duration": timer.get()}}
        return record

    def __design_regions(self, scene: MagicScene, log: MagicLog) -> SDict[Any]:
        if self.config.verbose:
            tsprint(colored("Submodule:", color="blue"), "design regions\n")
        with Timer() as timer:
            content = design_regions(scene, self.config, self.normal_llm, log)
            record = {"regions_design": {"content": content, "duration": timer.get()}}
        return record

    def __get_regions_objects(self, scene: MagicScene, log: MagicLog, portals: list) -> SDict[Any]:
        if self.config.verbose:
            tsprint(colored("Submodule:", color="blue"), "generate regions objects\n")
        with Timer() as timer:
            content = get_regions_objects(scene, self.config, self.normal_llm, log, portals)
            record = {"regions_objects": {"content": content, "duration": timer.get()}}
        return record

    def __establish_neighbors(self, scene: MagicScene, log: MagicLog) -> SDict[Any]:
        if self.config.verbose:
            tsprint(colored("Submodule:", color="blue"), "establish neighbors\n")
        with Timer() as timer:
            content = establish_neighbors(scene, self.config, self.normal_llm, log)
            record = {"neighbors_establishment": {"content": content, "duration": timer.get()}}
        return record

    def __establish_indoor_connections(self, scene: MagicScene, log: MagicLog, doors: list, p_windows: list) -> SDict[Any]:
        if self.config.verbose:
            tsprint(colored("Submodule:", color="blue"), "establish connections\n")
        with Timer() as timer:
            content = establish_indoor_connections(scene, self.config, self.normal_llm, log, doors, p_windows)
            record = {"connections": {"content": content, "duration": timer.get()}}
        return record

    def __get_regions_shape(self, scene: MagicScene, log: MagicLog) -> SDict[Any]:
        if self.config.verbose:
            tsprint(colored("Submodule:", color="blue"), "generate regions shape\n")
        with Timer() as timer:
            content = get_regions_shape(scene, self.config, self.normal_llm, log)
            record = {"regions_shape": {"content": content, "duration": timer.get()}}
        return record

    def __adjust_rooms(self, scene: MagicScene, log: MagicLog) -> SDict[Any]:
        if self.config.verbose:
            tsprint(colored("Submodule:", color="blue"), "adjust rooms\n")
        with Timer() as timer:
            content = adjust_rooms(scene, self.config, self.normal_llm, log)
            record = {"adjust_rooms": {"content": content, "duration": timer.get()}}
        return record

    def __place_indoor_connections(self, scene: MagicScene, log: MagicLog) -> SDict[Any]:
        if self.config.verbose:
            tsprint(colored("Submodule:", color="blue"), "place connections\n")
        with Timer() as timer:
            content = place_indoor_connections(scene, self.config, self.normal_llm, log)
            record = {"place_indoor_connections": {"content": content, "duration": timer.get()}}
        return record

    @auto_retry
    def __object_placement_draft(self, scene: MagicScene, log: MagicLog) -> SDict[Any]:
        if self.config.new_draft:
            log.modules.append(self.__draft_regions_solution(scene, log))
            log.save()
        if self.config.max_solution_corrections > 0:
            log.modules.append(self.__get_regions_corrections(scene, log))
            log.save()
        connectivity, success = blockage_eval(log=log.log_path, output_dir=self.__output_dir)
        tries = 0
        best_log = copy.deepcopy(log)
        best_conn = connectivity
        while (not success) and tries < 3:
            print("Flood fill failed, regenerating...")
            tries += 1
            if self.config.new_draft:
                log.modules.append(self.__draft_regions_solution(scene, log))
                log.save()
            if self.config.max_solution_corrections > 0:
                log.modules.append(self.__get_regions_corrections(scene, log))
                log.save()
            connectivity, success = blockage_eval(log=log.log_path, output_dir=self.__output_dir)
            if connectivity > best_conn:
                best_log = copy.deepcopy(log)
                best_conn = connectivity
        log = copy.deepcopy(best_log)
        log.save()
        if tries > 0:
            connectivity, success = blockage_eval(log=log.log_path, output_dir=self.__output_dir)
        print(f"\nFlood fill test: {success} Trials: {tries}")

    def __draft_regions_solution(self, scene: MagicScene, log: MagicLog) -> SDict[Any]:
        if self.config.verbose:
            tsprint(colored("Submodule:", color="blue"), "draft regions solution\n")
        with Timer() as timer:
            solver = getattr(self, self.config.solution_llm)
            assert isinstance(solver, Llm)
            content = draft_regions_solution(scene, self.config, solver, log)
            record = {"regions_draft": {"content": content, "duration": timer.get()}}
        return record

    def __get_regions_constraints(self, scene: MagicScene, log: MagicLog) -> SDict[Any]:
        if self.config.verbose:
            tsprint(colored("Submodule:", color="blue"), "generate regions constraints\n")
        with Timer() as timer:
            _llm = getattr(self, self.config.constraint_llm)
            assert isinstance(_llm, Llm)
            content = get_regions_constraints(scene, self.config, _llm, log)
            record = {"regions_constraints": {"content": content, "duration": timer.get()}}
        return record

    def __get_regions_corrections(self, scene: MagicScene, log: MagicLog) -> SDict[Any]:
        if self.config.verbose:
            tsprint(colored("Submodule:", color="blue"), "generate regions corrections\n")
        with Timer() as timer:
            solver = getattr(self, self.config.solution_llm)
            assert isinstance(solver, Llm)
            content = get_regions_corrections(scene, self.config, solver, log)
            record = {"regions_corrections": {"content": content, "duration": timer.get()}}
        return record

    def __get_regions_lights(self, scene: MagicScene, log: MagicLog) -> SDict[Any]:
        if self.config.verbose:
            tsprint(f"{colored('Submodule:', color='blue')} generate regions lights\n")
        with Timer() as timer:
            content = get_regions_lights(scene, self.config, self.normal_llm, log)
            record = {"regions_lights": {"content": content, "duration": timer.get()}}
        return record

    def remove_previous_output(self) -> bool:
        if self.__output_dir is not None and self.__output_dir.is_dir():
            shutil.rmtree(self.__output_dir, ignore_errors=True)
            self.__output_dir = None
            return True
        return False

    @property
    def config(self) -> MagicConfig:
        return self.__config

    @property
    def normal_llm(self) -> Llm:
        return self.__normal_llm

    @property
    def reasoning_llm(self) -> Llm:
        return self.__reasoning_llm

    @property
    def vlm(self) -> Llm:
        return self.__vlm


def _cli() -> None:
    import argparse

    from magic.dataset import MagicDatapoint

    parser = argparse.ArgumentParser()
    parser.add_argument("-i", "--index", type=str, required=True, help="Index of the scene.")
    parser.add_argument("-c", "--config", type=str, required=True, help="Path to a YAML configuration file.")
    parser.add_argument(
        "-p",
        "--prompt",
        action="append",
        type=str,
        default=None,
        help="A single prompt. Use multiple `--prompt`s for multiple prompts. Defaults to None.",
    )
    parser.add_argument(
        "--portals",
        action="append",
        type=str,
        default=None,
        help="List of portals in the scene. Defaults to None.",
    )
    parser.add_argument(
        "--doors",
        action="append",
        type=str,
        default=None,
        help="List of doors in the scene. Defaults to None.",
    )
    parser.add_argument(
        "--p_windows",
        action="append",
        type=str,
        default=None,
        help="List of portal windows in the scene. Defaults to None.",
    )
    parser.add_argument(
        "-f",
        "--file",
        action="append",
        type=str,
        default=None,
        help="Path to a single file containing lines of prompts. Use multiple `--file` for multiple files. Defaults to None.",
    )
    parser.add_argument(
        "-d", "--datapoint", action="append", type=str, default=None, help="Path to a JSON data point."
    )
    parser.add_argument("-l", "--log", action="append", type=str, default=None, help="Path to a JSON log file.")
    parser.add_argument("--seed", type=int, default=None, help="Random seed for reproducibility.")
    parser.add_argument("--kwarg", action="append", type=str, default=None, help="Additional keyword argument.")
    args = parser.parse_args()
    if args.prompt is None and args.file is None and args.datapoint is None and args.log is None:
        return
    config = load_yaml(args.config, replace_env_var=True)
    magic_config = MagicConfig(**{**config.get("magic", {}), **parse_cli_kwargs(args.kwarg)})
    if args.seed is not None:
        tsprint(f"Seeding: {args.seed}")
        fix_seed(args.seed)
    set_max_retries(magic_config.max_retries)
    llm_bag = {str(k): LlmConfig(**v, max_retries=magic_config.max_retries) for k, v in config["llm"].items()}
    tsprint(f"Configuration: {magic_config.model_dump()}\n")
    device = get_device()[0]

    # load all inputs
    inputs: list[str | MagicLog] = []
    if args.prompt is not None:
        for p in args.prompt:
            inputs.append(p)
    if args.file is not None:
        for f in args.file:
            for line in read_text_file(f, remove_spaces=True, remove_empty=True):
                inputs.append(line)
    if args.datapoint is not None:
        for item in args.datapoint:
            path, variant = item.split(":", maxsplit=1)
            dp = MagicDatapoint(**load_json(path))
            inputs.append(getattr(dp.prompts, variant))

    scene_idx = args.index
    clip = OpenClip(device=device)
    pipeline = Magic(magic_config, llm_bag, scene_idx, args.portals, args.doors, args.p_windows)
    composer = MagicComposition(magic_config, pipeline.vlm, clip, device=device) if magic_config.compose else None
    unity = MagicUnity(magic_config, scene_idx) if magic_config.unity else None
    for idx, inp in tqdm(enumerate(inputs), total=len(inputs), desc="Inputs"):
        for t in tqdm(range(magic_config.n_trials), desc="Trials", leave=False, disable=magic_config.n_trials == 1):
            run = f"{idx + 1}@{t + 1}"
            try:
                if args.log is not None:
                    log = MagicLog(**load_json(args.log[0]))
                else:
                    log = pipeline(inp)
                if composer is not None:
                    composer(log)
                if len(log.meshes) > 0:
                    MagicComposition.export_scenes(log)
                    if magic_config.render:
                        MagicComposition.render(log)
                    if unity is not None:
                        unity(log)
            except KeyboardInterrupt:
                raise
            except BaseException as e:
                err = "\n|\nv\n".join(format_error(e))
                tsprint(colored_error(), f"Exception(s) in {run}: {err}", end="\n\n")
                continue


if __name__ == "__main__":
    _cli()
