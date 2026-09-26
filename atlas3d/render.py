"""Blender / Cycles scene: physically based materials, studio lighting, cameras."""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

import bpy
from bpy_extras.object_utils import world_to_camera_view
from mathutils import Vector

from .meshing import Mesh

MM = 0.001  # scene unit is the metre; anatomy is modelled in millimetres


def srgb(r, g, b, a=1.0):
    def lin(c):
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
    return (lin(r), lin(g), lin(b), a)


# --------------------------------------------------------------------- materials
@dataclass
class Look:
    color: tuple
    sss_weight: float = 0.0
    sss_radius: tuple = (1.0, 0.4, 0.2)
    sss_scale: float = 1.0          # millimetres
    roughness: float = 0.5
    coat: float = 0.0
    coat_roughness: float = 0.2
    specular: float = 0.5
    transmission: float = 0.0
    ior: float = 1.4
    bump: str | None = None
    bump_strength: float = 0.2
    bump_scale: float = 1.0         # feature size in millimetres
    alpha: float = 1.0


LOOKS = {
    "skin": Look(srgb(0.78, 0.53, 0.43), sss_weight=1.0, sss_radius=(1.0, 0.36, 0.18), sss_scale=1.6,
                 roughness=0.42, coat=0.12, coat_roughness=0.35, bump="pores", bump_strength=0.32,
                 bump_scale=0.35),
    "superficial_fat": Look(srgb(0.96, 0.80, 0.38), sss_weight=0.9, sss_radius=(1.0, 0.8, 0.35),
                            sss_scale=1.2, roughness=0.28, coat=0.45, coat_roughness=0.12,
                            bump="lobules", bump_strength=0.35, bump_scale=1.4),
    "smas": Look(srgb(0.52, 0.15, 0.12), sss_weight=0.6, sss_radius=(0.9, 0.25, 0.12), sss_scale=0.8,
                 roughness=0.42, coat=0.55, coat_roughness=0.1, bump="fibers", bump_strength=0.28,
                 bump_scale=0.35),
    "deep_fat": Look(srgb(0.97, 0.88, 0.58), sss_weight=0.9, sss_radius=(1.0, 0.85, 0.5),
                     sss_scale=1.0, roughness=0.26, coat=0.5, coat_roughness=0.1,
                     bump="lobules", bump_strength=0.25, bump_scale=1.0),
    "bone": Look(srgb(0.90, 0.85, 0.72), sss_weight=0.2, sss_radius=(1.0, 0.8, 0.6), sss_scale=0.6,
                 roughness=0.55, bump="porous", bump_strength=0.25, bump_scale=0.25),
    "upper_lateral_cartilage": Look(srgb(0.80, 0.86, 0.88), sss_weight=0.75, sss_radius=(0.9, 0.9, 1.0),
                                    sss_scale=0.7, roughness=0.18, coat=0.7, coat_roughness=0.06,
                                    bump="porous", bump_strength=0.05, bump_scale=0.4),
    "lower_lateral_cartilage": Look(srgb(0.78, 0.85, 0.89), sss_weight=0.75, sss_radius=(0.9, 0.9, 1.0),
                                    sss_scale=0.7, roughness=0.18, coat=0.7, coat_roughness=0.06,
                                    bump="porous", bump_strength=0.05, bump_scale=0.4),
    "septum": Look(srgb(0.76, 0.83, 0.87), sss_weight=0.75, sss_radius=(0.9, 0.9, 1.0), sss_scale=0.7,
                   roughness=0.2, coat=0.6, coat_roughness=0.08),
    "filler": Look(srgb(0.35, 0.65, 1.0), transmission=0.55, ior=1.34, roughness=0.05, coat=0.5,
                   sss_weight=0.4, sss_radius=(0.6, 0.8, 1.0), sss_scale=1.5),
    "artery": Look(srgb(0.70, 0.05, 0.05), sss_weight=0.35, sss_radius=(1.0, 0.2, 0.1), sss_scale=0.3,
                   roughness=0.22, coat=0.8, coat_roughness=0.05),
}


def _bump_nodes(nt, look: Look):
    nodes, links = nt.nodes, nt.links
    coord = nodes.new("ShaderNodeTexCoord")
    mapping = nodes.new("ShaderNodeMapping")
    mapping.inputs["Scale"].default_value = (1.0 / (look.bump_scale * MM),) * 3
    links.new(coord.outputs["Object"], mapping.inputs["Vector"])
    bump = nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = look.bump_strength
    bump.inputs["Distance"].default_value = look.bump_scale * MM * 0.3

    if look.bump == "pores":
        vor = nodes.new("ShaderNodeTexVoronoi")
        vor.feature = "F1"
        vor.inputs["Randomness"].default_value = 1.0
        links.new(mapping.outputs["Vector"], vor.inputs["Vector"])
        ramp = nodes.new("ShaderNodeValToRGB")
        ramp.color_ramp.elements[0].position = 0.0
        ramp.color_ramp.elements[1].position = 0.18
        links.new(vor.outputs["Distance"], ramp.inputs["Fac"])
        noise = nodes.new("ShaderNodeTexNoise")
        noise.inputs["Scale"].default_value = 0.08
        noise.inputs["Detail"].default_value = 8.0
        noise.inputs["Roughness"].default_value = 0.65
        links.new(mapping.outputs["Vector"], noise.inputs["Vector"])
        mix = nodes.new("ShaderNodeMath")
        mix.operation = "MULTIPLY_ADD"
        mix.inputs[2].default_value = 0.0
        links.new(ramp.outputs["Color"], mix.inputs[0])
        mix.inputs[1].default_value = 0.8
        add = nodes.new("ShaderNodeMath")
        add.operation = "ADD"
        links.new(mix.outputs[0], add.inputs[0])
        links.new(noise.outputs["Fac"], add.inputs[1])
        height = add.outputs[0]
    elif look.bump == "fibers":
        wave = nodes.new("ShaderNodeTexWave")
        wave.wave_type = "BANDS"
        wave.bands_direction = "Z"
        wave.inputs["Scale"].default_value = 1.0
        wave.inputs["Distortion"].default_value = 6.0
        wave.inputs["Detail"].default_value = 4.0
        links.new(mapping.outputs["Vector"], wave.inputs["Vector"])
        height = wave.outputs["Fac"]
    elif look.bump == "lobules":
        vor = nodes.new("ShaderNodeTexVoronoi")
        vor.feature = "SMOOTH_F1"
        vor.inputs["Smoothness"].default_value = 0.6
        links.new(mapping.outputs["Vector"], vor.inputs["Vector"])
        height = vor.outputs["Distance"]
    else:  # porous
        noise = nodes.new("ShaderNodeTexNoise")
        noise.inputs["Scale"].default_value = 1.0
        noise.inputs["Detail"].default_value = 10.0
        noise.inputs["Roughness"].default_value = 0.7
        links.new(mapping.outputs["Vector"], noise.inputs["Vector"])
        height = noise.outputs["Fac"]
    links.new(height, bump.inputs["Height"])
    return bump


def make_material(name: str, look: Look, tip_redness: tuple | None = None, fade: dict | None = None,
                  ghost: float | None = None):
    if ghost is not None:
        look = Look(**{**look.__dict__, "alpha": ghost, "sss_weight": look.sss_weight * 0.3})
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nt = mat.node_tree
    bsdf = nt.nodes["Principled BSDF"]
    bsdf.subsurface_method = "RANDOM_WALK_SKIN" if look.sss_weight > 0.5 else "RANDOM_WALK"
    inp = bsdf.inputs
    inp["Base Color"].default_value = look.color
    inp["Subsurface Weight"].default_value = look.sss_weight
    inp["Subsurface Radius"].default_value = look.sss_radius
    inp["Subsurface Scale"].default_value = look.sss_scale * MM
    inp["Roughness"].default_value = look.roughness
    inp["Coat Weight"].default_value = look.coat
    inp["Coat Roughness"].default_value = look.coat_roughness
    inp["Specular IOR Level"].default_value = look.specular
    inp["Transmission Weight"].default_value = look.transmission
    inp["IOR"].default_value = look.ior
    inp["Alpha"].default_value = look.alpha
    if look.bump:
        bump = _bump_nodes(nt, look)
        nt.links.new(bump.outputs["Normal"], bsdf.inputs["Normal"])
        nt.links.new(bump.outputs["Normal"], bsdf.inputs["Coat Normal"])
    if tip_redness is None:
        if fade:
            _add_fade(nt, bsdf, fade)
        return mat

    if tip_redness is not None:
        # Natural skin is ruddier over the tip and alae; blend towards a redder tone
        # with distance from pronasale and add low-frequency mottling.
        nodes, links = nt.nodes, nt.links
        geo = nodes.new("ShaderNodeNewGeometry")
        dist = nodes.new("ShaderNodeVectorMath")
        dist.operation = "DISTANCE"
        dist.inputs[1].default_value = tip_redness
        links.new(geo.outputs["Position"], dist.inputs[0])
        ramp = nodes.new("ShaderNodeValToRGB")
        ramp.color_ramp.elements[0].position = 0.0
        ramp.color_ramp.elements[0].color = srgb(0.86, 0.52, 0.46)
        ramp.color_ramp.elements[1].position = 1.0
        ramp.color_ramp.elements[1].color = look.color
        scale = nodes.new("ShaderNodeMath")
        scale.operation = "DIVIDE"
        scale.inputs[1].default_value = 22 * MM
        links.new(dist.outputs["Value"], scale.inputs[0])
        links.new(scale.outputs[0], ramp.inputs["Fac"])
        noise = nodes.new("ShaderNodeTexNoise")
        noise.inputs["Scale"].default_value = 180.0
        noise.inputs["Detail"].default_value = 3.0
        mottle = nodes.new("ShaderNodeMix")
        mottle.data_type = "RGBA"
        mottle.blend_type = "MULTIPLY"
        mottle.inputs["Factor"].default_value = 0.12
        links.new(ramp.outputs["Color"], mottle.inputs["A"])
        links.new(noise.outputs["Color"], mottle.inputs["B"])
        links.new(mottle.outputs["Result"], bsdf.inputs["Base Color"])
        rough_noise = nodes.new("ShaderNodeMapRange")
        rough_noise.inputs["To Min"].default_value = look.roughness - 0.1
        rough_noise.inputs["To Max"].default_value = look.roughness + 0.1
        links.new(noise.outputs["Fac"], rough_noise.inputs["Value"])
        links.new(rough_noise.outputs["Result"], bsdf.inputs["Roughness"])
    if fade:
        _add_fade(nt, bsdf, fade)
    return mat


def _add_fade(nt, bsdf, fade: dict):
    """Fade the specimen edges into the background (atlas 'vignetted specimen' look)."""
    nodes, links = nt.nodes, nt.links
    geo = nodes.new("ShaderNodeNewGeometry")
    sep = nodes.new("ShaderNodeSeparateXYZ")
    links.new(geo.outputs["Position"], sep.inputs["Vector"])
    absx = nodes.new("ShaderNodeMath")
    absx.operation = "ABSOLUTE"
    links.new(sep.outputs["X"], absx.inputs[0])

    def ramp(src, a, b):
        mr = nodes.new("ShaderNodeMapRange")
        mr.interpolation_type = "SMOOTHSTEP"
        mr.inputs["From Min"].default_value = a * MM
        mr.inputs["From Max"].default_value = b * MM
        links.new(src, mr.inputs["Value"])
        return mr.outputs["Result"]

    w = fade.get("width", 10.0)
    terms = [ramp(absx.outputs[0], fade["x"] - w, fade["x"]),
             ramp(sep.outputs["Z"], fade["z_max"] - w, fade["z_max"]),
             ramp(sep.outputs["Z"], fade["z_min"] + w, fade["z_min"])]
    acc = terms[0]
    for t in terms[1:]:
        mx = nodes.new("ShaderNodeMath")
        mx.operation = "MAXIMUM"
        links.new(acc, mx.inputs[0])
        links.new(t, mx.inputs[1])
        acc = mx.outputs[0]
    transparent = nodes.new("ShaderNodeBsdfTransparent")
    mix = nodes.new("ShaderNodeMixShader")
    out = nodes["Material Output"]
    links.new(acc, mix.inputs["Fac"])
    links.new(bsdf.outputs["BSDF"], mix.inputs[1])
    links.new(transparent.outputs["BSDF"], mix.inputs[2])
    links.new(mix.outputs["Shader"], out.inputs["Surface"])


# ------------------------------------------------------------------------ scene
def reset_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.unit_settings.system = "METRIC"
    return scene


def add_mesh(mesh: Mesh, material, material_index: np.ndarray | None = None) -> bpy.types.Object:
    """Add a triangle mesh. `material` may be a list; `material_index` picks one per face."""
    me = bpy.data.meshes.new(mesh.name)
    verts = (mesh.vertices * MM).astype(np.float32)
    faces = mesh.faces.astype(np.int32)
    me.vertices.add(len(verts))
    me.vertices.foreach_set("co", verts.ravel())
    me.loops.add(faces.size)
    me.loops.foreach_set("vertex_index", faces.ravel())
    me.polygons.add(len(faces))
    me.polygons.foreach_set("loop_start", np.arange(0, faces.size, 3, dtype=np.int32))
    me.polygons.foreach_set("loop_total", np.full(len(faces), 3, dtype=np.int32))
    if material_index is not None:
        me.polygons.foreach_set("material_index", material_index.astype(np.int32))
    me.update(calc_edges=True)
    me.validate()
    me.polygons.foreach_set("use_smooth", np.ones(len(me.polygons), dtype=bool))
    # marching cubes emits inward-facing triangles for our "negative inside" convention
    me.flip_normals()
    obj = bpy.data.objects.new(mesh.name, me)
    for m in (material if isinstance(material, (list, tuple)) else [material]):
        obj.data.materials.append(m)
    bpy.context.scene.collection.objects.link(obj)
    return obj


def add_vessel(name: str, points_mm: np.ndarray, radius_mm: float, material) -> bpy.types.Object:
    curve = bpy.data.curves.new(name, "CURVE")
    curve.dimensions = "3D"
    curve.bevel_depth = radius_mm * MM
    curve.bevel_resolution = 6
    curve.use_fill_caps = True
    spline = curve.splines.new("NURBS")
    pts = np.asarray(points_mm) * MM
    spline.points.add(len(pts) - 1)
    for sp, q in zip(spline.points, pts):
        sp.co = (q[0], q[1], q[2], 1.0)
    spline.order_u = 4
    spline.use_endpoint_u = True
    # taper towards the periphery
    for i, sp in enumerate(spline.points):
        sp.radius = 1.0 - 0.45 * i / max(len(pts) - 1, 1)
    obj = bpy.data.objects.new(name, curve)
    obj.data.materials.append(material)
    bpy.context.scene.collection.objects.link(obj)
    return obj


def setup_world(background: str):
    world = bpy.data.worlds.new("studio")
    bpy.context.scene.world = world
    world.use_nodes = True
    nt = world.node_tree
    bg = nt.nodes["Background"]
    if background == "light":
        bg.inputs["Color"].default_value = srgb(0.93, 0.93, 0.94)
        bg.inputs["Strength"].default_value = 0.55
    else:
        # dark studio: subtle vertical gradient
        grad_coord = nt.nodes.new("ShaderNodeTexCoord")
        sep = nt.nodes.new("ShaderNodeSeparateXYZ")
        nt.links.new(grad_coord.outputs["Generated"], sep.inputs["Vector"])
        ramp = nt.nodes.new("ShaderNodeValToRGB")
        ramp.color_ramp.elements[0].color = srgb(0.015, 0.017, 0.022)
        ramp.color_ramp.elements[1].color = srgb(0.09, 0.10, 0.12)
        nt.links.new(sep.outputs["Z"], ramp.inputs["Fac"])
        nt.links.new(ramp.outputs["Color"], bg.inputs["Color"])
        bg.inputs["Strength"].default_value = 0.6


def _area_light(name, location, target, size, energy, color=(1, 1, 1)):
    light = bpy.data.lights.new(name, "AREA")
    light.shape = "RECTANGLE"
    light.size = size[0]
    light.size_y = size[1]
    light.energy = energy
    light.color = color
    obj = bpy.data.objects.new(name, light)
    obj.location = location
    direction = Vector(target) - Vector(location)
    obj.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()
    bpy.context.scene.collection.objects.link(obj)
    return obj


def setup_lights(target_mm, cam_dir: np.ndarray):
    """Three-point softbox rig oriented relative to the camera direction."""
    tgt = np.asarray(target_mm) * MM
    d = cam_dir / np.linalg.norm(cam_dir)
    up = np.array([0.0, 0.0, 1.0])
    right = np.cross(d, up)
    if np.linalg.norm(right) < 1e-3:
        right = np.array([1.0, 0.0, 0.0])
    right /= np.linalg.norm(right)
    up2 = np.cross(right, d)
    key = tgt + 0.55 * (d * 0.8 - right * 0.7 + up2 * 0.6)
    fill = tgt + 0.6 * (d * 0.9 + right * 0.9 + up2 * 0.1)
    rim = tgt + 0.5 * (-d * 0.7 + right * 0.5 + up2 * 0.9)
    under = tgt + 0.5 * (d * 0.6 - up2 * 0.9)
    _area_light("key", key, tgt, (0.35, 0.25), 14.0, (1.0, 0.95, 0.88))
    _area_light("fill", fill, tgt, (0.5, 0.5), 3.5, (0.88, 0.94, 1.0))
    _area_light("rim", rim, tgt, (0.2, 0.2), 12.0, (1.0, 1.0, 1.0))
    _area_light("bounce", under, tgt, (0.4, 0.4), 1.0, (1.0, 0.92, 0.85))


VIEWS = {
    # direction from the target towards the camera (patient's coordinates)
    "frontale": np.array([0.0, 1.0, 0.05]),
    "laterale": np.array([1.0, 0.12, 0.02]),
    "obliqua": np.array([0.75, 0.66, 0.12]),
    "basale": np.array([0.0, 0.55, -0.83]),
    "superiore": np.array([0.15, 0.55, 0.82]),
    "sagittale": np.array([1.0, 0.0, 0.0]),
}


def setup_camera(target_mm, view: str, frame_mm: float, lens_mm: float = 105.0,
                 dof: bool = False):
    direction = VIEWS[view]
    direction = direction / np.linalg.norm(direction)
    cam = bpy.data.cameras.new("camera")
    cam.lens = lens_mm
    cam.sensor_width = 36.0
    cam.clip_start = 0.01
    cam.clip_end = 10.0
    # distance so that frame_mm fits the sensor width
    dist = (lens_mm / 36.0) * frame_mm * MM
    obj = bpy.data.objects.new("camera", cam)
    tgt = np.asarray(target_mm) * MM
    obj.location = tuple(tgt + direction * dist)
    obj.rotation_euler = (Vector(tuple(tgt)) - obj.location).to_track_quat("-Z", "Y").to_euler()
    if dof:
        cam.dof.use_dof = True
        cam.dof.focus_distance = dist
        cam.dof.aperture_fstop = 11.0
    bpy.context.scene.collection.objects.link(obj)
    bpy.context.scene.camera = obj
    return obj, direction


def _enable_gpu() -> bool:
    prefs = bpy.context.preferences.addons["cycles"].preferences
    for backend in ("OPTIX", "CUDA", "HIP", "METAL", "ONEAPI"):
        try:
            prefs.compute_device_type = backend
        except TypeError:
            continue
        prefs.get_devices()
        gpus = [d for d in prefs.devices if d.type != "CPU"]
        if gpus:
            for d in prefs.devices:
                d.use = d.type != "CPU"
            return True
    return False


def setup_render(width: int, height: int, samples: int, transparent: bool = False,
                 device: str = "cpu"):
    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    scene.cycles.device = "GPU" if device == "gpu" and _enable_gpu() else "CPU"
    scene.cycles.samples = samples
    scene.cycles.use_adaptive_sampling = True
    scene.cycles.adaptive_threshold = 0.01
    scene.cycles.max_bounces = 12
    scene.cycles.transmission_bounces = 12
    scene.cycles.use_denoising = True
    try:
        scene.cycles.denoiser = "OPENIMAGEDENOISE"
    except TypeError:
        pass
    scene.render.resolution_x = width
    scene.render.resolution_y = height
    scene.render.resolution_percentage = 100
    scene.render.film_transparent = transparent
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_depth = "16"
    scene.view_settings.view_transform = "AgX"
    try:
        scene.view_settings.look = "AgX - Medium High Contrast"
    except TypeError:
        pass
    scene.render.threads_mode = "AUTO"


def project(points_mm, width, height) -> list:
    """Project 3D points (mm) to pixel coordinates in the rendered image."""
    scene = bpy.context.scene
    cam = scene.camera
    out = []
    for q in points_mm:
        if q is None:
            out.append(None)
            continue
        co = world_to_camera_view(scene, cam, Vector(tuple(np.asarray(q) * MM)))
        out.append((co.x * width, (1.0 - co.y) * height, co.z))
    return out


def render_to(path: str):
    bpy.context.scene.render.filepath = path
    bpy.ops.render.render(write_still=True)


def export_gltf(path: str):
    bpy.ops.export_scene.gltf(filepath=path, export_format="GLB", export_apply=True)
