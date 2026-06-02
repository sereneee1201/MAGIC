# -*- coding: utf-8 -*-

from magic.generation import MagicConfig, MagicLog, MagicScene
from magic.generation.modules.scene_conceptualization.regions_objects.object_injection import inject_regions_object
from magic.generation.modules.scene_conceptualization.regions_objects.parent_objects_description import (
    get_regions_parent_objects_description,
)
from magic.generation.modules.scene_conceptualization.regions_objects.parent_objects_dimensions import (
    get_regions_parent_objects_dimensions,
)
from magic.generation.modules.scene_conceptualization.regions_objects.parent_objects_name import (
    get_regions_parent_objects_name,
)
from magic.generation.modules.scene_conceptualization.regions_objects.parent_objects_relations import (
    get_regions_parent_objects_relations,
)
from magic.utils.dtypes import SDict
from magic.utils.llm import Llm, LlmContent


def get_regions_objects(
    scene: MagicScene, config: MagicConfig, llm: Llm, log: MagicLog, portals: list
) -> SDict[LlmContent | SDict[LlmContent]]:
    contents = {}
    if config.inject_object:
        contents["object_injection"] = inject_regions_object(scene, config, llm, log)
    else:
        for region in scene.regions.values():
            region.object_injected_subprompt = region.subprompt
        log.save()
    contents["parent_objects_name"] = get_regions_parent_objects_name(scene, config, llm, log, portals)
    contents["parent_objects_description"] = get_regions_parent_objects_description(scene, config, llm, log)
    contents["parent_objects_dimensions"] = get_regions_parent_objects_dimensions(scene, config, llm, log)
    contents["parent_objects_relations"] = get_regions_parent_objects_relations(scene, config, llm, log)
    return contents
