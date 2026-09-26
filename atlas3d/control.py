"""Control maps for the hybrid 'render -> photograph' step.

After the Cycles render, the same scene is rendered again with flat emission colours per
tissue (segmentation) and a normalised depth pass. From these we derive an edge map. A
diffusion model conditioned on depth + edges (see genera_foto.py) can then add photographic
texture while the anatomy stays exactly where the literature-based model put it.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

# tissue id -> (sRGB colour for the segmentation map, English prompt fragment)
SEGMENTS = {
    "background": ((0, 0, 0), ""),
    "skin": ((230, 190, 170), "pale cadaveric skin with pores and fine wrinkles"),
    "skin_cut": ((255, 240, 225), "white dense dermis at the incision margin"),
    "superficial_fat": ((250, 200, 60), "bright yellow lobulated subcutaneous fat with thin fibrous septa"),
    "deep_fat": ((255, 225, 120), "pale yellow deep fatty layer, glistening"),
    "fat_cut": ((240, 180, 40), "cut surface of yellow fat lobules"),
    "smas": ((150, 30, 25), "dark red nasal SMAS muscle fibres (procerus, transverse nasalis) under thin fascia"),
    "smas_cut": ((120, 20, 20), "cut muscle"),
    "bone": ((235, 225, 200), "ivory nasal bone covered by periosteum"),
    "bone_cut": ((210, 170, 140), "sawn cancellous bone with red marrow"),
    "cartilage": ((180, 200, 230), "pearly bluish translucent hyaline cartilage with perichondrium"),
    "cartilage_cut": ((200, 220, 245), "cut hyaline cartilage"),
    "mucosa": ((190, 70, 80), "moist pink-red nasal mucosa"),
    "filler": ((120, 190, 255), "clear translucent hyaluronic acid gel bolus"),
    "artery": ((255, 0, 0), "red latex-injected arteries"),
    "drape": ((20, 110, 110), "teal surgical drape"),
}


def _emission_material(name, rgb):
    import bpy
    from .render import srgb
    mat = bpy.data.materials.new(f"seg_{name}")
    mat.use_nodes = True
    nt = mat.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    em = nt.nodes.new("ShaderNodeEmission")
    em.inputs["Color"].default_value = srgb(*(c / 255.0 for c in rgb))
    em.inputs["Strength"].default_value = 1.0
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    nt.links.new(em.outputs["Emission"], out.inputs["Surface"])
    return mat


def render_control_maps(out_stem: Path, structure_tissues: dict) -> dict:
    """Render segmentation + depth for the current scene. `structure_tissues` maps object
    name -> (surface tissue, cut tissue). Returns the paths written."""
    import bpy
    scene = bpy.context.scene
    mats = {k: _emission_material(k, rgb) for k, (rgb, _) in SEGMENTS.items()}
    for obj in scene.objects:
        if obj.type == "MESH":
            surf, cut = structure_tissues.get(obj.name, ("skin", "skin_cut"))
            slots = obj.data.materials
            n = len(slots)
            slots.clear()
            slots.append(mats[surf])
            if n > 1:
                slots.append(mats[cut])
        elif obj.type == "CURVE":
            obj.data.materials.clear()
            obj.data.materials.append(mats["artery"])
        elif obj.type == "LIGHT":
            obj.hide_render = True

    world = scene.world
    if world and world.use_nodes:
        bg = world.node_tree.nodes.get("Background")
        if bg:
            for link in list(bg.inputs["Color"].links):
                world.node_tree.links.remove(link)
            bg.inputs["Color"].default_value = (0, 0, 0, 1)
    scene.cycles.samples = 1
    scene.cycles.use_denoising = False
    scene.cycles.use_adaptive_sampling = False
    scene.cycles.filter_width = 0.01
    scene.render.film_transparent = False
    scene.render.dither_intensity = 0.0
    scene.view_settings.view_transform = "Standard"
    scene.view_settings.look = "None"
    scene.view_settings.exposure = 0.0
    if scene.camera.data.dof.use_dof:
        scene.camera.data.dof.use_dof = False

    # depth through the compositor, normalised and inverted (near = white, as ControlNet expects)
    scene.view_layers[0].use_pass_z = True
    scene.use_nodes = True
    nt = scene.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    rl = nt.nodes.new("CompositorNodeRLayers")
    comp = nt.nodes.new("CompositorNodeComposite")
    nt.links.new(rl.outputs["Image"], comp.inputs["Image"])
    # map the specimen depth range (camera distance -60 mm ... +80 mm) to white ... black
    target = scene.camera.get("target_distance", None)
    dist = float(target) if target else 0.3
    inv = nt.nodes.new("CompositorNodeMapRange")
    inv.use_clamp = True
    inv.inputs["From Min"].default_value = dist - 0.06
    inv.inputs["From Max"].default_value = dist + 0.08
    inv.inputs["To Min"].default_value = 1.0
    inv.inputs["To Max"].default_value = 0.0
    nt.links.new(rl.outputs["Depth"], inv.inputs["Value"])
    fo = nt.nodes.new("CompositorNodeOutputFile")
    fo.base_path = str(out_stem.parent)
    fo.format.file_format = "PNG"
    fo.format.color_mode = "BW"
    fo.format.color_depth = "8"
    fo.file_slots[0].path = f"{out_stem.name}_depth_"
    nt.links.new(inv.outputs["Value"], fo.inputs[0])

    seg_path = out_stem.parent / f"{out_stem.name}_seg.png"
    scene.render.image_settings.color_depth = "8"
    scene.render.filepath = str(seg_path)
    bpy.ops.render.render(write_still=True)

    # the file output node appends the frame number
    depth_written = sorted(out_stem.parent.glob(f"{out_stem.name}_depth_*.png"))
    depth_path = out_stem.parent / f"{out_stem.name}_depth.png"
    if depth_written:
        depth_written[-1].replace(depth_path)
    edges_path = out_stem.parent / f"{out_stem.name}_edges.png"
    make_edges(seg_path, depth_path, edges_path)
    return {"seg": seg_path.name, "depth": depth_path.name, "edges": edges_path.name}


def make_edges(seg_path: Path, depth_path: Path, out_path: Path):
    """Edges = tissue boundaries (segmentation changes) + depth discontinuities (silhouettes)."""
    from PIL import Image, ImageFilter
    seg = np.asarray(Image.open(seg_path).convert("RGB")).astype(np.int32)
    palette = np.array([v[0] for v in SEGMENTS.values()], np.int32)
    # snap to the palette (removes dithering / antialiasing residue)
    flat = seg.reshape(-1, 3)
    code = np.empty(len(flat), np.int32)
    for i in range(0, len(flat), 500_000):
        chunk = flat[i:i + 500_000]
        code[i:i + 500_000] = np.argmin(((chunk[:, None, :] - palette[None]) ** 2).sum(-1), axis=1)
    code = code.reshape(seg.shape[:2])
    Image.fromarray(palette[code].astype(np.uint8)).save(seg_path)
    e = np.zeros(code.shape, bool)
    e[:, 1:] |= code[:, 1:] != code[:, :-1]
    e[1:, :] |= code[1:, :] != code[:-1, :]
    if depth_path.exists():
        d = np.asarray(Image.open(depth_path)).astype(np.float32)
        d /= max(d.max(), 1.0)
        gy, gx = np.gradient(d)
        e |= (np.hypot(gx, gy) > 0.04) & (d > 0.001)
    img = Image.fromarray((e * 255).astype(np.uint8)).filter(ImageFilter.MaxFilter(3))
    img.save(out_path)


def build_prompt(tissues_visible: list, plate_title_en: str, view: str) -> dict:
    parts = [SEGMENTS[t][1] for t in tissues_visible if t in SEGMENTS and SEGMENTS[t][1]]
    angle = {"obliqua": "three-quarter oblique view", "frontale": "frontal view",
             "laterale": "lateral view", "basale": "basal view", "sagittale": "sagittal hemisection"}.get(view, "")
    prompt = (f"macro photograph of a fresh-frozen human cadaver dissection, {plate_title_en}, nose, {angle}, "
              + ", ".join(parts)
              + ", anatomy atlas photograph, wet glistening tissue, ring flash, 100mm macro lens, f/11, "
                "extremely detailed, sharp focus, natural colours")
    negative = ("illustration, drawing, cartoon, CGI, 3d render, plastic, wax, toy, smooth, blurry, "
                "text, watermark, labels, gloves, instruments, extra nose, deformed anatomy, "
                "oversaturated")
    return {"prompt": prompt, "negative_prompt": negative}


def write_manifest(out_stem: Path, maps: dict, prompt: dict, labels_px: list, title: str,
                   refs: list):
    data = {"image": f"{out_stem.name}.png", **maps, **prompt, "title": title,
            "labels_px": labels_px, "footer_refs": refs,
            "segments": {k: list(v[0]) for k, v in SEGMENTS.items()}}
    (out_stem.parent / f"{out_stem.name}_controllo.json").write_text(
        json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
