# -*- coding: utf-8 -*-

from magic.generation.modules.scene_conceptualization.constraints import get_regions_constraints
from magic.generation.modules.scene_conceptualization.indoor_connections.establishment import (
    establish_indoor_connections,
)
from magic.generation.modules.scene_conceptualization.indoor_connections.placement import place_indoor_connections
from magic.generation.modules.scene_conceptualization.neighbors import establish_neighbors
from magic.generation.modules.scene_conceptualization.regions_design import design_regions
from magic.generation.modules.scene_conceptualization.regions_objects import get_regions_objects
from magic.generation.modules.scene_conceptualization.regions_shape import get_regions_shape
from magic.generation.modules.scene_conceptualization.regions_shape.room_adjustment import adjust_rooms
