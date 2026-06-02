import argparse
import subprocess
import platform
import json
import time
import os
import sys
import shutil

from collections import defaultdict
from pathlib import Path
from eval_files import EVAL_FILES
from eval_portal import portal_analyzer, match_leftover

sys.path.append("..")
from magic.utils.file import load_yaml
from magic.utils.llm import LlmConfig
from magic.generation import MagicConfig


class EvalAgent:

    def __init__(self, case_idx, project, out, config_dir, version, gt_dir):
        self.case_idx = int(case_idx)
        self.project = Path(project).resolve()
        self.assets = self.project / "Assets"
        self.out_dir = self.project / out
        self.gt_transitions = []
        self.results = []
        self.config_dir = config_dir
        self.length = None
        self.eval_dir = self.assets / "Evaluation"
        self.scene_dir = None
        self.exe_cmd = None
        self.version = version
        self.gt_dir = gt_dir

    def run(self, cmd, cwd=None):
        print("[RUN]", " ".join(cmd))
        subprocess.run(cmd, cwd=cwd, check=True)

    def unity_cmd(self, method):
        return [
            "Unity",
            "-batchmode",
            "-quit",
            "-projectPath", str(self.project),
            "-executeMethod", method,
            "-logFile", str(self.project / f"{method}.log"),
        ]
    
    def portal_dest(self, org, dest, ground_truth):
        types = []
        for edge in ground_truth:
            if ((edge["from"] == org and edge["to"] == dest) or (edge["from"] == dest and edge["to"] == org)):
                types.append(edge["type"])
        return types
    
    def clean_dir(self):
        if os.path.exists(self.out_dir):
            shutil.rmtree(self.out_dir)
            print("Cleaned output directory")
        if os.path.exists(f"{self.project}/Builds"):
            shutil.rmtree(f"{self.project}/Builds")
            print("Cleaned Builds")
        if os.path.exists(f"{self.project}/Assets/Evaluation") and os.path.exists(f"{self.project}/Assets/Editor/AutoInstallNavMesh.cs") and os.path.exists(f"{self.project}/Assets/Editor/AutoInstallNavMesh.cs.meta"):
            shutil.rmtree(f"{self.project}/Assets/Evaluation")
            os.remove(f"{self.project}/Assets/Editor/AutoInstallNavMesh.cs")
            os.remove(f"{self.project}/Assets/Editor/AutoInstallNavMesh.cs.meta")
            print("Cleaned Scripts")
        for f in self.project.glob("*.log"):
            f.unlink()

    def setup_gt(self):
        with open(self.gt_dir, "r") as f:
            gt_cases = json.load(f)

        gt_case = gt_cases[self.case_idx-1]

        scenes = {}
        for idx, scene in gt_case[f"case_{self.case_idx}"]["details"].items():
            scenes[scene["scene_type"]] = int(idx)-1
        self.length = len(scenes)

        for edge in gt_case["transition"]["transition_graph"]:
            self.gt_transitions.append({
                "type": edge["type"],
                "from": scenes[edge["from"]],
                "to": scenes[edge["to"]]
            })

    def gt_reformat(self):
        grouped = defaultdict(list)

        for edge in self.gt_transitions:
            f, t = edge["from"], edge["to"]
            key = tuple(sorted([f, t]))

            grouped[key].append(edge["type"])

        return [
            {"from": f, "to": t, "types": types}
            for (f, t), types in grouped.items()
        ]
    
    def setup_unity_scripts(self):
        self.eval_dir.mkdir(parents=True, exist_ok=True)
        for fname, content in EVAL_FILES.items():
            if fname == "AutoInstallNavMesh.cs":
                continue
            else:
                target = self.eval_dir / fname
            target.write_text(content, encoding="utf-8")
            print("[OK] Wrote", target)


    def nav_and_build(self):
        target = self.assets / "Editor" / "AutoInstallNavMesh.cs"
        target.write_text(EVAL_FILES["AutoInstallNavMesh.cs"], encoding="utf-8")
        print("[OK] Wrote", target)
        print("\n=== Installing NavMesh ===")
        self.run(self.unity_cmd("AutoInstallNavMesh.Install"))
        self.run([
            "Unity",
            "-batchmode",
            "-quit",
            "-projectPath", str(self.project),
            "-logFile", "-"
        ])
        self.setup_unity_scripts()
        print("\n=== Baking NavMesh ===")
        for f in self.project.glob("Assets/NavMesh_*.asset"):
            os.remove(f)
        self.run(self.unity_cmd("AutoBakeNavMesh.Bake"))
        print("\n=== Building Evaluator ===")
        self.run(self.unity_cmd("BuildEval.Build"))

    def resolve_executable(self):
        build_dir = self.project / "Builds" / "EvalBuilds"
        build_dir.mkdir(parents=True, exist_ok=True)
        system = platform.system()

        if system == "Darwin":
            app = next(build_dir.glob("*.app"))
            exe = next((app / "Contents" / "MacOS").iterdir())
            self.exe_cmd = [str(exe)]
        elif system == "Windows":
            exe = next(build_dir.glob("*.exe"))
            self.exe_cmd = [str(exe)]
        else:
            exe = next(build_dir.glob("*x86_64"))
            self.exe_cmd = [str(exe)]

    def run_locate(self, mode, version, idx):
        print(f"\n=== {version.upper()}: {mode.upper()} ===")

        self.run(
            self.exe_cmd
            + [
                "-batchmode",
                "-eval",
                "-mode",
                mode,
                "-version",
                version,
                "-out",
                str(self.scene_dir),
                "-idx",
                str(idx),
                "-logFile",
                str(self.project / f"{version}_{mode}_{idx}.log")
            ]
        )

    def run_capture(self, version, idx):
        print(f"\n=== {version.upper()}: ORBIT CAPTURE ===")

        self.run(
            self.exe_cmd
            + [
                "-batchmode",
                "-orbitCapture",
                "-results",
                str(self.scene_dir / f"portals_results_{self.version}.json"),
                "-out",
                str(self.scene_dir / "portals"),
                "-idx",
                str(idx),
                "-logFile",
                "-"
            ]
        )

    def analyze_portals(self, version, idx):
        print(f"\n=== {version.upper()}: ANALYZE ===")
        result_dir = (self.scene_dir / f"portals_results_{version}.json")
        with open(result_dir, "r", encoding="utf-8-sig") as f:
            portals = json.load(f)

        config = load_yaml(self.config_dir, replace_env_var=True)
        magic_config = MagicConfig(**{**config.get("magic", {})})
        llm_bag = {str(k): LlmConfig(**v, max_retries=magic_config.max_retries) for k, v in config["llm"].items()}

        pred_transitions = portals["portals"]
        gt_transitions = self.gt_reformat()
        print(gt_transitions)

        for gt_transition in gt_transitions:
            if gt_transition["from"] == idx:
                goal = gt_transition["to"]
            elif gt_transition["to"] == idx:
                goal = gt_transition["from"]
            else:
                continue
            
            gt_leftover = gt_transition["types"].copy()
            pred_leftover = []

            if (len(gt_leftover) == 1):
                for portal in pred_transitions:
                    if not portal["transitionOccurred"]:
                        continue
                    dest = int(portal["destinationScene"].split("_")[-1])
                    if not (dest == goal):
                        continue

                    if version == "ab2":
                        p_name = portal.get("name")
                        naming_res = portal_analyzer(
                            version=version,
                            portal=gt_leftover[0],
                            p_name=p_name,
                            llm_bag=llm_bag
                        )
                        portal["naming_analysis"] = naming_res
                    else:
                        img_dir = (self.scene_dir / "portals") / f"{portal['id']:03}_{portal['name']}"
                        if not img_dir.exists():
                            print("[WARN] portal images missing:", img_dir)
                            continue
                        img_res = portal_analyzer(
                            version=version,
                            portal=gt_leftover[0],
                            img_path=str(img_dir),
                            llm_bag=llm_bag
                        )            
                        portal["vision_analysis"] = img_res
                continue

            
            for portal in pred_transitions[:]:
                if not portal["transitionOccurred"]:
                    continue
                dest = int(portal["destinationScene"].split("_")[-1])
                if not (dest == goal):
                    continue

                if len(gt_leftover) == 0:
                    pred_leftover.append(portal)
                    pred_transitions.remove(portal)
                    continue

                flag = False

                for gt_portal in gt_leftover:
                    if version == "ab2":
                        p_name = portal.get("name")
                        naming_res = portal_analyzer(
                            version=version,
                            portal=gt_portal,
                            p_name=p_name,
                            llm_bag=llm_bag
                        )
                        portal["naming_analysis"] = naming_res
                        if naming_res["match"]:
                            gt_leftover.remove(gt_portal)
                            flag = True
                            break
                    else:
                        img_dir = (self.scene_dir / "portals") / f"{portal['id']:03}_{portal['name']}"
                        if not img_dir.exists():
                            print("[WARN] portal images missing:", img_dir)
                            continue
                        img_res = portal_analyzer(
                            version=version,
                            portal=gt_portal,
                            img_path=str(img_dir),
                            llm_bag=llm_bag
                        )
                        portal["vision_analysis"] = img_res
                        if img_res["match"]:
                            gt_leftover.remove(gt_portal)
                            flag = True
                            break
                if not flag:
                    pred_leftover.append(portal)
                    pred_transitions.remove(portal)
            
            if len(gt_leftover) == 0:
                gt_leftover = gt_transition["types"].copy()

            if len(pred_leftover) > 0:
                data_leftover = []
                for portal in pred_leftover:
                    if version == "ab2":
                        data_leftover.append(portal["name"])
                    else:
                        data_leftover.append(f"{self.scene_dir}/portals/{portal['id']:03}_{portal['name']}")

                leftover_match = match_leftover(
                    version=version,
                    portals=gt_leftover,
                    data=data_leftover,
                    llm_bag=llm_bag
                )
            
                for i in range(len(pred_leftover)):
                    if i < len(leftover_match):
                        if version == "ab2":
                            pred_leftover[i]["naming_analysis"] = leftover_match[i]
                        else:
                            pred_leftover[i]["vision_analysis"] = leftover_match[i]
                        pred_transitions.append(pred_leftover[i])

        portals["portals"] = pred_transitions
        with open(result_dir, "w", encoding="utf-8") as f:
            json.dump(portals, f, indent=2)

        print(f"\n[OK] Portal analysis results written to portals_results_{self.version}.json")
        return pred_transitions

    def gen_report(self):
        print("\n=== REPORT ===")
        out_dir = self.out_dir

        gt_meta = []
        for trans in self.gt_transitions:
            gt_meta.append({
                    "from": trans.get("from"),
                    "to": trans.get("to"),
                    "portal": trans.get("type"),
                    "is_match": 0
                })
            gt_meta.append({
                    "from": trans.get("to"),
                    "to": trans.get("from"),
                    "portal": trans.get("type"),
                    "is_match": 0
                })
        gt_total = len(gt_meta)
        gt_pool = gt_meta.copy()

        # load agent scene graph
        agent_meta = []
        agent_total = 0
        match = []
        miss = []
        extra = []
        n_approached = 0
        p_match = 0

        for idx in range(self.length):
            scene_root = out_dir / f"scene_{idx}"
            pr_path = scene_root / f"portals_results_{self.version}.json"
            if not pr_path.exists():
                continue
            try:
                with open(pr_path, "r", encoding="utf-8-sig") as f:
                    pr = json.load(f)
            except Exception as e:
                print(f"[WARN] Cannot read {pr_path} ({e})")
                continue

            portals = pr.get("portals", []) or []

            for portal in portals:
                if not portal.get("transitionOccurred", False):
                    continue

                dest_name = portal.get("destinationScene")
                dest = dest_name.split("_")[-1] if dest_name else None
                if dest is None:
                    continue
                
                va = {}
                na = {}
                
                if self.version == "ab2":
                    na = portal.get("naming_analysis")
                    ptype = na.get("detected_object")
                    gttype = na.get("ground_truth")
                    is_match = na.get("match")
                    agent_confidence = na.get("confidence")
                    agent_reasoning = na.get("reasoning")
                else:
                    va = portal.get("vision_analysis")
                    if va is not None:
                        ptype = va.get("detected_object")
                        gttype = va.get("ground_truth")
                        is_match = va.get("match")
                        agent_confidence = va.get("confidence")
                        agent_reasoning = va.get("reasoning")
                    else:
                        ptype = gttype = is_match = agent_confidence = agent_reasoning = None
                new_conn = {
                    "portal_name": portal.get("name"),
                    "from": idx,
                    "to": int(dest),
                    "pred_portal": ptype if ptype is not None else "unknown",
                    "gt_portal": gttype if gttype is not None else "unknown",
                    "is_match": is_match if is_match is not None else "unknown",
                    "is_approached": portal.get("approached"),
                    "agent_confidence":  agent_confidence if agent_confidence is not None else "unknown",
                    "agent_reasoning":  agent_reasoning if agent_reasoning is not None else "unknown",
                } if va is not None else (
                    {
                        "portal_name": portal.get("name"),
                        "from": idx,
                        "to": int(dest),
                        "pred_portal": ptype if ptype is not None else "unknown",
                        "gt_portal": gttype if gttype is not None else "unknown",
                        "is_match": is_match if is_match is not None else "unknown",
                        "is_approached": portal.get("approached"),
                        "agent_confidence":  agent_confidence if agent_confidence is not None else "unknown",
                        "agent_reasoning":  agent_reasoning if agent_reasoning is not None else "unknown",
                    } if na is not None else {
                        "portal_name": portal.get("name"),
                        "from": idx,
                        "to": int(dest),
                        "is_approached": portal.get("approached"),
                    }
                )

                agent_meta.append(new_conn)
                agent_total += 1

                found = False
                for i, gt in enumerate(gt_pool):
                    if (gt["from"] == idx and gt["to"] == int(dest) and gt["portal"] == gttype):
                        gt_pool.pop(i)
                        found = True
                        if is_match and is_match != "uncertain":
                            p_match += 1
                        if portal.get("approached"):
                            n_approached += 1
                        match.append(new_conn)
                        break
                if not found:
                    extra.append(new_conn)

        num_match = len(match)
        for item in gt_pool:
            miss.append({"from": item["from"], "to": item["to"], "portal": item["portal"]})
        num_miss = len(miss)
        num_extra =len(extra)
    
        precision = num_match / (num_match + num_extra) if (num_match + num_extra) > 0 else 0.0
        recall = num_match / (num_match + num_miss) if (num_match + num_miss) > 0 else 0.0
        f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) > 0 else 0.0

        report = {
            "case_idx": self.case_idx,
            "version": self.version,
            "eval_duration": "",
            "n_scenes": self.length,
            "n_portals": {
                "expected": gt_total,
                "generated": agent_total,
                "approached": n_approached,
                "portal match": p_match,
            },
            "metrics": {
                "precision": precision,
                "recall": recall,
                "f1": f1,
                "approach rate": n_approached / num_match if num_match != 0 else 0,
                "portal rate": p_match / num_match if num_match != 0 else 0
            },
            "details": {
                "match": match,
                "miss": miss,
                "extra": extra,
            }
        }
        
        return report

    def check_scenes(self, scene_dir):
        path = scene_dir / "Assets" / "Scenes"
        scenes = sorted(Path(path).rglob("*.unity"))

        print(f"[CHECK] Found {len(scenes)} scenes")
        for s in scenes:
            print(f"  - {s}")

        if self.length is not None and len(scenes) != self.length:
            print(f"[FATAL] Scene count mismatch: expected {self.length}, got {len(scenes)}")
            sys.exit(1)

    def pipeline(self):
        t0 = time.time()
        print("\n============================")
        print("Running Evaluation Pipeline")
        print("============================")
        
        self.clean_dir()
        self.setup_gt()
        self.check_scenes(self.project)
        self.nav_and_build()
        self.resolve_executable()
        self.out_dir.mkdir(parents=True, exist_ok=True)
        for idx in range(self.length):
            print(f"\n===== SCENE {idx+1}/{self.length} =====")
            self.scene_dir = self.out_dir / f"scene_{idx}"
            self.scene_dir.mkdir(parents=True, exist_ok=True)
            self.run_locate("extract", self.version, idx)
            self.run_locate("test", self.version, idx)
            self.run_locate("move", self.version, idx)
            if self.version != "ab2":
                self.run_capture(self.version, idx)
            result = self.analyze_portals(self.version, idx)
            self.results.append(result)
        report = self.gen_report()
        report["eval_duration"] = "{0:.2f}".format(time.time() - t0)

        try:
            out_path = self.out_dir / f"eval_report_{self.version}.json"
            with open(out_path, "w", encoding="utf-8") as f:
                json.dump(report, f, ensure_ascii=False, indent=4)
            print(f"[OK] Saved report to: {out_path}")
        except Exception as e:
            print(f"[WARN] Failed to save report: {e}")

        print("\n[SUCCESS] Evaluation output:", self.out_dir)

def main():

    ap = argparse.ArgumentParser()
    ap.add_argument("-i", "--case_idx", required=True, help="Case index to evaluate (1-based)")
    ap.add_argument("-o", "--out", required=False, default="EvalOutput", help="Output directory for evaluation results")
    ap.add_argument("-c", "--config", required=False, default="configs/config.yaml", help="Path to config file for generation")
    ap.add_argument("-v", "--version", required=False, default="normal", choices=["normal", "ab1", "ab2"], help="Version of the agent to evaluate")
    ap.add_argument("-t", "--gt_dir", required=False, default="eval_agent/benchmark/gt_example.json", help="Path to ground truth JSON file")

    args = ap.parse_args()

    agent = EvalAgent(
        case_idx=args.case_idx,
        project="test_cases/case_" + args.case_idx + "/magic-outputs-combined/unity",
        out=args.out,
        config_dir=args.config,
        version=args.version,
        gt_dir=args.gt_dir
    )

    agent.pipeline()

if __name__ == "__main__":
    main()