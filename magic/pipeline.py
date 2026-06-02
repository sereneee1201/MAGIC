import json
import os
import subprocess
import argparse
import ast
import re
import time
import random

from typing import Tuple

from planner import agent_planner, agent_validator
from combine import combine_unity_outputs
from utils.file import load_yaml
from magic.utils.llm import LlmConfig
from generation import MagicConfig

class SceneGeneratorPipeline:
    def __init__(self):
        pass
        
    def stage1_plan(self, prompt: str, config: str, output_dir: str, max_retries=3) -> str:
        """
        Stage 1: Create a simple JSON plan file from scene prompts.
        """

        def parse_planner_res(res: str, prompt, max_retries=5):
            last_error = None

            for attempt in range(max_retries):
                try:
                    json_data = json.loads(res)

                    r_prompt = json_data["prompt"]
                    scenes_dict = json_data["scenes"]
                    n = json_data["n"]
                    initial_scene = json_data["initial_scene"]
                    graph = json_data["graph"]

                    scenes = [scenes_dict[i] for i in range(n)]

                    return r_prompt, scenes, graph, initial_scene

                except Exception as e:
                    last_error = str(e)
                    print(f"[Planner parse failed {attempt+1}/{max_retries}] {e}")

                    res = agent_planner(
                        f"{prompt}\n\nPrevious error: {last_error}\nReturn valid JSON only.",
                        llm_bag
                    )

            raise RuntimeError("Planner failed repeatedly to return valid JSON.")
            
        def count_portals(plan):
            portals = []
            for scene in plan["scenes"]:
                portal_count = {}
                for conn in plan["graph"]["connections"]:
                    if (int(conn["from"])) == scene["scene_idx"] or (int(conn["to"])) == scene["scene_idx"]:
                        try:
                            portal_count[conn["portal"]] += 1
                        except:
                            portal_count[conn["portal"]] = 1
                portals.append(portal_count)
            return portals
        
        def validate_portals(plan, portals_count, llm_bag, max_retries=5):
            for scene in plan["scenes"]:
                valid = False
                tries = 0
                while not valid and tries < max_retries:
                    tries += 1
                    try:
                        validator_res = agent_validator(scene["prompt"], portals_count[scene["scene_idx"]], llm_bag)
                        json_data = json.loads(validator_res)
                        scene["prompt"] = json_data["prompt"]
                        valid = json_data["valid"]
                        if not valid and tries == max_retries:
                            raise RuntimeError("Max retries reached, portal validation failed.")
                    except:
                        print("Invalid JSON, retrying...")
            return plan
        
        config = load_yaml(args.config, replace_env_var=True)
        magic_config = MagicConfig(**{**config.get("magic", {})})
        llm_bag = {str(k): LlmConfig(**v, max_retries=magic_config.max_retries) for k, v in config["llm"].items()}

        planner_res = agent_planner(prompt, llm_bag)
        r_prompt, planner_parser, planner_graph, initial_scene = parse_planner_res(planner_res, prompt)

        for scene_a in planner_parser:
            for scene_b in planner_parser:
                try:
                    if scene_a["name"] != scene_b["name"]:
                        tries = 0
                        while scene_a["name"] in scene_b["description"] and tries < max_retries:
                            tries += 1
                            planner_res = agent_planner(prompt, llm_bag)
                            r_prompt, planner_parser, planner_graph, initial_scene = parse_planner_res(planner_res)
                            if tries == max_retries:
                                raise RuntimeError("Region mentioned in other prompts.")
                except:
                    planner_res = agent_planner(r_prompt, llm_bag)
                    r_prompt, planner_parser, planner_graph, initial_scene = parse_planner_res(planner_res, prompt)

        plan = {
            "prompt": r_prompt,
            "scenes": [
                {
                    "scene_idx": idx,
                    "scene_name": scene["name"],
                    "prompt": scene["description"]
                }
                for idx, scene in enumerate(planner_parser)
            ],
            "graph": planner_graph
        }

        portal_count = count_portals(plan)   
        print(portal_count)

        plan = validate_portals(plan, portal_count, llm_bag)

        json_path = f"{output_dir}/scene_plan.json"
        with open(json_path, "w") as f:
            json.dump(plan, f, indent=2)
        return json_path, initial_scene
    
    def stage2_generate(self, config, json_path: str, output_dir: str, log_flag: int, compose_flag: int):
        """
        Stage 2: Generate scenes from the JSON plan file using magic command.
        """
        with open(json_path, "r") as f:
            plan = json.load(f)

        output_dir = f"{output_dir}/magic-outputs"

        if output_dir:
            if not os.path.exists(output_dir):
                os.makedirs(output_dir)

        if log_flag == 0:
            for scene in sorted(os.listdir(output_dir)):
                scene_dir = os.path.join(output_dir, scene)
                if not os.path.isdir(scene_dir):
                        continue
                for filename in sorted(os.listdir(scene_dir)):
                    if filename.startswith("output"):
                        log_idx = filename.split("_")[-1]
                        cmd = [
                            "magic",
                            "-c", config,
                            "-i", log_idx,
                            "-p", "",
                            "--portals", "[0]",
                            "--doors", "[0]",
                            "--p_windows", "[0]",
                            "--log", os.path.join(scene_dir, filename),
                            "--kwarg", "inject_design=True",
                            "--kwarg", "inject_object=True",
                            "--kwarg", "obj_generator=None",
                            "--kwarg", f"output_dir={output_dir}"
                        ]
                        
                        print(f"Generating scene {log_idx}")
                        print("Command:", " ".join(cmd))
                        subprocess.run(cmd, check=True)
            return
                
        for scene in plan["scenes"]:
            portals = []
            doors = []
            p_windows = []

            for graph in plan["graph"]["connections"]:
                if (int(graph["from"])) == scene["scene_idx"] or (int(graph["to"])) == scene["scene_idx"]:
                    if re.search(r"\bdoor\b", graph["portal"], flags=re.IGNORECASE):
                        doors.append(graph["portal"])
                    elif re.search(r"\bwindow\b", graph["portal"], flags=re.IGNORECASE):
                        p_windows.append(graph["portal"])
                    else:
                        portals.append(graph["portal"])

            print(f"Scene {scene['scene_idx']} portals: {portals}, doors: {doors}, portal windows: {p_windows}")

            cmd = [
                "magic",
                "-c", config,
                "-i", str(scene["scene_idx"]),
                "-p", scene["prompt"],
                "--portals", json.dumps(portals),
                "--doors", json.dumps(doors),
                "--p_windows", json.dumps(p_windows),
                "--kwarg", f"compose={bool(compose_flag)}",
                "--kwarg", "inject_design=True",
                "--kwarg", "inject_object=True",
                "--kwarg", "obj_generator=None",
                "--kwarg", f"output_dir={output_dir}"
            ]
            
            print(f"Generating scene {scene['scene_idx']}: {scene['prompt']}")
            print("Command:", " ".join(cmd))
            subprocess.run(cmd, check=True)

    def stage3_unity_process(self, json_path: str, unity_path: str, output_dir:str):
        """
        Stage 3: Process generated scenes through Unity.
        
        Args:
            json_path: Path to the JSON plan file
        """
        with open(json_path, "r") as f:
            plan = json.load(f)
        
        graph = plan["graph"]["connections"]

        with os.scandir(output_dir) as entries:
            names = sorted([entry.name for entry in entries if entry.is_dir()])

        for scene, name in zip(plan["scenes"], names):
            scene_idx = scene["scene_idx"]

            log_file = f"{output_dir}/{name}/output_{scene_idx}.json"
            # read the existing log file
            try:
                with open(log_file, "r", encoding="utf-8") as f:
                    log_data = json.load(f)
                
                # replace paths in the log data
                def replace_paths(obj):
                    if isinstance(obj, dict):
                        return {k: replace_paths(v) for k, v in obj.items()}
                    elif isinstance(obj, list):
                        return [replace_paths(item) for item in obj]
                    return obj
                
                updated_log_data = replace_paths(log_data)
                
                # write the modified log file back
                with open(log_file, "w") as f:
                    json.dump(updated_log_data, f, indent=2)
                                    
            except FileNotFoundError:
                print(f"Warning: Log file not found at {log_file}")
            except json.JSONDecodeError:
                print(f"Warning: Could not parse JSON in {log_file}")
        
            portals = []

            for conn, c_data in log_data.get("scene", {}).get("connections", {}).items():
                if ("__outside__" in c_data.get("region_b", "")) and conn.startswith("door"):
                    d_name = "c-" + c_data.get("region_a", "") + "-" + conn
                    portals.append(d_name)
                elif c_data["obj"].get("is_portal", None) == True:
                    c_name = "c-" + c_data.get("region_a", "") + "-" + conn
                    portals.append(c_name)
      
            for region, r_data in log_data.get("scene", {}).get("regions", {}).items():
                for obj, o_data in r_data.get("objects", {}).items():
                    if o_data.get("is_portal", ""):
                        o_name = "o-" + region + "-" + obj
                        portals.append(o_name)
            
            print(f"Portals found in scene {scene_idx}: {portals}")

            exit_portals = []

            for edge in plan["graph"]["connections"]:
                found = False
                if (int(edge["from"])) == scene_idx:
                    for portal in portals:
                        g_portal = re.sub(r'[^\w]', '', edge["portal"])
                        p_portal = re.sub(r'[^\w]', '', portal)
                        if (g_portal in p_portal):
                            exit_portals.append([portal, edge["to"], edge["effect"]])
                            portals.remove(portal)
                            found = True
                            break
                    if not found:
                        print(f"Warning: {edge['portal']} not found in portals {portals}")
                elif (int(edge["to"])) == scene_idx:
                    for portal in portals:
                        g_portal = re.sub(r'[^\w]', '', edge["portal"])
                        p_portal = re.sub(r'[^\w]', '', portal)
                        if (g_portal in p_portal):
                            exit_portals.append([portal, edge["from"], edge["effect"]])
                            portals.remove(portal)
                            found = True
                            break
                    if not found:
                        print(f"Warning: {edge['portal']} not found in portals {portals}")

            exit_portals_str = json.dumps(exit_portals)

            # run the Unity command
            try:
                cmd = [
                    "python",
                    unity_path,
                    "-i", str(scene["scene_idx"]),
                    "-l", log_file,
                    "-e", exit_portals_str
                ]
                print(f"\nProcessing scene {scene_idx} in Unity...")
                print("Command:", " ".join(cmd))
                subprocess.run(cmd, check=True)
            except Exception as e:
                print(f"Error preparing Unity command for scene {scene_idx}: {e}")
                continue

    def stage4_combine(self, output_dir=""):
        """
        Stage 4: Combine generated scenes using the combine script.
        """
        print("Combining scenes...")
        combine_unity_outputs(output_dir=output_dir)

if __name__ == "__main__":

    parser = argparse.ArgumentParser()
    parser.add_argument("-p", "--prompt", required=True, help="Text prompt for scene generation")
    parser.add_argument("-i", "--case_idx", required=False, default="0", help="Case index of generated scenes")
    parser.add_argument("-c", "--config", required=False, default="configs/config.yaml", help="Path to config file for generation")
    parser.add_argument("-s", "--flags", required=False, default="[1, 1, 1, 1, 1]", help="Generation flags: [Scene plan, Log files, Compose, Unity, Combine]")
    args = parser.parse_args()
    prompt = args.prompt
    output_dir = f"test_cases/case_{args.case_idx}"
    config_dir = args.config
    flags = ast.literal_eval(args.flags)

    if output_dir:
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)

    pipeline = SceneGeneratorPipeline()
    
    # Stage 1: Create the plan
    if flags[0] == 1:
        print("\n=== Stage 1: Planning ===")
        plan_file, initial_scene = pipeline.stage1_plan(prompt, config_dir, output_dir)
        print(f"Plan file created at: {output_dir}/{plan_file}")
        
    # Stage 2: Generate scenes
    if flags[1] == 1 or flags[2] == 1:
        plan_file = f"{output_dir}/scene_plan.json"
        print("\n=== Running stage 2: Generation ===")
        pipeline.stage2_generate(config_dir, plan_file, output_dir, flags[1], flags[2])

    plan_file = f"{output_dir}/scene_plan.json"
    # Stage 3: Unity processing
    if flags[3] == 1:
        print("\n=== Stage 3: Unity Processing ===")
        pipeline.stage3_unity_process(plan_file, unity_path=f"magic/unity/main.py", output_dir=f"{output_dir}/magic-outputs")

    # Stage 4: Combine scenes
    if flags[4] == 1:
        print("\n=== Running stage 4: Combining ===")
        pipeline.stage4_combine(output_dir=output_dir)
        print("\nPipeline complete!")