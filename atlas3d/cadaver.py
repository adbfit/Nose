"""Photographic 'cadaveric dissection' look: tissue materials, drape, macro-photo lighting.

Colours follow the appearance of fresh-frozen specimens used in nasal filler anatomy
studies (pale greyish skin, bright yellow lobulated fat, dark red-brown muscle, pearly
hyaline cartilage, latex-injected arteries). Every material varies its albedo, wetness
and relief with procedural noise, because uniform colour is what makes a render read as CGI.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import bpy
import numpy as np
from mathutils import Vector

from .render import MM, srgb


@dataclass
class Tissue:
    colors: list                       # albedo palette (sRGB), mixed by low-frequency noise
    variation_mm: float = 6.0          # size of the albedo blotches
    sss: float = 0.5
    sss_radius: tuple = (1.0, 0.4, 0.2)
    sss_mm: float = 1.0
    roughness: tuple = (0.35, 0.6)     # wet ... dry, modulated by noise
    wet: float = 0.5                   # clear-coat film (moisture on dissected tissue)
    relief: list = field(default_factory=list)   # (kind, size_mm, strength)
    specular: float = 0.5
    septa: bool = False                # whitish fibrous septa between fat lobules
    fibers: str | None = None          # "procerus_nasalis" orientation map for muscle
    alpha: float = 1.0


TISSUES = {
    "skin": Tissue([(0.80, 0.66, 0.58), (0.74, 0.58, 0.52), (0.82, 0.70, 0.60), (0.70, 0.55, 0.52)],
                   variation_mm=5.0, sss=0.9, sss_radius=(1.0, 0.42, 0.25), sss_mm=1.4,
                   roughness=(0.38, 0.62), wet=0.08,
                   relief=[("pores", 0.30, 0.45), ("wrinkles", 2.5, 0.25), ("noise", 0.12, 0.12)]),
    "skin_cut": Tissue([(0.93, 0.84, 0.76), (0.90, 0.78, 0.72), (0.95, 0.88, 0.78)], variation_mm=0.8,
                       sss=0.6, sss_radius=(1.0, 0.6, 0.45), sss_mm=0.6, roughness=(0.3, 0.5), wet=0.35,
                       relief=[("noise", 0.15, 0.35)]),
    "superficial_fat": Tissue([(0.95, 0.76, 0.28), (0.90, 0.66, 0.20), (0.97, 0.83, 0.40), (0.88, 0.60, 0.22)],
                              variation_mm=2.5, sss=0.8, sss_radius=(1.0, 0.75, 0.3), sss_mm=1.8,
                              roughness=(0.12, 0.35), wet=0.7, septa=True,
                              relief=[("lobules", 1.1, 0.30), ("noise", 0.2, 0.15)]),
    "deep_fat": Tissue([(0.96, 0.84, 0.46), (0.93, 0.76, 0.36), (0.98, 0.88, 0.56)], variation_mm=2.0,
                       sss=0.8, sss_radius=(1.0, 0.8, 0.4), sss_mm=1.5, roughness=(0.12, 0.3), wet=0.75,
                       septa=True, relief=[("lobules", 0.9, 0.25)]),
    "smas": Tissue([(0.45, 0.12, 0.09), (0.38, 0.09, 0.07), (0.55, 0.18, 0.13), (0.50, 0.20, 0.16)],
                   variation_mm=3.0, sss=0.55, sss_radius=(0.9, 0.22, 0.1), sss_mm=0.7,
                   roughness=(0.18, 0.4), wet=0.65, fibers="procerus_nasalis",
                   relief=[("noise", 0.25, 0.12)]),
    "bone": Tissue([(0.93, 0.90, 0.83), (0.88, 0.82, 0.74), (0.94, 0.91, 0.86), (0.86, 0.76, 0.70)],
                   variation_mm=3.0, sss=0.25, sss_radius=(1.0, 0.8, 0.6), sss_mm=0.6,
                   roughness=(0.3, 0.55), wet=0.35, relief=[("pits", 0.35, 0.3), ("noise", 1.5, 0.2)]),
    "cartilage": Tissue([(0.74, 0.78, 0.82), (0.80, 0.80, 0.82), (0.70, 0.74, 0.80), (0.82, 0.76, 0.76)],
                        variation_mm=2.0, sss=1.0, sss_radius=(0.7, 0.8, 1.0), sss_mm=1.6,
                        roughness=(0.12, 0.3), wet=0.45, relief=[("noise", 0.6, 0.12), ("noise", 3.0, 0.1)]),
    "cartilage_cut": Tissue([(0.90, 0.92, 0.93)], sss=0.9, sss_radius=(0.8, 0.85, 1.0), sss_mm=0.6,
                            roughness=(0.1, 0.2), wet=0.6),
    "fat_cut": Tissue([(0.96, 0.80, 0.34), (0.92, 0.70, 0.26)], variation_mm=1.0, sss=0.8,
                      sss_radius=(1.0, 0.75, 0.3), sss_mm=1.6, roughness=(0.15, 0.35), wet=0.6, septa=True,
                      relief=[("lobules", 0.9, 0.3)]),
    "smas_cut": Tissue([(0.40, 0.10, 0.08), (0.48, 0.14, 0.10)], variation_mm=1.0, sss=0.5,
                       sss_radius=(0.9, 0.22, 0.1), sss_mm=0.6, roughness=(0.2, 0.35), wet=0.6,
                       relief=[("noise", 0.2, 0.2)]),
    "bone_cut": Tissue([(0.93, 0.88, 0.76), (0.90, 0.80, 0.64), (0.93, 0.87, 0.74), (0.66, 0.34, 0.28),
                        (0.92, 0.85, 0.72)], variation_mm=0.35, sss=0.25,
                       roughness=(0.4, 0.6), wet=0.3, relief=[("pits", 0.3, 0.6)]),
    "mucosa": Tissue([(0.52, 0.17, 0.18), (0.44, 0.12, 0.14), (0.60, 0.24, 0.24)], variation_mm=2.0,
                     sss=0.4, sss_radius=(1.0, 0.3, 0.2), sss_mm=0.8, roughness=(0.25, 0.45), wet=0.25,
                     relief=[("noise", 0.5, 0.25), ("noise", 3.0, 0.6)]),
    "filler": Tissue([(0.78, 0.86, 0.95)], sss=0.6, sss_radius=(0.9, 0.95, 1.0), sss_mm=3.0,
                     roughness=(0.05, 0.1), wet=0.9),
    "artery": Tissue([(0.72, 0.06, 0.05), (0.62, 0.04, 0.04), (0.78, 0.10, 0.07)], variation_mm=1.5,
                     sss=0.3, sss_radius=(1.0, 0.2, 0.1), sss_mm=0.3, roughness=(0.12, 0.25), wet=0.8),
    "drape": Tissue([(0.18, 0.40, 0.42), (0.15, 0.35, 0.38), (0.20, 0.44, 0.45)], variation_mm=12.0,
                    sss=0.0, roughness=(0.75, 0.95), wet=0.0, specular=0.25,
                    relief=[("weave", 0.35, 0.35), ("noise", 4.0, 0.2)]),
}

# structure -> (surface tissue, cut-surface tissue)
STRUCTURE_TISSUE = {
    "skin": ("skin", "skin_cut"),
    "superficial_fat": ("superficial_fat", "fat_cut"),
    "smas": ("smas", "smas_cut"),
    "deep_fat": ("deep_fat", "fat_cut"),
    "bone": ("bone", "bone_cut"),
    "upper_lateral_cartilage": ("cartilage", "cartilage_cut"),
    "lower_lateral_cartilage": ("cartilage", "cartilage_cut"),
    "septum": ("cartilage", "cartilage_cut"),
    "filler": ("filler", "filler"),
    "mucosa": ("mucosa", "mucosa"),
    "drape": ("drape", "drape"),
}


def _mapping(nt, size_mm, coord="Object"):
    tc = nt.nodes.new("ShaderNodeTexCoord")
    mp = nt.nodes.new("ShaderNodeMapping")
    mp.inputs["Scale"].default_value = (1.0 / (size_mm * MM),) * 3
    nt.links.new(tc.outputs[coord], mp.inputs["Vector"])
    return mp.outputs["Vector"]


def _noise(nt, size_mm, detail=4.0, rough=0.55, seed_offset=0.0):
    n = nt.nodes.new("ShaderNodeTexNoise")
    n.noise_dimensions = "4D"
    n.inputs["Scale"].default_value = 1.0
    n.inputs["Detail"].default_value = detail
    n.inputs["Roughness"].default_value = rough
    n.inputs["W"].default_value = seed_offset
    nt.links.new(_mapping(nt, size_mm), n.inputs["Vector"])
    return n


def _math(nt, op, a, b=None, clamp=False):
    m = nt.nodes.new("ShaderNodeMath")
    m.operation = op
    m.use_clamp = clamp
    for i, v in enumerate((a, b)):
        if v is None:
            continue
        if isinstance(v, (int, float)):
            m.inputs[i].default_value = v
        else:
            nt.links.new(v, m.inputs[i])
    return m.outputs[0]


def _relief(nt, kind, size_mm, strength):
    """Return a height socket for one relief layer."""
    links = nt.links
    vec = _mapping(nt, size_mm)
    if kind == "pores":
        vor = nt.nodes.new("ShaderNodeTexVoronoi")
        vor.inputs["Randomness"].default_value = 1.0
        links.new(vec, vor.inputs["Vector"])
        h = _math(nt, "POWER", _math(nt, "MINIMUM", _math(nt, "MULTIPLY", vor.outputs["Distance"], 3.0), 1.0), 0.5)
    elif kind == "wrinkles":
        wave = nt.nodes.new("ShaderNodeTexWave")
        wave.wave_type = "BANDS"
        wave.bands_direction = "Z"
        wave.wave_profile = "SAW"
        wave.inputs["Distortion"].default_value = 9.0
        wave.inputs["Detail"].default_value = 6.0
        wave.inputs["Detail Scale"].default_value = 2.0
        links.new(vec, wave.inputs["Vector"])
        h = wave.outputs["Fac"]
    elif kind == "lobules":
        vor = nt.nodes.new("ShaderNodeTexVoronoi")
        vor.feature = "DISTANCE_TO_EDGE"
        links.new(vec, vor.inputs["Vector"])
        h = _math(nt, "POWER", _math(nt, "MINIMUM", _math(nt, "MULTIPLY", vor.outputs["Distance"], 4.0), 1.0), 0.6)
    elif kind == "pits":
        vor = nt.nodes.new("ShaderNodeTexVoronoi")
        vor.feature = "F1"
        links.new(vec, vor.inputs["Vector"])
        h = _math(nt, "MINIMUM", _math(nt, "MULTIPLY", vor.outputs["Distance"], 2.5), 1.0)
    elif kind == "weave":
        wx = nt.nodes.new("ShaderNodeTexWave")
        wx.bands_direction = "X"
        wz = nt.nodes.new("ShaderNodeTexWave")
        wz.bands_direction = "Z"
        for w_ in (wx, wz):
            w_.inputs["Distortion"].default_value = 0.6
            links.new(vec, w_.inputs["Vector"])
        h = _math(nt, "MULTIPLY", wx.outputs["Fac"], wz.outputs["Fac"])
    else:
        h = _noise(nt, size_mm, detail=8.0, rough=0.7).outputs["Fac"]
    return _math(nt, "MULTIPLY", h, strength)


def _fibers(nt, rhinion_z_m):
    """Muscle striations: vertical (procerus) above the rhinion, transverse (nasalis) below."""
    links = nt.links
    out = []
    for direction in ("X", "Z"):
        wave = nt.nodes.new("ShaderNodeTexWave")
        wave.wave_type = "BANDS"
        wave.bands_direction = direction
        wave.inputs["Distortion"].default_value = 2.5
        wave.inputs["Detail"].default_value = 3.0
        links.new(_mapping(nt, 0.28), wave.inputs["Vector"])
        out.append(wave.outputs["Fac"])
    geo = nt.nodes.new("ShaderNodeNewGeometry")
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    links.new(geo.outputs["Position"], sep.inputs["Vector"])
    mr = nt.nodes.new("ShaderNodeMapRange")
    mr.interpolation_type = "SMOOTHSTEP"
    mr.inputs["From Min"].default_value = rhinion_z_m - 4 * MM
    mr.inputs["From Max"].default_value = rhinion_z_m + 4 * MM
    links.new(sep.outputs["Z"], mr.inputs["Value"])
    mix = nt.nodes.new("ShaderNodeMix")
    mix.data_type = "FLOAT"
    links.new(mr.outputs["Result"], mix.inputs["Factor"])
    links.new(out[1], mix.inputs["A"])   # below rhinion: transverse fibres (bands vary along z)
    links.new(out[0], mix.inputs["B"])   # above: vertical fibres (bands vary along x)
    return _math(nt, "MULTIPLY", mix.outputs["Result"], 0.35)


def tissue_material(name: str, t: Tissue, rhinion_z_mm: float = -18.0, seed: float = 0.0):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nt = mat.node_tree
    links = nt.links
    bsdf = nt.nodes["Principled BSDF"]
    bsdf.subsurface_method = "RANDOM_WALK_SKIN" if t.sss > 0.5 else "RANDOM_WALK"
    inp = bsdf.inputs

    # albedo: palette mixed by two octaves of noise
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    cols = t.colors
    ramp.color_ramp.elements[0].color = srgb(*cols[0])
    ramp.color_ramp.elements[1].color = srgb(*cols[-1])
    ramp.color_ramp.elements[1].position = 1.0
    for i, c in enumerate(cols[1:-1], start=1):
        el = ramp.color_ramp.elements.new(i / (len(cols) - 1))
        el.color = srgb(*c)
    n1 = _noise(nt, t.variation_mm, detail=5.0, rough=0.6, seed_offset=seed)
    links.new(n1.outputs["Fac"], ramp.inputs["Fac"])
    base = ramp.outputs["Color"]
    if t.septa:
        vor = nt.nodes.new("ShaderNodeTexVoronoi")
        vor.feature = "DISTANCE_TO_EDGE"
        links.new(_mapping(nt, 1.0), vor.inputs["Vector"])
        edge = _math(nt, "LESS_THAN", vor.outputs["Distance"], 0.035)
        mix = nt.nodes.new("ShaderNodeMix")
        mix.data_type = "RGBA"
        links.new(_math(nt, "MULTIPLY", edge, 0.55), mix.inputs["Factor"])
        links.new(base, mix.inputs["A"])
        mix.inputs["B"].default_value = srgb(0.93, 0.88, 0.78)
        base = mix.outputs["Result"]
    links.new(base, inp["Base Color"])

    inp["Subsurface Weight"].default_value = t.sss
    inp["Subsurface Radius"].default_value = t.sss_radius
    inp["Subsurface Scale"].default_value = t.sss_mm * MM
    inp["Specular IOR Level"].default_value = t.specular
    inp["Alpha"].default_value = t.alpha

    # wet / dry patches: roughness and coat vary together
    n2 = _noise(nt, 3.0, detail=3.0, rough=0.5, seed_offset=seed + 7.0)
    rr = nt.nodes.new("ShaderNodeMapRange")
    rr.inputs["To Min"].default_value = t.roughness[0]
    rr.inputs["To Max"].default_value = t.roughness[1]
    links.new(n2.outputs["Fac"], rr.inputs["Value"])
    links.new(rr.outputs["Result"], inp["Roughness"])
    if t.wet > 0:
        cw = nt.nodes.new("ShaderNodeMapRange")
        cw.inputs["To Min"].default_value = t.wet
        cw.inputs["To Max"].default_value = t.wet * 0.35
        links.new(n2.outputs["Fac"], cw.inputs["Value"])
        links.new(cw.outputs["Result"], inp["Coat Weight"])
        inp["Coat Roughness"].default_value = 0.04
        inp["Coat IOR"].default_value = 1.33

    heights = [_relief(nt, k, s, st) for k, s, st in t.relief]
    if t.fibers:
        heights.append(_fibers(nt, rhinion_z_mm * MM))
    if heights:
        acc = heights[0]
        for h in heights[1:]:
            acc = _math(nt, "ADD", acc, h)
        bump = nt.nodes.new("ShaderNodeBump")
        bump.inputs["Strength"].default_value = 1.0
        bump.inputs["Distance"].default_value = 0.08 * MM
        links.new(acc, bump.inputs["Height"])
        links.new(bump.outputs["Normal"], inp["Normal"])
        if t.wet > 0:
            # the moisture film smooths the micro relief
            coat_bump = nt.nodes.new("ShaderNodeBump")
            coat_bump.inputs["Strength"].default_value = 0.35
            coat_bump.inputs["Distance"].default_value = 0.08 * MM
            links.new(acc, coat_bump.inputs["Height"])
            links.new(coat_bump.outputs["Normal"], inp["Coat Normal"])
    return mat


def setup_photo_lights(target_mm, cam_obj, cam_dir):
    """Dissection-room photography: big overhead softbox + ring flash around the lens."""
    from .render import _area_light
    tgt = np.asarray(target_mm) * MM
    d = cam_dir / np.linalg.norm(cam_dir)
    up = np.array([0.0, 0.0, 1.0])
    right = np.cross(d, up)
    if np.linalg.norm(right) < 1e-3:
        right = np.array([1.0, 0.0, 0.0])
    right /= np.linalg.norm(right)
    up2 = np.cross(right, d)
    _area_light("softbox", tgt + 0.7 * (0.55 * d + 0.8 * up2 - 0.25 * right), tgt, (0.9, 0.6), 7.0,
                (1.0, 0.97, 0.93))
    _area_light("side", tgt + 0.6 * (0.5 * d + 0.9 * right), tgt, (0.4, 0.6), 1.5, (0.95, 0.97, 1.0))
    cam_loc = np.array(cam_obj.location)
    ring = bpy.data.lights.new("ringflash", "AREA")
    ring.shape = "DISK"
    ring.size = 0.12
    ring.energy = 0.8
    ring.color = (1.0, 0.98, 0.95)
    obj = bpy.data.objects.new("ringflash", ring)
    obj.location = tuple(cam_loc + 0.02 * up2)
    obj.rotation_euler = (Vector(tuple(tgt)) - obj.location).to_track_quat("-Z", "Y").to_euler()
    bpy.context.scene.collection.objects.link(obj)


def setup_photo_world():
    world = bpy.data.worlds.new("dissection_room")
    bpy.context.scene.world = world
    world.use_nodes = True
    bg = world.node_tree.nodes["Background"]
    bg.inputs["Color"].default_value = srgb(0.05, 0.06, 0.06)
    bg.inputs["Strength"].default_value = 0.5


def photo_color_management():
    view = bpy.context.scene.view_settings
    view.view_transform = "AgX"
    try:
        view.look = "AgX - Punchy"
    except TypeError:
        pass
    view.exposure = -0.2
