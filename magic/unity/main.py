# -*- coding: utf-8 -*-

import shutil
import json
import os
from os import makedirs
from os.path import dirname, join, exists

from termcolor import colored

from magic.generation import MagicConfig, MagicLog
from magic.object.qem import qem
from magic.unity import build_scene, has_unity
from magic.unity.scripts import *
from magic.utils.file import get_available_path, load_json
from magic.utils.misc import Timer, parse_cli_kwargs, tsprint


class MagicUnity(object):
    def __init__(self, config: MagicConfig, scene_idx: str, exit_portals: str) -> None:
        if not has_unity():
            raise RuntimeError("Failed to locate Unity")
        self.__config = config
        self.scene_idx = scene_idx
        self.exit_info = json.loads(exit_portals)

    def __call__(self, log: MagicLog) -> None:
        with Timer() as timer:
            # create directories
            unity_dir = join(log.output_dir, "unity")

            if os.path.exists(unity_dir):
                shutil.rmtree(unity_dir)

            os.makedirs(unity_dir)

            assets_dir = join(unity_dir, "Assets")
            scripts_dir = join(assets_dir, "Scripts")
            models_dir = join(assets_dir, "Models")

            makedirs(scripts_dir)
            makedirs(models_dir)

            # copy acquired entities
            unity_objects = UnityObjects()
            for rname, region in log.meshes["regions"].items():
                for key, path in region.items():
                    name = f"r-{rname}-{key}"
                    entity_dir = join(models_dir, name)
                    shutil.copytree(dirname(path), entity_dir)
                    unity_objects.add_object("room", name, name, rotation=Vector3(y=180))
                for oname, obj in log.meshes["objects"][rname].items():
                    name = f"o-{rname}-{oname}"
                    entity_dir = join(models_dir, name)
                    shutil.copytree(dirname(obj["path"]), entity_dir)
                    unity_objects.add_object(
                        "object",
                        name,
                        name,
                        Vector3(
                            log.scene.regions[rname].objects[oname].position[-1].x,
                            log.scene.regions[rname].objects[oname].position[-1].y,
                            log.scene.regions[rname].objects[oname].position[-1].z,
                        ),
                        Vector3(
                            log.scene.regions[rname].objects[oname].rotation[-1].x,
                            log.scene.regions[rname].objects[oname].rotation[-1].y,
                            log.scene.regions[rname].objects[oname].rotation[-1].z,
                        ),
                        Vector3(
                            log.scene.regions[rname].objects[oname].dimensions.width,
                            log.scene.regions[rname].objects[oname].dimensions.height,
                            log.scene.regions[rname].objects[oname].dimensions.depth,
                        ),
                    )
            if "connections" in log.meshes:
                for cname, conn in log.meshes["connections"].items():
                    rname = log.scene.connections[cname].region_a
                    name = f"c-{rname}-{cname}"
                    entity_dir = join(models_dir, name)
                    shutil.copytree(dirname(conn["path"]), entity_dir)
                    unity_objects.add_object(
                        "connection",
                        name,
                        name,
                        Vector3(
                            log.scene.connections[cname].obj.position[-1].x,
                            log.scene.connections[cname].obj.position[-1].y,
                            log.scene.connections[cname].obj.position[-1].z,
                        ),
                        Vector3(
                            log.scene.connections[cname].obj.rotation[-1].x,
                            log.scene.connections[cname].obj.rotation[-1].y,
                            log.scene.connections[cname].obj.rotation[-1].z,
                        ),
                        Vector3(
                            log.scene.connections[cname].obj.dimensions.width,
                            log.scene.connections[cname].obj.dimensions.height,
                            log.scene.connections[cname].obj.dimensions.depth,
                        ),
                    )

            # add point lights
            point_lights = PointLights()
            for region in log.scene.regions.values():
                for light in region.lights:
                    point_lights.add_light(Vector3(light.x, light.y, light.z))

            # write Unity scripts
            scene_idx = self.scene_idx
            exit_portals = []
            destinations = []
            effects = []
            exit_names = []
            
            for portal in self.exit_info: # portal, dest_idx, effect
                exit_portals.append(portal[0])
                exit_names.append(portal[0].split("-")[-1])
                destinations.append(portal[1])
                effects.append(portal[2])
            exit_portals = "{\"" + "\", \"".join(map(str, exit_portals)) + "\"}"
            exit_names = "{" + ", ".join(f'"{name}"' for name in exit_names) + "}"
            destinations = "{" + ", ".join(map(str, destinations)) + "}"
            effects = "{" + ", ".join(map(str, effects)) + "}"

            if self.config.verbose:
                tsprint(
                    colored(f"[{self.__class__.__name__}]", color="blue", attrs=["bold"]),
                    "Writing Unity scripts\n",
                )
            filename_sb = f"SceneBuilder_{scene_idx}.cs"
            with open(join(scripts_dir, filename_sb), "w") as f:
                f.write(get_scene_builder_script(ground="", objects=unity_objects, point_lights=point_lights, scene_idx=scene_idx, exit_portals=exit_portals, destinations=destinations, exit_names=exit_names))
            filename_cc = f"CameraController_{scene_idx}.cs"
            with open(join(scripts_dir, filename_cc), "w") as f:
                f.write(get_camera_controller_script(scene_idx=scene_idx))
            filename_k = f"Keyboard_{scene_idx}.cs"
            with open(join(scripts_dir, filename_k), "w") as f:
                f.write(get_keyboard_script(scene_idx=scene_idx))
            filename_o = f"Overlay_{scene_idx}.cs"
            with open(join(scripts_dir, filename_o), "w") as f:
                f.write(get_overlay_script(scene_idx=scene_idx))
            filename_bbd = f"BoundingBoxDrawer_{scene_idx}.cs"
            with open(join(scripts_dir, filename_bbd), "w") as f:
                f.write(get_bounding_box_drawer_script(scene_idx=scene_idx))
            filename_ard = f"ARDemo_{scene_idx}.cs"
            with open(join(scripts_dir, filename_ard), "w") as f:
                f.write(get_ar_demo_script(scene_idx=scene_idx))
            filename_tc = f"ToggleController_{scene_idx}.cs"
            with open(join(scripts_dir, filename_tc), "w") as f:
                f.write(get_toggle_controller_script(scene_idx=scene_idx))
            for portal, dest_idx, effect_type in self.exit_info:
                name = portal.split("-")[-1]
                filename_ll = f"LevelLoader_{name}_{scene_idx}_{dest_idx}.cs"
                with open(join(scripts_dir, filename_ll), "w") as f:
                    f.write(get_level_loader_script(scene_idx=scene_idx, dest_idx=dest_idx, effect_type=effect_type, name=name))
            filename_ts = f"TransitionSystem.cs"
            with open(join(scripts_dir, filename_ts), "w") as f:
                f.write(get_transition_system_script())

            if self.config.verbose:
                tsprint(
                    colored(f"[{self.__class__.__name__}]", color="blue", attrs=["bold"]),
                    "Building Unity scene\n",
                )
            build_scene(unity_dir, scene_idx, verbose=self.config.verbose)
            if self.config.verbose:
                tsprint(
                    colored(f"[{self.__class__.__name__}]", color="blue", attrs=["bold"]),
                    f"Unity project has been created in {unity_dir}.",
                    f"You can find a playable executable in {join(unity_dir, 'Builds')}.\n",
                )

            log.duration["unity_generation"] = timer.get()
            log.save()

    @property
    def config(self) -> MagicConfig:
        return self.__config


def _cli() -> None:
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("-l", "--log", type=str, required=True, help="Path to a JSON log file.")
    parser.add_argument("-i", "--index", type=str, required=True, help="Index of the scene.")
    parser.add_argument("-e", "--exit", type=str, required=True, help="The exit portals of the scene.")
    parser.add_argument("--kwarg", action="append", type=str, default=None, help="Additional keyword argument.")
    args = parser.parse_args()

    log = MagicLog(**load_json(path=args.log))
    unity = MagicUnity(MagicConfig(**{**log.config.model_dump(), **parse_cli_kwargs(args.kwarg)}), scene_idx=args.index, exit_portals=args.exit)
    unity(log)


if __name__ == "__main__":
    _cli()
