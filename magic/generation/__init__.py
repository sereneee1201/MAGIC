# -*- coding: utf-8 -*-

from enum import Enum
from math import sqrt
from pathlib import Path
from typing import Annotated, Any, Literal, Optional

import numpy as np
from pydantic import BaseModel, DirectoryPath, Field, FilePath, field_validator, model_validator, computed_field
from typing_extensions import Self
from magic.utils.dtypes import NonEmptyStr
from magic.utils.misc import next_available_in_dict, replace_non_alphanumeric


class GenerationMode(Enum):
    BASELINE = 0
    EVERYTHING = 1
    BEFORE_OBJECT_PLACEMENT = 2
    FROM_OBJECT_PLACEMENT = 3
    FROM_COMPOSE = 4


class MagicConfig(BaseModel, validate_assignment=True):
    normal_llm: NonEmptyStr = "normal_llm"
    reasoning_llm: NonEmptyStr = "reasoning_llm"
    vlm: NonEmptyStr = "vlm"
    temperature: Annotated[float, Field(ge=0.0, le=2.0)] = 0.7
    gen_mode: GenerationMode = GenerationMode.EVERYTHING
    new_constraints: bool = True
    new_draft: bool = True
    compose: bool = True
    render: bool = False
    unity: bool = False
    output_dir: str = "."
    # ----- Ablation studies -----
    inject_design: bool = False
    inject_object: bool = False
    constraint_llm: NonEmptyStr = "normal_llm"
    max_constraint_modifications: Annotated[int, Field(ge=0)] = 2
    solution_llm: NonEmptyStr = "normal_llm"
    max_solution_corrections: Annotated[int, Field(ge=0)] = 5
    n_constraints_per_round: Annotated[int, Field(ge=1)] = 3
    obj_retriever: Optional[NonEmptyStr] = "magic.object.objrtv.objathor.retriever.ObjathorRetriever"
    obj_retriever_kwargs: dict[NonEmptyStr, Any] = {"thresh": 0.5, "alpha": 100.0, "beta": 1.0}
    obj_generator: Optional[NonEmptyStr] = "magic.object.objgen.shap_e.generator.ShapEGenerator"
    obj_generator_kwargs: dict[NonEmptyStr, Any] = {"steps": 64}
    # ============================
    n_trials: Annotated[int, Field(ge=1)] = 1
    max_retries: Annotated[int, Field(ge=0)] = 10
    max_threads: Annotated[int, Field(ge=1)] = 4
    suffix: Optional[NonEmptyStr] = None
    verbose: bool = True

    @computed_field
    @property
    def parent_dir(self) -> Path:
        return Path(self.output_dir)
    
    @field_validator("constraint_llm", mode="after")
    @classmethod
    def validate_constraint_llm(cls, v: NonEmptyStr) -> NonEmptyStr:
        if v not in {"normal_llm", "reasoning_llm"}:
            raise ValueError("`constraint_llm` must be either 'normal_llm' or 'reasoning_llm'")
        return v

    @field_validator("solution_llm", mode="after")
    @classmethod
    def validate_solution_llm(cls, v: NonEmptyStr) -> NonEmptyStr:
        if v not in {"normal_llm", "reasoning_llm"}:
            raise ValueError("`solution_llm` must be either 'normal_llm' or 'reasoning_llm'")
        return v

    @field_validator("parent_dir", mode="before")
    @classmethod
    def ensure_dir_exists(cls, v: Any) -> Path:
        path = Path(v)
        if not path.exists():
            path.mkdir(parents=True, exist_ok=True)
        elif not path.is_dir():
            raise ValueError(f"{v} exists but is not a directory")
        return path

    @model_validator(mode="after")
    def has_object_acquirer(self) -> Self:
        if self.obj_retriever is None and self.obj_generator is None:
            raise ValueError("`obj_retriever` and `obj_generator` must not be both None")
        return self


class Dimensions3D(BaseModel, validate_assignment=True, strict=True):
    width: Annotated[float, Field(gt=0.0)]
    height: Annotated[float, Field(gt=0.0)]
    depth: Annotated[float, Field(gt=0.0)]

    @property
    def volume(self) -> float:
        return self.width * self.height * self.depth


class Vector2D(BaseModel, validate_assignment=True, strict=True):
    x: float = 0.0
    y: float = 0.0

    def __add__(self, other: "Vector2D") -> "Vector2D":
        return Vector2D(x=self.x + other.x, y=self.y + other.y)

    def __sub__(self, other: "Vector2D") -> "Vector2D":
        return Vector2D(x=self.x - other.x, y=self.y - other.y)


class Vector3D(Vector2D):
    z: float = 0.0

    def __add__(self, other: "Vector3D") -> "Vector3D":
        return Vector3D(x=self.x + other.x, y=self.y + other.y, z=self.z + other.z)

    def __sub__(self, other: "Vector3D") -> "Vector3D":
        return Vector3D(x=self.x - other.x, y=self.y - other.y, z=self.z - other.z)

    def __mul__(self, scalar: float) -> "Vector3D":
        return Vector3D(x=self.x * scalar, y=self.y * scalar, z=self.z * scalar)

    def __eq__(self, other: "Vector3D") -> bool:
        return self.x == other.x and self.y == other.y and self.z == other.z

    @property
    def magnitude(self) -> float:
        return sqrt(self.x**2 + self.y**2 + self.z**2)

    @property
    def normalized(self) -> "Vector3D":
        mag = self.magnitude
        return Vector3D() if mag == 0.0 else Vector3D(x=self.x / mag, y=self.y / mag, z=self.z / mag)


class Rotation3D(BaseModel, validate_assignment=True, strict=True):
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0

    @field_validator("x", "y", "z", mode="after")
    @classmethod
    def clamp_rotation(cls, v: float) -> float:
        return v % 360.0


class ObjectDescription(BaseModel, validate_assignment=True, strict=True):
    color: NonEmptyStr
    material: NonEmptyStr
    attributes: str
    roughness: Annotated[float, Field(ge=0.0, le=1.0)] = 0.5
    metallic: Annotated[float, Field(ge=0.0, le=1.0)] = 0.0


class AnticipatedObject(BaseModel, validate_assignment=True, strict=True):
    category: Optional[NonEmptyStr] = None
    is_portal: bool = False
    supported_from_below: bool = False
    hanged_on_wall: bool = False
    hanged_from_ceiling: bool = False
    description: Optional[ObjectDescription] = None
    dimensions: Optional[Dimensions3D] = None
    position: list[Vector3D] = []
    rotation: list[Rotation3D] = []
    children: dict[NonEmptyStr, "AnticipatedObject"] = {}

    def get_min_vertex(self, index: int) -> Vector3D:
        obb = self.get_obb(self.dimensions, self.position[index], self.rotation[index])
        obb_min = obb.min(axis=0).tolist()
        return Vector3D(x=obb_min[0], y=obb_min[1], z=obb_min[2])

    def get_max_vertex(self, index: int) -> Vector3D:
        obb = self.get_obb(self.dimensions, self.position[index], self.rotation[index])
        obb_max = obb.max(axis=0).tolist()
        return Vector3D(x=obb_max[0], y=obb_max[1], z=obb_max[2])

    def get_textual_description(self, with_dims: bool = False) -> str:
        if self.description is None:
            raise RuntimeError(f"`description` must not be None")
        desc = f"a {self.description.color} {self.category} made with {self.description.material}"
        if self.description.attributes.strip() != "":
            desc += f" that is {self.description.attributes}"
        if with_dims:
            if self.dimensions is None:
                raise RuntimeError(f"`dimensions` must not be None")
            width = round(self.dimensions.width * 100, 1)
            height = round(self.dimensions.height * 100, 1)
            depth = round(self.dimensions.depth * 100, 1)
            desc += f" [{width}cm x {height}cm x {depth}cm]"
        return desc

    @staticmethod
    def get_obb(
        dims: Dimensions3D, pos: Vector3D, rot: Rotation3D
    ) -> np.ndarray[tuple[Literal[8], Literal[3]], np.floating]:
        from magic.utils.mesh import rotate_in_lhs

        aabb_min = Vector3D(x=-dims.width / 2, y=-dims.height / 2, z=-dims.depth / 2)
        aabb_max = Vector3D(x=dims.width / 2, y=dims.height / 2, z=dims.depth / 2)
        aabb = [
            [aabb_min.x, aabb_min.y, aabb_min.z],
            [aabb_min.x, aabb_min.y, aabb_max.z],
            [aabb_min.x, aabb_max.y, aabb_min.z],
            [aabb_min.x, aabb_max.y, aabb_max.z],
            [aabb_max.x, aabb_min.y, aabb_min.z],
            [aabb_max.x, aabb_min.y, aabb_max.z],
            [aabb_max.x, aabb_max.y, aabb_min.z],
            [aabb_max.x, aabb_max.y, aabb_max.z],
        ]
        rotated = rotate_in_lhs(aabb, [rot.x, rot.y, rot.z])
        obb = rotated + np.array([pos.x, pos.y, pos.z])
        return obb

    @staticmethod
    def get_oriented_dimensions(dims: Dimensions3D, rot: Rotation3D) -> Dimensions3D:
        obb = AnticipatedObject.get_obb(dims, Vector3D(), rot)
        odims = (obb.max(axis=0) - obb.min(axis=0)).tolist()
        return Dimensions3D(width=odims[0], height=odims[1], depth=odims[2])


class RegionShape(BaseModel, validate_assignment=True, strict=True):
    min_vertex: Vector2D
    max_vertex: Vector2D
    height: Optional[Annotated[float, Field(gt=0.0)]] = None
    shifts: Vector2D = Vector2D()

    @property
    def width(self) -> float:
        return self.max_vertex.x - self.min_vertex.x

    @property
    def depth(self) -> float:
        return self.max_vertex.y - self.min_vertex.y

    @property
    def center(self) -> Vector2D:
        return Vector2D(x=(self.min_vertex.x + self.max_vertex.x) / 2, y=(self.min_vertex.y + self.max_vertex.y) / 2)

    @property
    def shifted_min_vertex(self) -> Vector2D:
        if self.shifts is None:
            raise RuntimeError(f"`shifts` must not be None")
        return self.min_vertex + self.shifts

    @property
    def shifted_max_vertex(self) -> Vector2D:
        if self.shifts is None:
            raise RuntimeError(f"`shifts` must not be None")
        return self.max_vertex + self.shifts

    @property
    def shifted_center(self) -> Vector2D:
        if self.shifts is None:
            raise RuntimeError(f"`shifts` must not be None")
        return self.center + self.shifts


class Region(BaseModel, validate_assignment=True):
    name: NonEmptyStr
    subprompt: Optional[NonEmptyStr] = None
    floor: Optional[ObjectDescription] = None
    wall: Optional[ObjectDescription] = None
    object_injected_subprompt: Optional[NonEmptyStr] = None
    objects: dict[NonEmptyStr, AnticipatedObject] = {}
    object_relations: list[list[NonEmptyStr]] = []
    shape: Optional[RegionShape] = None
    constraints: list[NonEmptyStr] = []
    cstr_syntax_passing_rate: Optional[Annotated[float, Field(ge=0.0, le=1.0)]] = None
    cstr_nonsense_passing_rates: list[Annotated[float, Field(ge=0.0, le=1.0)]] = []
    no_nonsensical_cstr: bool = False
    cstr_redundancy_passing_rates: list[Annotated[float, Field(ge=0.0, le=1.0)]] = []
    no_redundant_cstr: bool = False
    cstr_contradiction_passing_rates: list[Annotated[float, Field(ge=0.0, le=1.0)]] = []
    no_contradicted_cstr: bool = False
    allowed_collision: set[tuple[str, str]] = set()
    allowed_outside: set[NonEmptyStr] = set()
    lights: list[Vector3D] = []

    def clear_constraints(self) -> None:
        self.constraints.clear()
        self.cstr_syntax_passing_rate = None
        self.cstr_redundancy_passing_rates.clear()
        self.no_redundant_cstr = False
        self.cstr_contradiction_passing_rates.clear()
        self.no_contradicted_cstr = False
        self.allowed_collision.clear()
        self.allowed_outside.clear()

    def clear_solutions(self, keep_draft: bool = False) -> None:
        for obj in self.objects.values():
            for arr in (obj.position, obj.rotation):
                for _ in range(len(arr) - (1 if keep_draft else 0)):
                    arr.pop()
        self.lights.clear()


class NeighborPair(BaseModel, validate_assignment=True, strict=True):
    region_a: NonEmptyStr
    region_b: NonEmptyStr | Literal["__outside__"]


class Connection(BaseModel, validate_assignment=True, strict=True):
    region_a: Optional[NonEmptyStr] = None
    region_b: Optional[NonEmptyStr | Literal["__outside__"]] = None
    obj: Optional[AnticipatedObject] = None
    shifts: Vector2D = Vector2D()


class MagicScene(BaseModel, validate_assignment=True, strict=True):
    prompt: Optional[NonEmptyStr] = None
    scene_type: Optional[Literal["indoor", "outdoor"]] = None
    design_injected_prompt: Optional[NonEmptyStr] = None
    regions: dict[NonEmptyStr, Region] = {}
    neighbors: dict[NonEmptyStr, NeighborPair] = {}
    connections: dict[NonEmptyStr, Connection] = {}

    @property
    def is_indoor(self) -> bool:
        if self.scene_type is None:
            raise RuntimeError(f"`scene_type` must not be None")
        return self.scene_type == "indoor"

    @property
    def region_type(self) -> str:
        if self.scene_type is None:
            raise RuntimeError(f"`scene_type` must not be None")
        return "room" if self.is_indoor else "area"

    @property
    def n_regions(self) -> int:
        return len(self.regions)

    def has_region(self, region_name: NonEmptyStr) -> bool:
        return region_name in self.regions

    def has_neighbor_pair(self, region_a: NonEmptyStr, region_b: NonEmptyStr) -> bool:
        for neighbor in self.neighbors.values():
            if (neighbor.region_a == region_a and neighbor.region_b == region_b) or (
                neighbor.region_a == region_b and neighbor.region_b == region_a
            ):
                return True
        return False

    def add_neighbor_pair(self, region_a: NonEmptyStr, region_b: NonEmptyStr) -> None:
        region_a = replace_non_alphanumeric(region_a.lower())
        region_b = replace_non_alphanumeric(region_b.lower())
        if not self.has_region(region_a):
            raise RuntimeError()
        if not self.has_region(region_b) and region_b != "__outside__":
            raise RuntimeError()
        if region_a == region_b:
            return
        if self.has_neighbor_pair(region_a, region_b):
            return
        neighbor_name = f"neighbor_{len(self.neighbors) + 1}"
        self.neighbors[neighbor_name] = NeighborPair(region_a=region_a, region_b=region_b)

    def check_all_regions_have_neighbor(self) -> bool:
        for region_name in self.regions:
            if not any(
                neighbor.region_a == region_name or neighbor.region_b == region_name
                for neighbor in self.neighbors.values()
            ):
                return False
        return True

    def __add_connection(
        self, conn_type: Literal["door", "window"], region_a: NonEmptyStr, region_b: NonEmptyStr
    ) -> None:
        region_a = replace_non_alphanumeric(region_a.lower())
        region_b = replace_non_alphanumeric(region_b.lower())
        if not self.has_neighbor_pair(region_a, region_b):
            return
        conn_name = f"{conn_type}_1"
        if conn_name in self.connections:
            conn_name = next_available_in_dict(self.connections, conn_type)
        self.connections[conn_name] = Connection(region_a=region_a, region_b=region_b)

    def add_door(self, region_a: NonEmptyStr, region_b: NonEmptyStr) -> None:
        self.__add_connection("door", region_a, region_b)

    def add_window(self, region_a: NonEmptyStr, region_b: NonEmptyStr) -> None:
        self.__add_connection("window", region_a, region_b)

    def get_connections_to_region(self, region_name: NonEmptyStr) -> dict[NonEmptyStr, Connection]:
        connections = {}
        for conn_name, conn in self.connections.items():
            if conn.region_a == region_name or conn.region_b == region_name:
                connections[conn_name] = conn
        return connections


class MagicLog(BaseModel, validate_assignment=True):
    parent: Optional[str] = None
    timestamp: Optional[str] = None
    config: Optional[MagicConfig] = None
    output_dir: Optional[DirectoryPath] = None
    log_path: Optional[FilePath] = None
    scene: Optional[MagicScene] = None
    duration: dict[NonEmptyStr, float] = {}
    meshes: dict[NonEmptyStr, dict[NonEmptyStr, dict[NonEmptyStr, Any]]] = {}
    evaluation: dict[NonEmptyStr, Any] = {}
    modules: list[dict[NonEmptyStr, Any]] = []

    @property
    def renders_dir(self) -> DirectoryPath:
        if self.output_dir is None:
            raise RuntimeError(f"`output_dir` must not be None")
        return self.output_dir / "renders"

    def save(self) -> None:
        if self.log_path is None:
            raise RuntimeError(f"`log_path` must not be None")
        with open(self.log_path, "w", encoding="utf-8") as f:
            f.write(self.model_dump_json(indent=2))

    def add_region_mesh(
        self,
        region_name: NonEmptyStr,
        floor_path: Path,
        non_floor_path: Optional[Path] = None,
        wall_path: Optional[Path] = None,
        **kwargs: Any,
    ) -> None:
        if "regions" not in self.meshes:
            self.meshes["regions"] = {}
        if region_name in self.meshes["regions"]:
            raise ValueError(f'Mesh for region "{region_name}" already exists')
        self.meshes["regions"][region_name] = {"floor": floor_path}
        if non_floor_path is not None:
            self.meshes["regions"][region_name]["non_floor"] = non_floor_path
        if wall_path is not None:
            self.meshes["regions"][region_name]["wall"] = wall_path
        self.meshes["regions"][region_name].update(kwargs)

    def add_object_mesh(
        self, region_name: NonEmptyStr, obj_name: NonEmptyStr, query: NonEmptyStr, obj_path: Path, **kwargs: Any
    ) -> None:
        if "objects" not in self.meshes:
            self.meshes["objects"] = {}
        if region_name not in self.meshes["objects"]:
            self.meshes["objects"][region_name] = {}
        if obj_name in self.meshes["objects"][region_name]:
            raise ValueError(f'Mesh for object "{obj_name}" in region "{region_name}" already exists')
        self.meshes["objects"][region_name][obj_name] = {"query": query, "path": obj_path, **kwargs}

    def add_connection_mesh(self, conn_name: NonEmptyStr, query: NonEmptyStr, obj_path: Path, **kwargs: Any) -> None:
        if "connections" not in self.meshes:
            self.meshes["connections"] = {}
        if conn_name in self.meshes["connections"]:
            raise ValueError(f'Mesh for connection "{conn_name}" already exists')
        self.meshes["connections"][conn_name] = {"query": query, "path": obj_path, **kwargs}
