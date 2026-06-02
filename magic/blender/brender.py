# -*- coding: utf-8 -*-

import argparse
import math
import sys
import traceback
from copy import deepcopy
from math import radians, sin
from os import makedirs
from os.path import abspath, dirname, exists, join
from typing import Literal, Optional, overload

import bmesh  # type: ignore
import bpy  # type: ignore
from bpy.types import Image, Object  # type: ignore
from mathutils import Euler, Matrix, Vector  # type: ignore

TEXTURES_DIR = join(abspath(dirname(__file__)), "textures")
DEFAULT_ALBEDO_PATH = join(TEXTURES_DIR, "default_albedo.png")
DEFAULT_EMISSION_PATH = join(TEXTURES_DIR, "default_emission.png")
DEFAULT_NORMAL_PATH = join(TEXTURES_DIR, "default_normal.png")

PyVector3D = tuple[float, float, float]


def clear() -> None:
    for obj in bpy.data.objects:
        bpy.data.objects.remove(obj, do_unlink=True)
    for material in bpy.data.materials:
        bpy.data.materials.remove(material, do_unlink=True)
    for texture in bpy.data.textures:
        bpy.data.textures.remove(texture, do_unlink=True)
    for image in bpy.data.images:
        bpy.data.images.remove(image, do_unlink=True)


def duplicate(obj: Object, name: Optional[str] = None) -> Object:
    if name is None:
        name = f"{obj.name}_copy"
    focus(obj)
    bpy.ops.object.duplicate(linked=False)
    obj_copy = bpy.context.active_object
    obj_copy.name = name
    focus(obj_copy)
    return obj_copy


def export_obj(
    path: str, obj: Optional[Object] = None, export_vertex_colors: bool = False, export_materials: bool = True
) -> bool:
    export_dir = dirname(path)
    if export_dir != "" and not exists(export_dir):
        makedirs(export_dir)
    if obj is not None:
        # store original visibility
        visibility = {o: o.hide_get() for o in bpy.context.scene.objects}
        # make only the target object visible
        for o in bpy.context.scene.objects:
            o.hide_set(True if o != obj else False)
    bpy.ops.wm.obj_export(
        filepath=path,
        export_colors=export_vertex_colors,
        export_materials=export_materials,
        export_pbr_extensions=True,
        path_mode="COPY",
    )
    if obj is not None:
        # restore original visibility
        for o, was_hidden in visibility.items():
            o.hide_set(was_hidden)
    return exists(path)


def focus(obj: Object) -> None:
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj


def initialize(
    *,
    transparent: bool = False,
    color_depth: Literal["8", "16"] = "8",
    compression: int = 15,
    samples: int = 32,
    use_adaptive_sampling: bool = True,
    adaptive_threshold: float = 0.01,
    use_denoising: bool = True,
    pixel_filter_type: Literal["BOX", "GAUSSIAN", "BLACKMAN_HARRIS"] = "BLACKMAN_HARRIS",
    filter_width: float = 0.1,
    exposure: float = 1.0,
) -> None:
    """
    Args:
        compression (int, optional): Lower values output faster with less
            lossless compression. Defaults to 15.
        samples (int, optional): Number of samples to render for
            each pixel. Defaults to 32.
        use_adaptive_sampling (bool, optional): Automatically reduce
            the number of samples per pixel based on estimated noise level.
            Defaults to True.
        adaptive_threshold (float, optional): Lower values reduce
            noise at the cost of render time. Defaults to 0.01.
        filter_width (float, optional): Lower values give more
            aliased but less blurry edges. Defaults to 0.1.
    """

    # reference: https://blender.stackexchange.com/a/196702
    for device in ("CUDA", "HIP", "METAL", "NONE"):
        try:
            bpy.context.preferences.addons["cycles"].preferences.compute_device_type = device
            break
        except TypeError:
            continue
    bpy.context.preferences.addons["cycles"].preferences.get_devices()
    is_set = False
    cpu_device = None
    for device in bpy.context.preferences.addons["cycles"].preferences.devices:
        if device.type != "CPU":
            device.use = True
            is_set = True
        else:
            cpu_device = device
    if not is_set:
        if cpu_device is not None:
            cpu_device.use = True
        else:
            raise RuntimeError("No GPU found, and CPU is not available")

    # set background color
    bpy.data.worlds["World"].node_tree.nodes["Background"].inputs[0].default_value = (1.0, 1.0, 1.0, 1.0)
    bpy.data.worlds["World"].node_tree.nodes["Background"].inputs[1].default_value = 1.0  # Background strength

    context = bpy.context
    scene = context.scene
    scene.view_settings.view_transform = "Standard"

    # customize the Cycles render engine
    scene.cycles.device = "GPU" if is_set else "CPU"
    scene.cycles.use_adaptive_sampling = use_adaptive_sampling
    scene.cycles.adaptive_threshold = adaptive_threshold
    scene.cycles.samples = samples
    scene.cycles.use_denoising = use_denoising
    scene.cycles.pixel_filter_type = pixel_filter_type
    scene.cycles.filter_width = filter_width
    scene.cycles.film_exposure = exposure

    # customize the render settings
    render = scene.render
    render.engine = "CYCLES"
    render.film_transparent = transparent
    render.resolution_percentage = 100
    render.pixel_aspect_x = 1.0
    render.pixel_aspect_y = 1.0
    render.use_file_extension = True
    render.image_settings.file_format = "PNG"
    render.image_settings.color_mode = "RGBA"
    render.image_settings.color_depth = color_depth
    render.image_settings.compression = compression


def is_mesh(obj: Object, raise_err: bool = False) -> bool:
    if obj.type == "MESH":
        return True
    if raise_err:
        raise TypeError(f"Object {obj.name} is not a mesh")
    return False


def import_obj(obj_path: str, load_vertex_colors: bool = False) -> Object:
    bpy.ops.wm.obj_import(filepath=obj_path)
    obj = bpy.context.selected_objects[0]
    if load_vertex_colors and is_mesh(obj):
        colors = []
        with open(obj_path) as f:
            for line in f:
                if line.startswith("v "):
                    parts = line.strip().split()
                    if len(parts) < 4:
                        continue
                    if len(parts) >= 7:
                        colors.append(tuple(map(float, parts[4:7])))
                    else:
                        colors.append((0.0, 0.0, 0.0))

        mesh = obj.data
        color_layer = mesh.vertex_colors.new(name="ImportedVertexColor")
        for face in mesh.polygons:
            for loop_idx in face.loop_indices:
                vert_idx = mesh.loops[loop_idx].vertex_index
                color_layer.data[loop_idx].color = colors[vert_idx] + (1.0,)

        mat = bpy.data.materials.new(name="BakedMaterial")
        mat.use_nodes = True
        nodes = mat.node_tree.nodes
        links = mat.node_tree.links
        nodes.clear()
        links.clear()
        output = nodes.new(type="ShaderNodeOutputMaterial")
        diffuse = nodes.new(type="ShaderNodeBsdfDiffuse")
        vcol = nodes.new(type="ShaderNodeVertexColor")
        links.new(vcol.outputs["Color"], diffuse.inputs["Color"])
        links.new(diffuse.outputs["BSDF"], output.inputs["Surface"])
        if len(obj.data.materials) == 0:
            obj.data.materials.append(mat)
        else:
            obj.data.materials[0] = mat
    return obj


def load_blender_image(path: str) -> Image:
    return bpy.data.images.load(path, check_existing=True)


def transform(
    obj: Object,
    position: Optional[PyVector3D] = None,
    rotation: Optional[PyVector3D] = None,
    scale: Optional[PyVector3D] = None,
    inplace: bool = True,
) -> Object:
    if not inplace:
        obj = duplicate(obj)
    focus(obj)
    bpy.ops.object.origin_set(type="ORIGIN_GEOMETRY", center="BOUNDS")
    old_location = deepcopy(obj.location)
    obj.location = Vector((0, 0, 0))
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)  # in case there is unapplied transform
    if scale is not None:
        obj.scale = Vector(scale)
        bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    if rotation is not None:
        obj.rotation_euler = Euler(map(radians, rotation))
        bpy.ops.object.transform_apply(location=False, rotation=True, scale=False)
    obj.location = Vector(position) if position is not None else old_location
    bpy.ops.object.transform_apply(location=True, rotation=False, scale=False)
    return obj


class Builder(object):
    def __init__(self) -> None:
        initialize()

    def add_material(
        self,
        obj: Object,
        albedo_path: Optional[str] = None,
        emission_path: Optional[str] = None,
        normal_path: Optional[str] = None,
        roughness: Optional[float] = None,
        metallic: Optional[float] = None,
        index_of_refraction: float = 1.0,
        enable_backface_culling: bool = False,
        material_name: str = "Material",
        inplace: bool = True,
    ) -> Object:
        is_mesh(obj, raise_err=True)
        if not inplace:
            obj = duplicate(obj)
        focus(obj)

        albedo_path = DEFAULT_ALBEDO_PATH if albedo_path is None else albedo_path
        emission_path = DEFAULT_EMISSION_PATH if emission_path is None else emission_path
        normal_path = DEFAULT_NORMAL_PATH if normal_path is None else normal_path
        roughness = 1.0 if roughness is None else max(0.0, min(roughness, 1.0))
        metallic = 0.0 if metallic is None else max(0.0, min(metallic, 1.0))

        mat = bpy.data.materials.new(name=material_name)
        mat.use_nodes = True
        nodes = mat.node_tree.nodes
        links = mat.node_tree.links
        links.clear()
        bsdf = nodes["Principled BSDF"]
        output = nodes["Material Output"]

        albedo_img = nodes.new("ShaderNodeTexImage")
        albedo_img.image = load_blender_image(albedo_path)
        links.new(albedo_img.outputs["Color"], bsdf.inputs["Base Color"])
        bsdf.inputs[1].default_value = metallic
        bsdf.inputs[2].default_value = roughness
        bsdf.inputs[3].default_value = max(index_of_refraction, 1.0)

        emission_img = nodes.new("ShaderNodeTexImage")
        emission_img.image = load_blender_image(emission_path)
        links.new(emission_img.outputs["Color"], bsdf.inputs["Emission Color"])
        bsdf.inputs[28].default_value = 1.0  # emission strength

        normal_img = nodes.new("ShaderNodeTexImage")
        normal_img.image = load_blender_image(normal_path)
        normal_img.image.colorspace_settings.name = "Non-Color"
        normal_map = nodes.new("ShaderNodeNormalMap")
        links.new(normal_img.outputs["Color"], normal_map.inputs["Color"])
        links.new(normal_map.outputs["Normal"], bsdf.inputs["Normal"])

        if not enable_backface_culling:
            links.new(bsdf.outputs["BSDF"], output.inputs["Surface"])
        else:
            mix = nodes.new("ShaderNodeMixShader")
            mix.inputs["Fac"].default_value = 1.0
            transparent = nodes.new("ShaderNodeBsdfTransparent")
            geometry = nodes.new("ShaderNodeNewGeometry")
            links.new(bsdf.outputs["BSDF"], mix.inputs[2])
            links.new(mix.outputs["Shader"], output.inputs["Surface"])
            links.new(geometry.outputs["Backfacing"], mix.inputs["Fac"])
            links.new(transparent.outputs["BSDF"], mix.inputs[1])

        if len(obj.data.materials) == 0:
            obj.data.materials.append(mat)
        else:
            obj.data.materials[0] = mat
        return obj

    def bake_vertex_colors_to_albedo(self, obj: Object, albedo_path: str, resolution: int = 1024) -> bool:
        is_mesh(obj, raise_err=True)
        if len(obj.data.materials) == 0:
            raise RuntimeError("`obj` has no material to bake vertex colors to albedo texture")
        if len(obj.data.uv_layers) == 0:
            self.create_uv(obj)
        mat = obj.data.materials[0]
        nodes = mat.node_tree.nodes
        img = bpy.data.images.new("BakedAlbedo", width=resolution, height=resolution)
        img.file_format = "PNG"
        img_node = nodes.new(type="ShaderNodeTexImage")
        img_node.image = img
        img_node.select = True
        nodes.active = img_node
        bpy.ops.object.bake(type="DIFFUSE", pass_filter={"COLOR"}, use_clear=True)
        img.filepath_raw = albedo_path
        img.save()
        return exists(albedo_path)

    def create_uv(
        self, obj: Object, angle_limit: float = 66.0, island_margin: float = 0.0, inplace: bool = True
    ) -> Object:
        is_mesh(obj, raise_err=True)
        if not inplace:
            obj = duplicate(obj)
        focus(obj)
        bpy.ops.object.mode_set(mode="EDIT")
        bpy.ops.mesh.select_all(action="SELECT")
        bpy.ops.uv.smart_project(angle_limit=radians(angle_limit), island_margin=island_margin)
        bpy.ops.object.mode_set(mode="OBJECT")
        return obj

    def create_wireframe(self, obj: Object, sphere_radius: float = 0.05, cylinder_radius: float = 0.02) -> Object:
        is_mesh(obj, raise_err=True)
        obj_copy = duplicate(obj)
        self.simplify(obj_copy)
        combined_mesh = bpy.data.meshes.new(f"{obj.name}_WireframeMesh")
        bm = bmesh.new()

        # create spheres for vertices
        for vert in obj_copy.data.vertices:
            sphere = bmesh.ops.create_icosphere(bm, subdivisions=3, radius=sphere_radius)
            for v in sphere["verts"]:
                v.co += vert.co  # move to the vertex location

        # create cylinders for edges
        for edge in obj_copy.data.edges:
            v1 = obj_copy.data.vertices[edge.vertices[0]].co
            v2 = obj_copy.data.vertices[edge.vertices[1]].co

            # calculate the midpoint and direction
            mid_point = (v1 + v2) / 2
            direction = (v2 - v1).normalized()
            distance = (v2 - v1).length

            # create a cylinder
            cylinder = bmesh.ops.create_cone(
                bm, cap_tris=True, radius1=cylinder_radius, radius2=cylinder_radius, depth=distance, segments=8
            )

            # calculate the rotation matrix to align the cylinder
            z_axis = Vector((0, 0, 1))
            rotation_axis = direction.cross(z_axis).normalized()
            rotation_angle = direction.angle(z_axis)
            rotation_matrix = Matrix.Rotation(rotation_angle, 4, rotation_axis)

            # apply the rotation to the cylinder vertices
            for v in cylinder["verts"]:
                v.co = rotation_matrix @ v.co

            # move the cylinder to the midpoint
            for v in cylinder["verts"]:
                v.co += mid_point

        # finalize the bmesh
        bm.to_mesh(combined_mesh)
        bm.free()
        bpy.data.objects.remove(obj_copy, do_unlink=True)
        combined_object = bpy.data.objects.new(f"{obj.name}_Wireframe", combined_mesh)
        bpy.context.collection.objects.link(combined_object)
        focus(combined_object)
        return combined_object

    def flip_normals(self, obj: Object, inplace: bool = True) -> Object:
        is_mesh(obj, raise_err=True)
        if not inplace:
            obj = duplicate(obj)
        focus(obj)
        bpy.ops.object.mode_set(mode="EDIT")
        bpy.ops.mesh.select_all(action="SELECT")
        bpy.ops.mesh.flip_normals()
        bpy.ops.object.mode_set(mode="OBJECT")
        return obj

    def map_faces_to_full_uv(self, obj: Object, inplace: bool = True) -> Object:
        is_mesh(obj, raise_err=True)
        if not inplace:
            obj = duplicate(obj)
        focus(obj)
        uv_layer = obj.data.uv_layers.active.data
        for poly in obj.data.polygons:
            if poly.loop_total == 3 or poly.loop_total == 4:
                if poly.loop_total == 3:
                    uv_coords = [(0.0, 0.0), (1.0, 0.0), (1.0, 1.0)]
                else:
                    uv_coords = [(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)]
                for i, loop_index in enumerate(poly.loop_indices):
                    uv_layer[loop_index].uv = uv_coords[i % len(uv_coords)]
            else:
                pass
        return obj

    def modify_boolean(self, op: Literal["DIFFERENCE", "INTERSECT", "UNION"], obj1: Object, obj2: Object) -> Object:
        is_mesh(obj1, raise_err=True)
        is_mesh(obj2, raise_err=True)
        obj = duplicate(obj1, name=f"{obj1.name}_{op}")
        modifier = obj.modifiers.new(name="BooleanModifier", type="BOOLEAN")
        modifier.operation = op
        modifier.object = obj2
        bpy.ops.object.modifier_apply(modifier=modifier.name)
        return obj

    def new_cube(self, name: str = "Cube") -> Object:
        bpy.ops.mesh.primitive_cube_add(size=1, calc_uvs=False)
        obj = bpy.context.selected_objects[0]
        obj.name = name
        focus(obj)
        return obj

    def normalize(self, obj: Object, dims: PyVector3D = (1.0, 1.0, 1.0), inplace: bool = True) -> Object:
        is_mesh(obj, raise_err=True)
        if not inplace:
            obj = duplicate(obj)
        focus(obj)
        transform(obj)
        scale_factors = [1 / d if d != 0 else 1.0 for d in obj.dimensions]
        new_scale = (
            obj.scale.x * scale_factors[0] * dims[0],
            obj.scale.y * scale_factors[1] * dims[1],
            obj.scale.z * scale_factors[2] * dims[2],
        )
        transform(obj, scale=new_scale)
        return obj

    def separate_bottom(self, obj: Object, bottom_z: float, eps: float = 1e-5) -> tuple[Optional[Object], Object]:
        is_mesh(obj, raise_err=True)
        non_bottom = duplicate(obj, name=f"{obj.name}_non-bottom")
        bpy.ops.object.mode_set(mode="EDIT")
        bpy.context.tool_settings.mesh_select_mode = (False, False, True)

        # get mesh from the object
        bm = bmesh.from_edit_mesh(non_bottom.data)
        bm.faces.ensure_lookup_table()
        for face in bm.faces:
            face.select = False

        # find bottom faces
        has_bottom_face = False
        for face in bm.faces:
            center = face.calc_center_median()
            if center.z < bottom_z + eps:
                face.select = True
                has_bottom_face = True

        # separate bottom faces from the rest
        bottom = None
        if has_bottom_face:
            bmesh.update_edit_mesh(non_bottom.data)
            ori_objects = set(bpy.context.scene.objects)
            bpy.ops.mesh.separate(type="SELECTED")
            bpy.ops.object.mode_set(mode="OBJECT")
            new_objects = set(bpy.context.scene.objects) - ori_objects
            if len(new_objects) > 0:
                bottom = new_objects.pop()
                bottom.name = f"{obj.name}_bottom"
        else:
            bpy.ops.object.mode_set(mode="OBJECT")

        bm.free()
        return bottom, non_bottom

    def separate_top(self, obj: Object, top_z: float, eps: float = 1e-5) -> tuple[Object, Object]:
        is_mesh(obj, raise_err=True)
        non_top = duplicate(obj, name=f"{obj.name}_non-top")
        bpy.ops.object.mode_set(mode="EDIT")
        bpy.context.tool_settings.mesh_select_mode = (False, False, True)

        # get mesh from the object
        bm = bmesh.from_edit_mesh(non_top.data)
        bm.faces.ensure_lookup_table()
        for face in bm.faces:
            face.select = False

        # find top faces
        has_top_face = False
        for face in bm.faces:
            center = face.calc_center_median()
            if center.z > top_z - eps:
                face.select = True
                has_top_face = True

        # separate top faces from the rest
        top = None
        if has_top_face:
            bmesh.update_edit_mesh(non_top.data)
            ori_objects = set(bpy.context.scene.objects)
            bpy.ops.mesh.separate(type="SELECTED")
            bpy.ops.object.mode_set(mode="OBJECT")
            new_objects = set(bpy.context.scene.objects) - ori_objects
            if len(new_objects) > 0:
                top = new_objects.pop()
                top.name = f"{obj.name}_top"
        else:
            bpy.ops.object.mode_set(mode="OBJECT")

        bm.free()
        return top, non_top

    def simplify(self, obj: Object, inplace: bool = True) -> Object:
        is_mesh(obj, raise_err=True)
        if not inplace:
            obj = duplicate(obj)
        focus(obj)
        bpy.ops.object.mode_set(mode="EDIT")
        bpy.ops.mesh.select_all(action="SELECT")
        bpy.ops.mesh.dissolve_limited()
        bpy.ops.object.mode_set(mode="OBJECT")
        return obj

    def solidify(self, obj: Object, thickness: float = 0.01, offset: float = 1.0, inplace: bool = True) -> Object:
        is_mesh(obj, raise_err=True)
        if not inplace:
            obj = duplicate(obj)
        focus(obj)
        modifier = obj.modifiers.new(name="SolidifyModifier", type="SOLIDIFY")
        modifier.thickness = thickness
        modifier.offset = offset
        modifier.use_even_offset = True
        bpy.ops.object.modifier_apply(modifier=modifier.name)
        return obj

    def triangulate(self, obj: Object, inplace: bool = True) -> Object:
        is_mesh(obj, raise_err=True)
        if not inplace:
            obj = duplicate(obj)
        focus(obj)
        bpy.ops.object.mode_set(mode="EDIT")
        bm = bmesh.from_edit_mesh(obj.data)
        bmesh.ops.triangulate(bm, faces=bm.faces)
        bmesh.update_edit_mesh(obj.data)
        bm.free()
        bpy.ops.object.mode_set(mode="OBJECT")
        return obj


class Renderer(object):
    def __init__(self, *, transparent: bool = False, samples: int = 32, exposure: float = 1.0) -> None:
        initialize(transparent=transparent, samples=samples, exposure=exposure)

    def add_area_light(
        self, position: PyVector3D = (0, 0, 0), rotation: PyVector3D = (0, 0, 0), energy: int = 100
    ) -> None:
        bpy.ops.object.light_add(type="AREA")
        light = bpy.context.selected_objects[0]
        transform(light, position=position, rotation=rotation)
        light.data.energy = energy
        light.data.shape = "SQUARE"
        light.data.size = 1
        light.data.use_shadow = True
        light.data.spread = radians(180)

    def add_point_light(self, position: PyVector3D = (0, 0, 0), energy: int = 40, use_shadow: bool = True) -> None:
        bpy.ops.object.light_add(type="POINT")
        light = bpy.context.selected_objects[0]
        transform(light, position=position)
        light.data.energy = energy
        light.data.use_soft_falloff = True
        light.data.shadow_soft_size = 0.1
        light.data.use_shadow = use_shadow

    def add_sun_light(
        self,
        position: PyVector3D = (0, 0, 0),
        rotation: PyVector3D = (0, 0, 0),
        energy: float = 5.0,
        angle: float = 0.0,
        use_shadow: bool = True,
    ) -> None:
        bpy.ops.object.light_add(type="SUN")
        light = bpy.context.selected_objects[0]
        transform(light, position=position, rotation=rotation)
        light.data.energy = energy
        light.data.angle = radians(angle)
        light.data.use_shadow = use_shadow

    def compute_bounding_sphere(self) -> tuple[Vector, float]:
        min_x, min_y, min_z = [math.inf for _ in range(3)]
        max_x, max_y, max_z = [-math.inf for _ in range(3)]
        for obj in bpy.context.scene.objects:
            if is_mesh(obj) and obj.visible_get():
                for v in obj.data.vertices:
                    world_v = obj.matrix_world @ v.co
                    min_x = min(min_x, world_v.x)
                    min_y = min(min_y, world_v.y)
                    min_z = min(min_z, world_v.z)
                    max_x = max(max_x, world_v.x)
                    max_y = max(max_y, world_v.y)
                    max_z = max(max_z, world_v.z)
        center = Vector(((min_x + max_x) / 2, (min_y + max_y) / 2, (min_z + max_z) / 2))
        radius = (Vector((max_x, max_y, max_z)) - center).length
        return center, radius

    def render_panoramic(self, output_png: str, position: PyVector3D, resolution: int = 512) -> bool:
        render = bpy.context.scene.render
        render.resolution_x = resolution * 2
        render.resolution_y = resolution

        bpy.ops.object.camera_add()
        camera = bpy.context.selected_objects[0]
        bpy.context.scene.camera = camera
        transform(camera, position=position, rotation=(90, 0, 0))
        camera.data.type = "PANO"
        camera.data.panorama_type = "EQUIRECTANGULAR"
        try:
            bpy.context.scene.render.filepath = output_png
            bpy.ops.render.render(write_still=True)
        finally:
            bpy.data.objects.remove(camera, do_unlink=True)
        return exists(output_png)

    @overload
    def render_perspective(
        self,
        output_png: str,
        position_or_center: PyVector3D,
        radius: Literal[None] = None,
        rotation: PyVector3D = ...,
        resolution: int = ...,
    ) -> bool: ...

    @overload
    def render_perspective(
        self,
        output_png: str,
        position_or_center: Vector,
        radius: float,
        rotation: PyVector3D = ...,
        resolution: int = ...,
    ) -> bool: ...

    def render_perspective(
        self,
        output_png: str,
        position_or_center: PyVector3D | Vector,
        radius: Optional[float] = None,
        rotation: PyVector3D = (0, 0, 0),
        resolution: int = 1024,
    ) -> bool:
        def set_camera(camera: Object, fov_degree: float = 39.6, fill_ratio: float = 1.0) -> None:
            camera.data.type = "PERSP"
            camera.data.lens_unit = "FOV"
            camera.data.angle = radians(fov_degree)
            camera.data.clip_start = 0.01
            if radius is not None:
                # fit bounding sphere
                direction = Euler(map(radians, rotation)).to_matrix() @ Vector((0, 0, -1))
                adjusted_fov = camera.data.angle * fill_ratio
                distance = radius / sin(adjusted_fov / 2)
                transform(camera, position=position_or_center - direction * distance, rotation=rotation)
                camera.data.clip_end = distance + 2 * radius
            else:
                # use explicit camera position
                transform(camera, position=position_or_center, rotation=rotation)
                camera.data.clip_end = 1000.0

        render = bpy.context.scene.render
        render.resolution_x = resolution
        render.resolution_y = resolution

        bpy.ops.object.camera_add()
        camera = bpy.context.selected_objects[0]
        bpy.context.scene.camera = camera
        try:
            set_camera(camera)
            bpy.context.scene.render.filepath = output_png
            bpy.ops.render.render(write_still=True)
        finally:
            bpy.data.objects.remove(camera, do_unlink=True)
        return exists(output_png)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("codes", nargs="+", type=str)
    argv = sys.argv[sys.argv.index("--") + 1 :]
    args = parser.parse_args(argv)
    digits = len(str(len(args.codes)))
    for i, line in enumerate(args.codes, start=1):
        print(f"[{i:0{digits}}] {line}", flush=True)
        try:
            exec(line)
        except KeyboardInterrupt:
            raise
        except BaseException as e:
            err_name = f"{e.__class__.__module__}.{e.__class__.__name__}"
            err_msg = f"{str(e)}\n|\nv\n{traceback.format_exc()}\n"
            print(f"\n[{__file__}] {err_name}: {err_msg}", flush=True)
            sys.exit(-1)
