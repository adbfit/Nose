"""High level orchestration: plates (tavole) -> fields -> meshes -> Blender -> PNG + provenance."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from .anatomy import Cut, NoseModel, Window
from .meshing import extract
from .params import Params, measured_profile

VIEW_NAMES = ["frontale", "laterale", "obliqua", "basale", "superiore", "sagittale"]

NAMES = {
    "it": {
        "skin": "Cute", "superficial_fat": "Pannicolo adiposo superficiale",
        "smas": "SMAS nasale (strato fibromuscolare)", "deep_fat": "Strato adiposo profondo",
        "bone": "Osso nasale", "upper_lateral_cartilage": "Cartilagine laterale superiore",
        "lower_lateral_cartilage": "Cartilagine alare maggiore (crus laterale)",
        "septum": "Cartilagine settale", "mucosa": "Mucosa nasale", "filler": "Filler (piano sopraperiosteo)",
        "nasion": "Nasion", "rhinion": "Rhinion", "pronasale": "Pronasale (punta)",
        "subnasale": "Subnasale", "supratip": "Sopra-punta", "ala": "Ala del naso",
        "columella": "Columella", "piriform_aperture": "Apertura piriforme",
        "angular": "A. angolare", "lateral_nasal": "A. nasale laterale",
        "dorsal_nasal": "A. dorsale del naso", "columellar": "A. columellare",
    },
    "en": {
        "skin": "Skin", "superficial_fat": "Superficial fatty layer", "smas": "Nasal SMAS (fibromuscular layer)",
        "deep_fat": "Deep fatty layer", "bone": "Nasal bone", "upper_lateral_cartilage": "Upper lateral cartilage",
        "lower_lateral_cartilage": "Lower lateral cartilage (lateral crus)", "septum": "Septal cartilage", "mucosa": "Nasal mucosa",
        "filler": "Filler (supraperiosteal plane)", "nasion": "Nasion", "rhinion": "Rhinion",
        "pronasale": "Pronasale (tip)", "subnasale": "Subnasale", "supratip": "Supratip", "ala": "Ala",
        "columella": "Columella", "piriform_aperture": "Piriform aperture", "angular": "Angular a.",
        "lateral_nasal": "Lateral nasal a.", "dorsal_nasal": "Dorsal nasal a.", "columellar": "Columellar a.",
    },
}

TITLES = {
    "it": {"cute": "Morfologia esterna", "strati": "Stratigrafia dei tessuti molli",
           "impalcatura": "Impalcatura osteocartilaginea", "vascolare": "Vascolarizzazione arteriosa",
           "sezione": "Sezione sagittale paramediana", "filler": "Rinofiller: piano sopraperiosteo",
           "filler_profilo": "Rinofiller: effetto sul profilo",
           "cadavere_cute": "Dissezione: regione nasale, cute integra",
           "cadavere_smas": "Dissezione: SMAS nasale e arterie (iniezione di lattice)",
           "cadavere_strati": "Dissezione stratigrafica del naso",
           "cadavere_impalcatura": "Dissezione: impalcatura osteocartilaginea (degloving)",
           "cadavere_sezione": "Emisezione sagittale paramediana",
           "cadavere_filler": "Emisezione sagittale: filler sopraperiosteo"},
    "en": {"cute": "External morphology", "strati": "Soft-tissue layers", "impalcatura": "Osteocartilaginous framework",
           "vascolare": "Arterial supply", "sezione": "Paramedian sagittal section",
           "filler": "Nasal filler: supraperiosteal plane",
           "filler_profilo": "Nasal filler: effect on the profile",
           "cadavere_cute": "Dissection: nasal region, intact skin",
           "cadavere_smas": "Dissection: nasal SMAS and arteries (latex injection)",
           "cadavere_strati": "Layered dissection of the nose",
           "cadavere_impalcatura": "Dissection: osteocartilaginous framework (degloving)",
           "cadavere_sezione": "Paramedian sagittal hemisection",
           "cadavere_filler": "Sagittal hemisection: supraperiosteal filler"},
}


@dataclass
class Plate:
    structures: list
    views: list
    arteries: bool = False
    cut: float | None = None
    per_structure_cut: dict = field(default_factory=dict)
    labels: list = field(default_factory=list)
    refs: list = field(default_factory=list)
    frame_mm: float = 92.0
    force_filler: bool = False
    nose_only: list = field(default_factory=list)
    ghost: list = field(default_factory=list)
    style: str = "illustrazione"     # or "cadavere" (photographic dissection)
    windows: dict = field(default_factory=dict)
    drape: bool = False


PLATES = {
    "cute": Plate(["skin"], ["frontale", "laterale", "obliqua", "basale"],
                  labels=["nasion", "rhinion", "supratip", "pronasale", "ala", "columella", "subnasale"],
                  refs=["farkas2005", "ballin2017"]),
    "strati": Plate(["skin", "superficial_fat", "smas", "deep_fat", "bone",
                     "upper_lateral_cartilage", "lower_lateral_cartilage"], ["obliqua", "laterale"],
                    per_structure_cut={"skin": 0.0, "superficial_fat": 3.0, "smas": 6.5, "deep_fat": 10.0},
                    labels=["skin", "superficial_fat", "smas", "deep_fat", "bone",
                            "upper_lateral_cartilage", "lower_lateral_cartilage"],
                    refs=["letourneau1988", "lessard1985"]),
    "impalcatura": Plate(["bone", "upper_lateral_cartilage", "lower_lateral_cartilage", "septum"],
                         ["obliqua", "frontale", "laterale", "basale"],
                         labels=["bone", "upper_lateral_cartilage", "lower_lateral_cartilage",
                                 "piriform_aperture", "rhinion"],
                         refs=["lessard1985"]),
    "vascolare": Plate(["skin", "smas", "bone", "upper_lateral_cartilage", "lower_lateral_cartilage"],
                       ["obliqua", "frontale", "laterale"], arteries=True, nose_only=["smas"],
                       ghost=["skin"],
                       labels=["angular", "lateral_nasal", "dorsal_nasal", "columellar", "smas"],
                       refs=["toriumi1996", "saban2012", "tansatit2021", "jiang2020", "ortizmiddleton2025"]),
    "sezione": Plate(["skin", "superficial_fat", "smas", "deep_fat", "bone",
                      "upper_lateral_cartilage", "lower_lateral_cartilage", "septum"],
                     ["sagittale"], cut=0.0,
                     labels=["skin", "superficial_fat", "smas", "deep_fat", "bone", "upper_lateral_cartilage",
                             "lower_lateral_cartilage", "septum", "rhinion", "nasion"],
                     refs=["letourneau1988", "lessard1985"]),
    "filler": Plate(["skin", "superficial_fat", "smas", "deep_fat", "bone",
                     "upper_lateral_cartilage", "lower_lateral_cartilage", "septum", "filler"],
                    ["sagittale"], cut=0.0, force_filler=True,
                    labels=["filler", "skin", "smas", "bone", "deep_fat", "nasion"],
                    refs=["vasconcelosberg2024", "alfertshofer2022", "ortizmiddleton2025", "beleznay2015"]),
    # ---------------- photographic cadaveric dissections ----------------
    "cadavere_cute": Plate(["skin", "drape"], ["obliqua", "frontale", "laterale"], style="cadavere",
                           drape=True, frame_mm=96.0,
                           labels=["nasion", "rhinion", "supratip", "pronasale", "ala", "columella"],
                           refs=["farkas2005", "ballin2017"]),
    "cadavere_smas": Plate(["skin", "superficial_fat", "smas", "drape"], ["obliqua", "frontale"],
                           style="cadavere", drape=True, arteries=True, frame_mm=96.0,
                           windows={"skin": Window((0.0, -21.0), (19.0, 26.5), 0.9, 1),
                                    "superficial_fat": Window((0.0, -21.0), (16.5, 24.0), 0.8, 2)},
                           labels=["skin", "superficial_fat", "smas", "dorsal_nasal", "lateral_nasal",
                                   "angular", "columellar"],
                           refs=["toriumi1996", "letourneau1988", "tansatit2021", "jiang2020",
                                 "ortizmiddleton2025"]),
    "cadavere_strati": Plate(["skin", "superficial_fat", "smas", "deep_fat", "bone",
                              "upper_lateral_cartilage", "lower_lateral_cartilage", "drape"],
                             ["obliqua", "frontale"], style="cadavere", drape=True, frame_mm=96.0,
                             windows={"skin": Window((0.0, -21.0), (19.5, 27.0), 0.9, 1),
                                      "superficial_fat": Window((0.0, -21.0), (16.0, 24.5), 0.8, 2),
                                      "smas": Window((0.0, -21.0), (12.5, 22.0), 0.7, 3),
                                      "deep_fat": Window((0.0, -21.0), (9.5, 19.5), 0.6, 4)},
                             labels=["skin", "superficial_fat", "smas", "deep_fat", "bone",
                                     "upper_lateral_cartilage", "lower_lateral_cartilage"],
                             refs=["letourneau1988", "lessard1985"]),
    "cadavere_impalcatura": Plate(["skin", "superficial_fat", "smas", "deep_fat", "bone",
                                   "upper_lateral_cartilage", "lower_lateral_cartilage", "septum", "drape"],
                                  ["obliqua", "frontale", "laterale"], style="cadavere", drape=True,
                                  frame_mm=96.0,
                                  windows={k: Window((0.0, -21.5), (18.5 - i * 0.6, 26.5 - i * 0.6), 0.8, 5 + i)
                                           for i, k in enumerate(["skin", "superficial_fat", "smas", "deep_fat"])},
                                  labels=["bone", "upper_lateral_cartilage", "lower_lateral_cartilage",
                                          "rhinion", "skin"],
                                  refs=["lessard1985", "letourneau1988"]),
    "cadavere_sezione": Plate(["skin", "superficial_fat", "smas", "deep_fat", "bone",
                               "upper_lateral_cartilage", "lower_lateral_cartilage", "septum", "mucosa"],
                              ["sagittale"], cut=2.2, style="cadavere",
                              labels=["skin", "superficial_fat", "smas", "deep_fat", "bone",
                                      "upper_lateral_cartilage", "lower_lateral_cartilage", "septum"],
                              refs=["letourneau1988", "lessard1985"]),
    "cadavere_filler": Plate(["skin", "superficial_fat", "smas", "deep_fat", "bone",
                              "upper_lateral_cartilage", "lower_lateral_cartilage", "septum", "mucosa",
                              "filler"],
                             ["sagittale"], cut=2.2, style="cadavere", force_filler=True,
                             labels=["filler", "skin", "smas", "bone", "deep_fat", "nasion"],
                             refs=["vasconcelosberg2024", "alfertshofer2022", "ortizmiddleton2025",
                                   "beleznay2015"]),
    "filler_profilo": Plate(["skin"], ["laterale", "obliqua"], force_filler=True,
                            labels=["nasion", "rhinion", "pronasale"],
                            refs=["vasconcelosberg2024", "alfertshofer2022"]),
}


def log(msg):
    print(f"[atlas3d] {msg}", flush=True)


def provenance(params: Params, model: NoseModel, plate_name: str, plate: Plate, extra: dict) -> dict:
    entries = {}
    for key, entry in params.items():
        entries[key] = {k: entry.get(k) for k in ("value", "unit", "evidence", "refs", "note") if k in entry}
    used_refs = set(plate.refs)
    for e in entries.values():
        used_refs.update(e.get("refs") or [])
    return {
        "plate": plate_name,
        "generated": time.strftime("%Y-%m-%d %H:%M:%S"),
        "overrides": params.overrides,
        "profile_check": {k: round(float(v), 3) for k, v in measured_profile(model.lm).items()},
        "parameters": entries,
        "plate_references": {r: params.references[r] for r in plate.refs},
        "all_references": {r: params.references[r] for r in sorted(used_refs) if r in params.references},
        "disclaimer": ("Illustrazione procedurale basata su parametri tratti dalla letteratura. "
                       "Valori con evidence 'qualitative'/'illustrative' sono stime di modellazione; "
                       "non rappresenta un singolo paziente né sostituisce la dissezione o l'imaging."),
        **extra,
    }


def render_plate(params: Params, plate_name: str, out_dir: Path, *, views=None, width=1800,
                 height=None, samples=192, spacing=0.3, lang="it", labels=True,
                 background="dark", export_glb=False, seed=7, device="cpu") -> list[Path]:
    from . import render as R  # bpy is imported lazily so that the core stays usable without it
    from .labels import annotate

    plate = PLATES[plate_name]
    if plate.force_filler and not params["filler.enabled"]:
        params.entry("filler.enabled")["value"] = True
    model = NoseModel(params)
    t0 = time.time()
    cut = Cut(plate.cut) if plate.cut is not None else None
    cadaver = plate.style == "cadavere"
    fields = model.evaluate(spacing, cut=cut, per_structure_cut=plate.per_structure_cut,
                            nose_only=plate.nose_only, windows=plate.windows, detail=cadaver,
                            drape=plate.drape)
    log(f"campi SDF {fields.grid.shape} in {time.time() - t0:.1f}s")

    meshes, cut_faces = {}, {}
    for name in plate.structures:
        if name not in fields.volumes:
            continue
        m = extract(fields, name, smooth_iterations=3 if cadaver else 4)
        if not m.empty:
            meshes[name] = m
            cut_faces[name] = _cut_faces(fields, name, m)
    vessels = model.arteries(fields, seed=seed) if plate.arteries else []
    if plate.arteries and cut is not None:
        vessels = [dict(v, points=v["points"][v["points"][:, 0] < cut.limit]) for v in vessels]
        vessels = [v for v in vessels if len(v["points"]) >= 2]
    log(f"mesh: " + ", ".join(f"{k}={len(m.faces)}" for k, m in meshes.items()))

    anchors = model.label_anchors(fields)
    lm = model.lm
    target = 0.5 * (lm.nasion + lm.subnasale) + np.array([0.0, 2.0, -2.0])
    out_dir.mkdir(parents=True, exist_ok=True)
    height = height or int(width * 1.15)
    written = []

    for view in views or plate.views:
        R.reset_scene()
        mats = {}
        for name, mesh in meshes.items():
            if cadaver:
                from . import cadaver as C
                surf, cutname = C.STRUCTURE_TISSUE[name]
                rz = float(lm.rhinion[2])
                pair = [C.tissue_material(f"{name}_{surf}", C.TISSUES[surf], rz, seed=hash(name) % 17),
                        C.tissue_material(f"{name}_{cutname}", C.TISSUES[cutname], rz, seed=3.0)]
                R.add_mesh(mesh, pair, cut_faces[name].astype(np.int32))
                continue
            look = R.LOOKS[name]
            red = tuple(lm.pronasale * R.MM) if name == "skin" else None
            fade = dict(x=model.half_x - 6.0, z_max=model.z_max - 1.0, z_min=model.z_min + 1.0, width=16.0)
            ghost = 0.12 if name in plate.ghost else None
            mats[name] = R.make_material(name, look, tip_redness=None if ghost else red, fade=fade,
                                         ghost=ghost)
            R.add_mesh(mesh, mats[name])
        if vessels:
            if cadaver:
                from . import cadaver as C
                amat = C.tissue_material("artery", C.TISSUES["artery"])
            else:
                amat = R.make_material("artery", R.LOOKS["artery"])
            for v in vessels:
                R.add_vessel(v["name"], v["points"], v["radius"], amat)
        frame = plate.frame_mm * (1.1 if view == "basale" else 1.0)
        cam_obj, cam_dir = R.setup_camera(target, view, frame, lens_mm=100.0 if cadaver else 105.0,
                                          dof=cadaver)
        if cadaver:
            from . import cadaver as C
            C.setup_photo_world()
            C.setup_photo_lights(target, cam_obj, cam_dir)
        else:
            R.setup_world(background)
            R.setup_lights(target, cam_dir)
        R.setup_render(width, height, samples, device=device)
        if cadaver:
            C.photo_color_management()

        stem = f"{plate_name}_{view}"
        raw = out_dir / f"{stem}_raw.png"
        t1 = time.time()
        R.render_to(str(raw))
        log(f"render {stem}: {time.time() - t1:.1f}s")

        final = out_dir / f"{stem}.png"
        label_items = []
        if labels:
            for key in plate.labels:
                if key in ("angular", "lateral_nasal", "dorsal_nasal", "columellar"):
                    cands = [v for v in vessels if v["label"] == key]
                    if not cands:
                        continue
                    pts = cands[0]["points"]
                    # pick the vessel point nearest the camera side
                    score = pts @ cam_dir
                    q = pts[int(np.argmax(score[len(pts) // 4: 3 * len(pts) // 4 + 1])) + len(pts) // 4]
                else:
                    q = anchors.get(key)
                if q is None:
                    continue
                label_items.append((NAMES[lang][key], q))
        projected = R.project([q for _, q in label_items], width, height)
        items = [(name, xy) for (name, _), xy in zip(label_items, projected)
                 if xy is not None and 0 <= xy[0] < width and 0 <= xy[1] < height and xy[2] > 0]
        refs_short = [short_ref(params.references[r]) for r in plate.refs]
        if cadaver:
            from .labels import photo_finish
            photo_finish(raw, final)
            if labels:
                annotate(final, out_dir / f"{stem}_etichette.png", title=TITLES[lang][plate_name],
                         items=items, footer_refs=refs_short, lang=lang, background="dark")
        else:
            annotate(raw, final, title=TITLES[lang][plate_name], items=items if labels else [],
                     footer_refs=refs_short, lang=lang, background=background)
        raw.unlink(missing_ok=True)
        written.append(final)

        prov = provenance(params, model, plate_name, plate,
                          {"view": view, "image": final.name, "samples": samples,
                           "voxel_mm": spacing, "resolution": [width, height]})
        final.with_suffix(".json").write_text(json.dumps(prov, indent=2, ensure_ascii=False, default=float),
                                              encoding="utf-8")
        if export_glb:
            R.export_gltf(str(out_dir / f"{stem}.glb"))
    return written


def _cut_faces(fields, name: str, mesh) -> np.ndarray:
    """True for triangles lying on a dissection/section surface rather than an anatomical one:
    there the uncut structure is solid (its SDF is clearly negative)."""
    from scipy.interpolate import RegularGridInterpolator
    uncut = fields.uncut.get(name)
    if uncut is None:
        return np.zeros(len(mesh.faces), bool)
    centroids = mesh.vertices[mesh.faces].mean(axis=1)
    val = RegularGridInterpolator(fields.grid.axes, uncut, bounds_error=False, fill_value=1.0)(centroids)
    return val < -0.6 * fields.grid.spacing


def short_ref(ref: dict) -> str:
    cit = ref["citation"]
    first_author = cit.split(",")[0].split(" ")[0]
    year = next((tok[:4] for tok in cit.replace(";", " ").split() if tok[:4].isdigit() and tok[:2] in ("19", "20")), "")
    et_al = " et al." if cit.count(",") > 1 else ""
    return f"{first_author}{et_al} {year}"
