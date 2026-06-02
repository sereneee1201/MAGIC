# -*- coding: utf-8 -*-

from magic.generation import (
    AnticipatedObject,
    Connection,
    Dimensions3D,
    MagicConfig,
    MagicLog,
    MagicScene,
    ObjectDescription,
    Region,
    RegionShape,
    Rotation3D,
    Vector2D,
    Vector3D,
)
from magic.generation.modules import CONNECTION_THICKNESS, OUTPUT_GUIDANCE
from magic.generation.modules.baseline.templates import BASELINE_TEMPLATE
from magic.utils.llm import Llm, LlmContent, TemplateFormatter
from magic.utils.retry import auto_retry

get_baseline_prompt = TemplateFormatter(
    BASELINE_TEMPLATE,
    wall_thickness=round(CONNECTION_THICKNESS / 2, 6),
    connection_thickness=CONNECTION_THICKNESS,
    output_guidance=OUTPUT_GUIDANCE,
    prompt=None,
)


@auto_retry
def get_baseline(scene: MagicScene, config: MagicConfig, llm: Llm, log: MagicLog) -> LlmContent:
    scene.regions.clear()
    scene.connections.clear()
    llm.clear_messages()
    prompt = get_baseline_prompt(prompt=scene.prompt)
    response, llm_output = llm.chat(prompt, temperature=config.temperature, to_json=True)
    scene.scene_type = response["scene_type"].lower()
    for rname, region in response["regions"].items():
        scene.regions[rname] = Region(
            name=rname.replace("_", " "),
            floor=ObjectDescription(
                color=region["floor"]["color"].strip(),
                material=region["floor"]["material"].strip().replace("made with ", ""),
                attributes=region["floor"]["attributes"].strip().replace("that is ", ""),
            ),
            wall=(
                ObjectDescription(
                    color=region["wall"]["color"].strip(),
                    material=region["wall"]["material"].strip().replace("made with ", ""),
                    attributes=region["wall"]["attributes"].strip().replace("that is ", ""),
                )
                if scene.is_indoor
                else None
            ),
            objects={
                oname: AnticipatedObject(
                    category=obj["category"],
                    description=ObjectDescription(
                        color=obj["color"].strip(),
                        material=obj["material"].strip().replace("made with ", ""),
                        attributes=obj["attributes"].strip().replace("that is ", ""),
                    ),
                    dimensions=Dimensions3D(
                        width=obj["dimensions"][0], height=obj["dimensions"][1], depth=obj["dimensions"][2]
                    ),
                    position=[Vector3D(x=obj["position"][0], y=obj["position"][1], z=obj["position"][2])],
                    rotation=[Rotation3D(x=obj["rotation"][0], y=obj["rotation"][1], z=obj["rotation"][2])],
                )
                for oname, obj in region["objects"].items()
            },
            shape=RegionShape(
                min_vertex=Vector2D(x=region["shape"]["min_vertex"][0], y=region["shape"]["min_vertex"][1]),
                max_vertex=Vector2D(x=region["shape"]["max_vertex"][0], y=region["shape"]["max_vertex"][1]),
                height=region["shape"]["height"] if scene.is_indoor else None,
            ),
            lights=[Vector3D(x=light[0], y=light[1], z=light[2]) for light in region["lights"]],
        )
    for i, conn in enumerate(response["connections"], start=1):
        scene.connections[f"conn_{i}"] = Connection(
            obj=AnticipatedObject(
                category=conn["type"],
                description=ObjectDescription(
                    color=conn["color"].strip(),
                    material=conn["material"].strip().replace("made with ", ""),
                    attributes=conn["attributes"].strip().replace("that is ", ""),
                ),
                dimensions=Dimensions3D(
                    width=conn["dimensions"][0], height=conn["dimensions"][1], depth=conn["dimensions"][2]
                ),
                position=[Vector3D(x=conn["position_x"], y=conn["position_y"], z=conn["position_z"])],
                rotation=[Rotation3D(y=conn["rotation_y"])],
            )
        )
    log.save()
    llm.clear_messages()
    return llm_output.content
