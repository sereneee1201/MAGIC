# -*- coding: utf-8 -*-

from importlib import import_module
from itertools import product
from pathlib import Path
from typing import Any, Optional
from uuid import uuid4

from termcolor import colored
from tqdm import tqdm

from magic.blender import brender, has_blender
from magic.generation import MagicConfig, MagicLog
from magic.generation.modules import CONNECTION_THICKNESS
from magic.holodeck.material_selector import MaterialSelector
from magic.models.clip import OpenClip
from magic.object.base import ObjectAcquirer
from magic.object.objgen.base import ObjectGenerator
from magic.object.objrtv.base import ObjectRetriever
from magic.object.rotation import correct_rotation_with_vlm
from magic.utils.dtypes import PathLike, SDict
from magic.utils.llm import Llm
from magic.utils.misc import Timer, tsprint


class MagicComposition(object):
    def __init__(self, config: MagicConfig, vlm: Llm, clip: OpenClip, device: Optional[str] = None) -> None:
        if not has_blender():
            raise RuntimeError("Blender is not installed or not found in the system path")
        device = "cpu" if device is None else device
        self.__config = config
        self.__objrtv: Optional[ObjectRetriever] = None
        if config.obj_retriever is not None:
            self.__objrtv = self.__import_object_acquirer(config.obj_retriever)(
                detect_rot=correct_rotation_with_vlm(vlm), device=device
            )
            if not isinstance(self.__objrtv, ObjectRetriever):
                raise TypeError(f"`config.obj_retriever` must be a subclass of ObjectRetriever")
        self.__objgen: Optional[ObjectGenerator] = None
        if config.obj_generator is not None:
            self.__objgen = self.__import_object_acquirer(config.obj_generator)(
                detect_rot=correct_rotation_with_vlm(vlm), device=device
            )
            if not isinstance(self.__objgen, ObjectGenerator):
                raise TypeError(f"`config.obj_generator` must be a subclass of ObjectGenerator")
        self.__mat_selector = MaterialSelector(clip=clip)

    def __call__(self, log: MagicLog) -> None:
        tsprint(colored("Module:", color="blue", attrs=["bold"]), "Composition\n")
        with Timer() as timer:
            scene = log.scene
            if scene is None:
                raise ValueError("The input log does not contain a scene")
            log.meshes.clear()
            log.save()
            for region_name in tqdm(scene.regions.keys(), desc="Regions"):
                region_uid = self.__compose_region(log, region_name)
                self.__compose_region_objects(log, region_name, region_uid)
            self.__compose_connections(log)
            log.duration["object_acquisition"] = timer.get()
            log.save()

    def __import_object_acquirer(self, name: str) -> type[ObjectAcquirer]:
        module, cls = name.rsplit(".", 1)
        acquirer = getattr(import_module(module), cls)
        if not issubclass(acquirer, ObjectAcquirer):
            raise TypeError(f'"{name}" should be a subclass of ObjectAcquirer')
        return acquirer

    def __compose_region(self, log: MagicLog, region_name: str) -> str:
        scene = log.scene
        region = scene.regions[region_name]
        region_uid = uuid4().hex
        region_dir = log.output_dir / "meshes" / "regions" / region_uid
        floor_prompt = f"a {region.floor.color} floor made of {region.floor.material}"
        if region.floor.attributes.strip() != "":
            floor_prompt += f" that is {region.floor.attributes}"
        floor_albedo = self.__mat_selector(floor_prompt)
        floor_path = region_dir / "floor" / "mesh.obj"
        shape = region.shape
        codes = [
            "clear()",
            "builder = Builder()",
            "region = builder.new_cube()",
            "builder.create_uv(region)",
            "builder.map_faces_to_full_uv(region)",
            f"transform(region, position=({shape.shifted_center.x}, {shape.shifted_center.y}, {shape.height / 2 if scene.is_indoor else 0.5}), scale=({shape.width}, {shape.depth}, {shape.height if scene.is_indoor else 1.0}))",
            "floor, non_floor = builder.separate_bottom(region, 0.0)",
            f'builder.add_material(floor, albedo_path=r"{floor_albedo}", roughness={region.floor.roughness}, metallic={region.floor.metallic})',
        ]
        if scene.is_indoor:
            wall_prompt = f"a {region.wall.color} wall made of {region.wall.material}"
            if region.wall.attributes.strip() != "":
                wall_prompt += f" that is {region.wall.attributes}"
            wall_albedo = self.__mat_selector(wall_prompt)
            non_floor_path = region_dir / "non_floor" / "mesh.obj"
            wall_path = region_dir / "wall" / "mesh.obj"
            codes.append(
                f'builder.add_material(non_floor, albedo_path=r"{wall_albedo}", roughness={region.wall.roughness}, metallic={region.wall.metallic})'
            )
            codes.append(f"_, wall = builder.separate_top(non_floor, {shape.height})")
        codes.append(f"builder.solidify(floor, thickness={CONNECTION_THICKNESS / 2})")
        if scene.is_indoor:
            codes.append(f"builder.solidify(non_floor, thickness={CONNECTION_THICKNESS / 2})")
            codes.append(f"builder.solidify(wall, thickness={CONNECTION_THICKNESS / 2})")
            for idx, conn in enumerate(scene.get_connections_to_region(region_name).values(), start=1):
                pos_x, pos_y, pos_z = conn.obj.position[-1].model_dump().values()
                rot_x, rot_y, rot_z = conn.obj.rotation[-1].model_dump().values()
                width, height, depth = conn.obj.dimensions.model_dump().values()
                codes.append(f"conn{idx} = builder.new_cube()")
                codes.append(
                    f"transform(conn{idx}, position=({pos_x + conn.shifts.x}, {pos_z + conn.shifts.y}, {pos_y}), rotation=({-rot_x}, {-rot_z}, {-rot_y}), scale=({width}, {depth * 1.01}, {height}))"
                )
                codes.append(f'non_floor = builder.modify_boolean("DIFFERENCE", non_floor, conn{idx})')
                codes.append(f'wall = builder.modify_boolean("DIFFERENCE", wall, conn{idx})')
        codes.append(f'if not export_obj(r"{floor_path}", obj=floor): raise RuntimeError()')
        if scene.is_indoor:
            codes.append(f'if not export_obj(r"{non_floor_path}", obj=non_floor): raise RuntimeError()')
            codes.append(f'if not export_obj(r"{wall_path}", obj=wall): raise RuntimeError()')
        brender(*codes, verbose=False)
        if scene.is_indoor:
            log.add_region_mesh(region_name, floor_path, non_floor_path=non_floor_path, wall_path=wall_path)
        else:
            log.add_region_mesh(region_name, floor_path)
        log.save()
        return region_uid

    def __acquire_object(self, query: str, output_obj: PathLike, **kwargs) -> tuple[bool, SDict[Any]]:
        query = f"a 3D model of {query}"
        obj_ok = False
        if self.__objrtv is not None:
            obj_ok, extra = self.__objrtv(query, str(output_obj), **{**kwargs, **self.config.obj_retriever_kwargs})
        if not obj_ok:
            if self.__objgen is None:
                tsprint("Failed to retrieve object for query:", query)
                return obj_ok, extra
            obj_ok, extra = self.__objgen(query, str(output_obj), **{**kwargs, **self.config.obj_generator_kwargs})
        if not obj_ok:
            tsprint("Failed to acquire object for query:", query)
        return obj_ok, extra

    def __compose_region_objects(self, log: MagicLog, region_name: str, region_uid: str) -> None:
        objects_dir = log.output_dir / "meshes" / "objects" / region_uid
        query2path: SDict[Path] = {}
        extras: dict[Path, SDict[Any]] = {}
        for obj_name, obj in tqdm(log.scene.regions[region_name].objects.items(), desc=region_name, leave=False):
            if obj_name in log.meshes.get("objects", {}).get(region_name, {}):
                continue
            query = obj.get_textual_description(with_dims=False)
            obj_path = query2path.get(query, None)
            if obj_path is None:
                obj_path = objects_dir / uuid4().hex / "mesh.obj"
                is_acquired, extra = self.__acquire_object(
                    query, obj_path, roughness=obj.description.roughness, metallic=obj.description.metallic
                )
                if not is_acquired:
                    continue
                query2path[query] = obj_path
                extras[obj_path] = extra
            log.add_object_mesh(region_name, obj_name, query, obj_path, **extras[obj_path])
            log.save()

    def __compose_connections(self, log: MagicLog) -> None:
        conns_dir = log.output_dir / "meshes" / "connections"
        query2path: SDict[Path] = {}
        extras: dict[Path, SDict[Any]] = {}
        for conn_name, conn in tqdm(log.scene.connections.items(), desc="Connections"):
            if "open" in conn.obj.category.lower():
                continue
            query = conn.obj.get_textual_description(with_dims=False)
            obj_path = query2path.get(query, None)
            if obj_path is None:
                obj_path = conns_dir / uuid4().hex / "mesh.obj"
                is_acquired, extra = self.__acquire_object(
                    query, obj_path, roughness=conn.obj.description.roughness, metallic=conn.obj.description.metallic
                )
                if not is_acquired:
                    continue
                query2path[query] = obj_path
                extras[obj_path] = extra
            log.add_connection_mesh(conn_name, query, obj_path, **extras[obj_path])
            log.save()

    @staticmethod
    def export_scenes(log: MagicLog) -> None:
        scene = log.scene
        n_sols = len(list(list(scene.regions.values())[0].objects.values())[0].position)
        sol_indexes = (-1,) if n_sols == 1 else (0, -1)
        for sol in sol_indexes:
            combined_path = log.output_dir / "scene" / ("first" if sol == 0 else "last") / "scene.obj"
            codes = ["clear()"]
            for region_name, paths_dict in log.meshes.get("regions", {}).items():
                floor_path = paths_dict["floor"]
                codes.append(f'import_obj(r"{floor_path}")')
                wall_path = paths_dict.get("wall", None)
                if wall_path is not None:
                    codes.append(f'import_obj(r"{wall_path}")')
            for i, (region_name, obj2path) in enumerate(log.meshes.get("objects", {}).items()):
                for j, (obj_name, obj_dict) in enumerate(obj2path.items(), start=1):
                    obj_path = obj_dict["path"]
                    dims = scene.regions[region_name].objects[obj_name].dimensions
                    pos = scene.regions[region_name].objects[obj_name].position[sol]
                    pos.x += scene.regions[region_name].shape.shifts.x
                    pos.z += scene.regions[region_name].shape.shifts.y
                    rot = scene.regions[region_name].objects[obj_name].rotation[sol]
                    codes.append(f'obj{i}_{j} = import_obj(r"{obj_path}")')
                    codes.append(
                        f"transform(obj{i}_{j}, position=({pos.x}, {pos.z}, {pos.y}), rotation=({-rot.x}, {-rot.z}, {-rot.y}), scale=({dims.width}, {dims.depth}, {dims.height}))"
                    )
            for i, (conn_name, conn_dict) in enumerate(log.meshes.get("connections", {}).items(), start=1):
                conn_path = conn_dict["path"]
                dims = scene.connections[conn_name].obj.dimensions
                pos = scene.connections[conn_name].obj.position[sol]
                rot = scene.connections[conn_name].obj.rotation[sol]
                codes.append(f'conn{i} = import_obj(r"{conn_path}")')
                codes.append(
                    f"transform(conn{i}, position=({pos.x + scene.connections[conn_name].shifts.x}, {pos.z + scene.connections[conn_name].shifts.y}, {pos.y}), rotation=({-rot.x}, {-rot.z}, {-rot.y}), scale=({dims.width}, {dims.depth}, {dims.height}))"
                )
            codes.append(f'if not export_obj(r"{combined_path}"): raise RuntimeError()')
            brender(*codes, verbose=False)

    @staticmethod
    def render(log: MagicLog) -> None:
        tsprint(colored("Module:", color="blue", attrs=["bold"]), "Rendering\n")
        for sol in (-1,):  # only render the last solution because lights are positioned based on the last solution
            combined_path = log.output_dir / "scene" / ("first" if sol == 0 else "last") / "scene.obj"
            codes = ["clear()", "renderer = Renderer(exposure=2.0)", f'import_obj(r"{combined_path}")']
            for region_name in log.scene.regions:
                for light in log.scene.regions[region_name].lights:
                    codes.append(f"renderer.add_point_light(position=({light.x}, {light.z}, {light.y}))")
            # codes.append("renderer.add_sun_light(use_shadow=False)")
            codes.append("center, radius = renderer.compute_bounding_sphere()")
            for pitch, yaw in product(range(0, 31, 30), range(0, 360, 30)):
                render_path = log.renders_dir / ("first" if sol == 0 else "last") / f"render_{pitch}-0-{yaw}.png"
                codes.append(
                    f'renderer.render_perspective(r"{render_path}", center, radius=radius, rotation=({pitch}, 0, {yaw}), resolution=1024)'
                )
            brender(*codes, verbose=False)

    @property
    def config(self) -> MagicConfig:
        return self.__config
