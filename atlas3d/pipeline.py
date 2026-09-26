"""High level orchestration: plates (tavole) -> fields -> meshes -> Blender -> PNG + provenance."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from .anatomy import Cut, NoseModel
from .meshing import extract
from .params import Params, measured_profile

VIEW_NAMES = ["frontale", "laterale", "obliqua", "basale", "superiore", "sagittale"]

NAMES = {
    "it": {
        "skin": "Cute", "superficial_fat": "Pannicolo adiposo superficiale",
        "smas": "SMAS nasale (strato fibromuscolare)", "deep_fat": "Strato adiposo profondo",
        "bone": "Osso nasale", "upper_lateral_cartilage": "Cartilagine laterale superiore",
        "lower_lateral_cartilage": "Cartilagine alare maggiore (crus laterale)",
        "septum": "Cartilagine settale", "filler": "Filler (piano sopraperiosteo)",
        "nasion": "Nasion", "rhinion": "Rhinion", "pronasale": "Pronasale (punta)",
        "subnasale": "Subnasale", "supratip": "Sopra-punta", "ala": "Ala del naso",
        "columella": "Columella", "piriform_aperture": "Apertura piriforme",
        "angular": "A. angolare", "lateral_nasal": "A. nasale laterale",
        "dorsal_nasal": "A. dorsale del naso", "columellar": "A. columellare",
    },
    "en": {
        "skin": "Skin", "superficial_fat": "Superficial fatty layer", "smas": "Nasal SMAS (fibromuscular layer)",
        "deep_fat": "Deep fatty layer", "bone": "Nasal bone", "upper_lateral_cartilage": "Upper lateral cartilage",
        "lower_lateral_cartilage": "Lower lateral cartilage (lateral crus)", "septum": "Septal cartilage",
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
           "filler_profilo": "Rinofiller: effetto sul profilo"},
    "en": {"cute": "External morphology", "strati": "Soft-tissue layers", "impalcatura": "Osteocartilaginous framework",
           "vascolare": "Arterial supply", "sezione": "Paramedian sagittal section",
           "filler": "Nasal filler: supraperiosteal plane",
           "filler_profilo": "Nasal filler: effect on the profile"},
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
    fields = model.evaluate(spacing, cut=cut, per_structure_cut=plate.per_structure_cut,
                            nose_only=plate.nose_only)
    log(f"campi SDF {fields.grid.shape} in {time.time() - t0:.1f}s")

    meshes = {}
    for name in plate.structures:
        if name not in fields.volumes:
            continue
        m = extract(fields, name)
        if not m.empty:
            meshes[name] = m
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
            look = R.LOOKS[name]
            red = tuple(lm.pronasale * R.MM) if name == "skin" else None
            fade = dict(x=model.half_x - 6.0, z_max=model.z_max - 1.0, z_min=model.z_min + 1.0, width=16.0)
            ghost = 0.12 if name in plate.ghost else None
            mats[name] = R.make_material(name, look, tip_redness=None if ghost else red, fade=fade,
                                         ghost=ghost)
            R.add_mesh(mesh, mats[name])
        if vessels:
            amat = R.make_material("artery", R.LOOKS["artery"])
            for v in vessels:
                R.add_vessel(v["name"], v["points"], v["radius"], amat)
        R.setup_world(background)
        frame = plate.frame_mm * (1.1 if view == "basale" else 1.0)
        _, cam_dir = R.setup_camera(target, view, frame)
        R.setup_lights(target, cam_dir)
        R.setup_render(width, height, samples, device=device)

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
        annotate(raw, final, title=TITLES[lang][plate_name], items=items if labels else [],
                 footer_refs=[short_ref(params.references[r]) for r in plate.refs], lang=lang,
                 background=background)
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


def short_ref(ref: dict) -> str:
    cit = ref["citation"]
    first_author = cit.split(",")[0].split(" ")[0]
    year = next((tok[:4] for tok in cit.replace(";", " ").split() if tok[:4].isdigit() and tok[:2] in ("19", "20")), "")
    et_al = " et al." if cit.count(",") > 1 else ""
    return f"{first_author}{et_al} {year}"
