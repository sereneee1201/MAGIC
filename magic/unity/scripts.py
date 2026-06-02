# -*- coding: utf-8 -*-

from typing import Literal

from magic.constants import PACKAGE_NAME
from magic.unity.templates import *
from magic.utils.llm import TemplateFormatter

__all__ = [
    "Vector3",
    "UnityObjects",
    "PointLights",
    "get_scene_builder_script",
    "get_camera_controller_script",
    "get_keyboard_script",
    "get_overlay_script",
    "get_bounding_box_drawer_script",
    "get_ar_demo_script",
    "get_toggle_controller_script",
    "get_level_loader_script",
    "get_transition_system_script",
]


class Vector3(object):
    def __init__(self, x: float = 0, y: float = 0, z: float = 0) -> None:
        self.x = x
        self.y = y
        self.z = z

    def __str__(self) -> str:
        return f"new Vector3({self.x}f, {self.y}f, {self.z}f)"


class UnityObjects(object):
    def __init__(self) -> None:
        self.__objects: list[tuple[str, str, str, Vector3, Vector3, Vector3]] = []

    def __str__(self) -> str:
        if len(self.__objects) == 0:
            return ""
        objects = "\n".join('        Load{}("{}", "{}", {}, {}, {});'.format(*obj) for obj in self.__objects)
        return f"\n\n{objects}"

    def add_object(
        self,
        mode: Literal["connection", "object", "room"],
        dir_name: str,
        name: str,
        position: Vector3 = Vector3(),
        rotation: Vector3 = Vector3(),
        scale: Vector3 = Vector3(),
    ) -> None:
        self.__objects.append((mode.capitalize(), dir_name, name, position, rotation, scale))


class PointLights(object):
    count = 0

    def __init__(self) -> None:
        self.__lights: list[tuple[str, Vector3, float, float]] = []

    def __str__(self) -> str:
        if len(self.__lights) == 0:
            return ""
        lights = "\n".join('        AddPointLight("{}", {}, {}, {});'.format(*uid) for uid in self.__lights)
        return f"\n\n{lights}"

    def add_light(self, position: Vector3 = Vector3(), distance: float = 5, intensity: float = 1) -> None:
        PointLights.count += 1
        self.__lights.append((f"PointLight{PointLights.count}", position, distance, intensity))


get_scene_builder_script = TemplateFormatter(
    SCENE_BUILDER_TEMPLATE,
    package_name=PACKAGE_NAME,
    camera_position="default",
    camera_look_at="default",
    ground="\nAddGround();",
    objects="",
    point_lights="",
    scene_idx=""
)
get_camera_controller_script = TemplateFormatter(CAMERA_CONTROLLER_TEMPLATE, move_speed=3, mouse_sensitivity=3)
get_keyboard_script = TemplateFormatter(KEYBOARD_TEMPLATE, package_name=PACKAGE_NAME)
get_overlay_script = TemplateFormatter(OVERLAY_TEMPLATE)
get_bounding_box_drawer_script = TemplateFormatter(BOUNDING_BOX_DRAWER_TEMPLATE)
get_ar_demo_script = TemplateFormatter(AR_DEMO_TEMPLATE)
get_toggle_controller_script = TemplateFormatter(TOGGLE_CONTROLLER_TEMPLATE, scene_idx="")
get_level_loader_script = TemplateFormatter(LEVEL_LOADER_TEMPLATE)
get_transition_system_script = TemplateFormatter(TRANSITION_SYSTEM_TEMPLATE)