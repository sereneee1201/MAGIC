import shutil
import sys
import subprocess

from pathlib import Path

CI_TEMPLATE = """#if UNITY_EDITOR
using System;
using System.IO;
using System.Linq;
using UnityEditor;
using UnityEditor.Build.Reporting;
using UnityEngine;

public static class BuildCi
{{
    public static void Run()
    {{
        try
        {{
            // Resolve all scenes under Assets/Scenes
            var scenes = AssetDatabase.FindAssets("t:Scene")
                .Select(AssetDatabase.GUIDToAssetPath)
                .Where(p => p.StartsWith("Assets/Scenes", StringComparison.OrdinalIgnoreCase)
                         && p.EndsWith(".unity", StringComparison.OrdinalIgnoreCase))
                .OrderBy(p => p)
                .ToArray();

            if (scenes.Length == 0)
            {{
                Debug.LogError("[CI] No scenes found under Assets/Scenes.");
                EditorApplication.Exit(1);
                return;
            }}

            // Write effective list for the Player
            EditorBuildSettings.scenes = scenes.Select(p => new EditorBuildSettingsScene(p, true)).ToArray();

            // Target/platform selection
            string targetArg = GetArg("-target", "");
            var (target, buildPath) = ResolveTargetAndPath(targetArg);
            if (target == BuildTarget.NoTarget)
            {{
                // Fallback: infer from Editor OS
                if (Application.platform == RuntimePlatform.OSXEditor)
                {{ target = BuildTarget.StandaloneOSX; buildPath = "Builds/gameworld.app"; }}
                else if (Application.platform == RuntimePlatform.WindowsEditor)
                {{ target = BuildTarget.StandaloneWindows64; buildPath = "Builds/gameworld.exe"; }}
                else if (Application.platform == RuntimePlatform.LinuxEditor)
                {{ target = BuildTarget.StandaloneLinux64; buildPath = "Builds/gameworld.x86_64"; }}
                else
                {{ Debug.LogError($"[CI] Unsupported editor platform: {{Application.platform}}"); EditorApplication.Exit(1); return; }}
            }}

            // Switch target if needed
            var group = BuildPipeline.GetBuildTargetGroup(target);
            if (EditorUserBuildSettings.activeBuildTarget != target)
            {{
                if (!EditorUserBuildSettings.SwitchActiveBuildTarget(group, target))
                {{
                    Debug.LogError($"[CI] Failed to switch active build target to {{target}}");
                    EditorApplication.Exit(1);
                    return;
                }}
            }}

            Directory.CreateDirectory("Builds");
            var opts = new BuildPlayerOptions
            {{
                scenes = scenes,
                locationPathName = buildPath,
                target = target,
                options = BuildOptions.None
            }};

            var report = BuildPipeline.BuildPlayer(opts);
            var summary = report.summary;

            if (summary.result == BuildResult.Succeeded)
            {{
                Debug.Log($"[CI] Build succeeded: {{buildPath}}");
                EditorApplication.Exit(0);
            }}
            else
            {{
                Debug.LogError($"[CI] Build failed: {{summary.result}} | Errors: {{summary.totalErrors}}, Warnings: {{summary.totalWarnings}}");
                EditorApplication.Exit(1);
            }}
        }}
        catch (Exception ex)
        {{
            Debug.LogError($"[CI] Exception: {{ex}}");
            EditorApplication.Exit(1);
        }}
    }}

    private static (BuildTarget target, string path) ResolveTargetAndPath(string arg)
    {{
        string output = "Builds";
        string product = "gameworld";
        switch ((arg ?? "").Trim().ToLowerInvariant())
        {{
            case "win64": case "windows64": case "standalonewindows64":
                return (BuildTarget.StandaloneWindows64, Path.Combine(output, $"{{product}}.exe"));
            case "osx": case "mac": case "standaloneosx":
                return (BuildTarget.StandaloneOSX, Path.Combine(output, $"{{product}}.app"));
            case "linux": case "linux64": case "standalonelinux64":
                return (BuildTarget.StandaloneLinux64, Path.Combine(output, $"{{product}}.x86_64"));
            default:
                return (BuildTarget.NoTarget, "");
        }}
    }}

    private static string GetArg(string name, string defaultValue)
    {{
        var args = Environment.GetCommandLineArgs();
        for (int i = 0; i < args.Length; i++)
            if (args[i].Equals(name, StringComparison.OrdinalIgnoreCase) && i + 1 < args.Length)
                return args[i + 1];
        return defaultValue;
    }}
}}
#endif
"""

def combine_unity_outputs(output_dir=""):
    # define paths
    base = Path(output_dir)
    source_dir = base / "magic-outputs"
    dest_dir   = base / "magic-outputs-combined"
    unity_dir = dest_dir / "unity"
    
    # create empty destination directory
    if dest_dir.exists():
        shutil.rmtree(dest_dir)
    dest_dir.mkdir(exist_ok=True)
    unity_dir.mkdir(exist_ok=True)
    
    # track copied assets for Models/Scripts
    copied_assets = {
        "Models": set(),
        "Scripts": set()
    }
    
    # first pass: Copy all non-Assets content (except Builds/.log files)
    for gen_folder in source_dir.glob("magic_*"):

        output_file = next(gen_folder.glob("output*"), None)
        if output_file:
            shutil.copy2(output_file, dest_dir / output_file.name)

        unity_source = gen_folder / "unity"
        if not unity_source.exists():
            continue
        
        print(f"Processing {gen_folder.name}...")
        
        # copy all non-Assets content first
        for item in unity_source.iterdir():
            # skip Builds folder and .log files
            if item.name == "Builds" or item.suffix == ".log":
                continue
                
            # skip Assets (we'll handle separately)
            if item.name == "Assets":
                continue
            
            dest_path = unity_dir / item.name
            
            # if it's a file, copy it
            if item.is_file():
                shutil.copy2(item, dest_path)
            # if it's a directory, merge contents
            elif item.is_dir():
                if dest_path.exists():
                    shutil.copytree(item, dest_path, dirs_exist_ok=True)
                else:
                    shutil.copytree(item, dest_path)

    # second pass: Merge Assets folders
    assets_dir = unity_dir / "Assets"
    assets_dir.mkdir(exist_ok=True)
    for subfolder in ["Models", "Scenes", "Scripts", "Editor"]:
        (assets_dir / subfolder).mkdir(exist_ok=True)
    
    for gen_folder in source_dir.glob("magic_*"):
        unity_source = gen_folder / "unity"
        assets_source = unity_source / "Assets"
        if not assets_source.exists():
            continue
            
        # process each asset type
        for asset_type in ["Models", "Scenes", "Scripts"]:
            source_folder = assets_source / asset_type
            if not source_folder.exists():
                continue
                
            dest_folder = assets_dir / asset_type
            
            if asset_type == "Scenes":
                # copy all scene files
                for item in source_folder.iterdir():
                    dest_path = dest_folder / item.name
                    if item.is_file():
                        shutil.copy2(item, dest_path)
                    elif item.is_dir():
                        shutil.copytree(item, dest_path, dirs_exist_ok=True)
            else:
                # only copy new Models/Scripts
                for item in source_folder.iterdir():
                    if item.name not in copied_assets[asset_type]:
                        dest_path = dest_folder / item.name
                        if item.is_file():
                            shutil.copy2(item, dest_path)
                        elif item.is_dir():
                            shutil.copytree(item, dest_path, dirs_exist_ok=True)
                        copied_assets[asset_type].add(item.name)

    # create BuildCi.cs in Assets/Editor
    editor_dir = assets_dir / "Editor"
    ci_path = editor_dir / "BuildCi.cs"
    with open(ci_path, "w", encoding="utf-8") as f:
        f.write(CI_TEMPLATE.format())

    print(f"\nCombined outputs saved to: {dest_dir}")