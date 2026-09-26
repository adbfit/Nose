"""Photographic cadaveric plates of the whole face (BodyParts3D anatomy + literature arteries)."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from .arterie import REFERENCES, trace_arteries
from .catalogo import ATTRIBUTION, STRUTTURE
from .geometria import HalfWindow, Window, build_fields, load_face, mesh_from_sdf, mesh_from_trimesh

NOMI = {
    "it": {"skin": "Cute", "superficial_fat": "Tessuto adiposo sottocutaneo", "facial": "A. facciale",
           "labial": "A. labiale", "lateral_nasal": "A. nasale laterale", "dorsal_nasal": "A. dorsale del naso",
           "supratrochlear": "A. sopratrocleare", "supraorbital": "A. sopraorbitaria"},
    "en": {"skin": "Skin", "superficial_fat": "Subcutaneous fat", "facial": "Facial a.", "labial": "Labial a.",
           "lateral_nasal": "Lateral nasal a.", "dorsal_nasal": "Dorsal nasal a.",
           "supratrochlear": "Supratrochlear a.", "supraorbital": "Supraorbital a."},
}
MUSCOLI_ETICHETTATI = ["FMA46760", "FMA55611", "FMA55607", "FMA46783", "FMA46804", "FMA46813", "FMA46841",
                       "FMA46830", "FMA49002", "FMA46797"]


@dataclass
class TavolaVolto:
    title_it: str
    title_en: str
    views: list
    windows: dict = field(default_factory=dict)
    arteries: bool = False
    labels: list = field(default_factory=list)
    refs: list = field(default_factory=list)


TAVOLE = {
    "volto_cute": TavolaVolto("Volto: cute integra", "Face: intact skin", ["frontale", "obliqua", "laterale"],
                              refs=["bodyparts3d"]),
    "volto_emidissezione": TavolaVolto(
        "Emidissezione del volto: muscoli mimici e arterie", "Hemifacial dissection: mimetic muscles and arteries",
        ["frontale", "obliqua"], arteries=True,
        windows={"skin": HalfWindow((38.0, -30.0), (62.0, 100.0), 1.2, 1, side=1),
                 "superficial_fat": HalfWindow((38.0, -30.0), (57.0, 95.0), 1.0, 2, side=1)},
        labels=["skin", "facial", "supratrochlear", "supraorbital", "dorsal_nasal"] + MUSCOLI_ETICHETTATI,
        refs=["bodyparts3d", "trzeciak2025", "pourani2025", "cotofana2020", "kliniec2024"]),
    "volto_muscoli": TavolaVolto(
        "Dissezione del volto: piano muscolare e arterie", "Facial dissection: muscular plane and arteries",
        ["frontale", "obliqua", "laterale"], arteries=True,
        windows={"skin": Window((0.0, -30.0), (74.0, 100.0), 1.2, 3),
                 "superficial_fat": Window((0.0, -30.0), (69.0, 95.0), 1.0, 4)},
        labels=["facial", "labial", "supratrochlear", "supraorbital", "lateral_nasal"] + MUSCOLI_ETICHETTATI,
        refs=["bodyparts3d", "trzeciak2025", "pourani2025", "cotofana2020", "kliniec2024", "scheuer2017"]),
}


def _short(ref):
    c = ref["citation"]
    if c.startswith("BodyParts3D"):
        return "BodyParts3D (DBCLS)"
    first = c.split(",")[0].split(" ")[0]
    year = next((t[:4] for t in c.replace(";", " ").replace(".", " ").split() if t[:4].isdigit() and t[:2] in ("19", "20")), "")
    return f"{first} et al. {year}"


def _muscle_axis(mesh) -> np.ndarray:
    v = np.asarray(mesh.vertices) - np.asarray(mesh.vertices).mean(axis=0)
    _, _, vt = np.linalg.svd(v[:: max(1, len(v) // 4000)], full_matrices=False)
    return vt[0]


def render_face_plate(name: str, out_dir: Path, *, views=None, width=1400, samples=64, spacing=0.6,
                      lang="it", device="cpu", control_maps=True) -> list[Path]:
    from .. import cadaver as C
    from .. import control as K
    from .. import render as R
    from ..labels import annotate, photo_finish
    from ..pipeline import _cut_faces, log

    plate = TAVOLE[name]
    t0 = time.time()
    face = load_face()
    fields = build_fields(face, spacing=spacing, windows=plate.windows, drape=True)
    log(f"volto: campi {fields.grid.shape} in {time.time() - t0:.1f}s")

    derived = {}
    for key in ("skin", "superficial_fat", "drape"):
        m = mesh_from_sdf(key, fields.volumes[key], fields.grid, smooth=4)
        if not m.empty:
            derived[key] = m
    cut = {k: _cut_faces(fields, k, m) for k, m in derived.items()}
    vessels = trace_arteries(face, fields.grid, fields.skin_sdf) if plate.arteries else []
    if plate.windows:
        # show vessels only where the overlying tissue has been removed
        from scipy.interpolate import RegularGridInterpolator
        skin_now = RegularGridInterpolator(fields.grid.axes, fields.volumes["skin"], bounds_error=False, fill_value=1)
        keep = []
        for v in vessels:
            pts = v["points"]
            covered = np.array([skin_now([p + np.array([0, 3.0, 0])])[0] < 0 for p in pts])
            if (~covered).sum() >= 3:
                keep.append(dict(v, points=pts[~covered]))
        vessels = keep
    log(f"volto: mesh derivate {', '.join(f'{k}={len(m.faces)}' for k, m in derived.items())}, "
        f"arterie {len(vessels)}")

    lm = face.landmarks
    target = np.array([0.0, -8.0, -30.0])
    out_dir.mkdir(parents=True, exist_ok=True)
    height = int(width * 1.2)
    written = []
    tissues_obj = {}
    for view in views or plate.views:
        R.reset_scene()
        rz = float(lm["nasion"][2] - 20)
        for key, mesh in derived.items():
            surf, cutname = C.STRUCTURE_TISSUE[key]
            mats = [C.tissue_material(f"{key}_s", C.TISSUES[surf], rz, seed=1.0),
                    C.tissue_material(f"{key}_c", C.TISSUES[cutname], rz, seed=2.0)]
            R.add_mesh(mesh, mats, cut[key].astype(np.int32))
            tissues_obj[key] = C.STRUCTURE_TISSUE[key]
        for fma, tm in face.meshes.items():
            kind = STRUTTURE[fma][1]
            if kind in ("skin", "eyebrow"):
                continue
            mesh = mesh_from_trimesh(fma, tm)
            if kind == "muscle":
                mat = C.muscle_material(fma, _muscle_axis(tm), seed=float(int(fma[3:]) % 13))
                tissues_obj[fma] = ("smas", "smas_cut")
            else:
                tis = {"bone": "bone", "cartilage": "cartilage", "eye": "eye", "tooth": "tooth"}[kind]
                mat = C.tissue_material(fma, C.TISSUES[tis], rz, seed=3.0)
                tissues_obj[fma] = (tis if tis in K.SEGMENTS else "bone", "bone_cut")
            R.add_mesh(mesh, mat)
        if vessels:
            amat = C.tissue_material("artery", C.TISSUES["artery"])
            for v in vessels:
                R.add_vessel(v["name"], v["points"], v["radius"], amat)
        cam_obj, cam_dir = R.setup_camera(target, view, 235.0, lens_mm=100.0, dof=True)
        cam_obj.data.dof.aperture_fstop = 16.0
        C.setup_photo_world()
        C.setup_photo_lights(target, cam_obj, cam_dir)
        R.setup_render(width, height, samples, device=device)
        C.photo_color_management()

        stem = f"{name}_{view}"
        raw = out_dir / f"{stem}_raw.png"
        t1 = time.time()
        R.render_to(str(raw))
        log(f"render {stem}: {time.time() - t1:.1f}s")
        final = out_dir / f"{stem}.png"
        photo_finish(raw, final)
        raw.unlink(missing_ok=True)

        # labels: structure anchors projected into the image
        anchors = []
        for key in plate.labels:
            if key in NOMI[lang]:
                if key in ("skin", "superficial_fat"):
                    q = lm["commissura_dx"] + np.array([-25.0, -6.0, 25.0]) if key == "skin" else None
                else:
                    vv = [v for v in vessels if v["label"] == key and v["name"].endswith("_sx")] or \
                         [v for v in vessels if v["label"] == key]
                    q = vv[0]["points"][len(vv[0]["points"]) // 2] if vv else None
                label = NOMI[lang][key]
            else:
                tm = face.meshes.get(key)
                if tm is None:
                    continue
                c = np.asarray(tm.vertices).mean(axis=0)
                q = np.asarray(tm.vertices)[np.argmax(np.asarray(tm.vertices) @ cam_dir - 0.02 * np.linalg.norm(np.asarray(tm.vertices) - c, axis=1))]
                q = 0.6 * q + 0.4 * c
                label = STRUTTURE[key][0].replace(" sx", "").replace(" dx", "").replace(" sinistro", "")
            if q is not None:
                anchors.append((label, q))
        proj = R.project([q for _, q in anchors], width, height)
        items = [(n, xy) for (n, _), xy in zip(anchors, proj)
                 if xy and 0 <= xy[0] < width and 0 <= xy[1] < height and xy[2] > 0]
        title = plate.title_it if lang == "it" else plate.title_en
        refs_short = [_short(REFERENCES[r]) for r in plate.refs]
        annotate(final, out_dir / f"{stem}_etichette.png", title=title, items=items, footer_refs=refs_short,
                 lang=lang, background="dark")
        prov = {"plate": name, "view": view, "image": final.name,
                "anatomy_source": ATTRIBUTION,
                "structures": {fma: STRUTTURE[fma][0] for fma in face.meshes},
                "landmarks_mm": {k: [round(float(x), 2) for x in v] for k, v in lm.items()},
                "arteries": [{"name": v["name"], "evidence": v["evidence"], "radius_mm": round(v["radius"], 2)}
                             for v in vessels],
                "references": {r: REFERENCES[r] for r in plate.refs},
                "derived_layers": "dermis 1.8 mm; subcutaneous fat = space between dermis and "
                                  "muscles/bone (max 20 mm), computed volumetrically",
                "disclaimer": "Ricostruzione: anatomia da BodyParts3D (un individuo), arterie tracciate "
                              "secondo i dati di letteratura citati. Non è la fotografia di un preparato."}
        final.with_suffix(".json").write_text(json.dumps(prov, indent=2, ensure_ascii=False), encoding="utf-8")
        written.append(final)

        if control_maps:
            maps = K.render_control_maps(out_dir / stem, tissues_obj)
            visible = ["skin", "skin_cut", "superficial_fat", "fat_cut", "smas", "bone", "drape"]
            if vessels:
                visible.append("artery")
            prompt = K.build_prompt(visible, plate.title_en.lower() + ", whole face", view)
            prompt["prompt"] = prompt["prompt"].replace(", nose,", ", human face,")
            K.write_manifest(out_dir / stem, maps, prompt,
                             [[n, [float(v) for v in xy]] for n, xy in items], title, refs_short)
            log(f"mappe di controllo {stem}")
    return written
