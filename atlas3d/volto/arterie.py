"""Arteries of the face traced on the BodyParts3D head from published depth/position data.

BodyParts3D has no facial arteries, so each vessel is a centreline through anatomical
landmarks of this head (mandibular notch at the masseter, oral commissure, alar base,
medial canthus, supraorbital rim) placed at the depth below the skin reported in the
literature. Values marked 'measured' come from the cited abstracts (PubMed).
"""

from __future__ import annotations

import numpy as np
from scipy.interpolate import RegularGridInterpolator

REFERENCES = {
    "trzeciak2025": {"citation": "Trzeciak M, Ostrowski P, Gladysz T, et al. The depth of the facial artery, "
                                 "meta-analysis. Aesthetic Plast Surg. 2025;49(13):3793-3802.",
                     "pmid": "40164893", "doi": "10.1007/s00266-025-04833-9"},
    "pourani2025": {"citation": "Pourani MR, Ebrahimzade M, Goudarzi E, et al. Evaluation of facial artery course "
                                "variations, diameters, and depth using Doppler ultrasonography: a systematic review "
                                "and meta-analysis. J Cosmet Dermatol. 2025;24(9):e70431.",
                    "pmid": "40874402", "doi": "10.1111/jocd.70431"},
    "cotofana2020": {"citation": "Cotofana S, Alfertshofer M, Frank K, et al. Relationship between vertical glabellar "
                                 "lines and the supratrochlear and supraorbital arteries. Aesthet Surg J. "
                                 "2020;40(12):1341-1348.", "pmid": "32469392", "doi": "10.1093/asj/sjaa138"},
    "kliniec2024": {"citation": "Kliniec K, Domagala Z, Kempisty B, Szepietowski JC. Arterial vascularization of the "
                                "forehead in aesthetic dermatology procedures: a review. J Clin Med. 2024;13(14):4238.",
                    "pmid": "39064278", "doi": "10.3390/jcm13144238"},
    "scheuer2017": {"citation": "Scheuer JF 3rd, Sieber DA, Pezeshk RA, et al. Facial danger zones: techniques to "
                                "maximize safety during soft-tissue filler injections. Plast Reconstr Surg. "
                                "2017;139(5):1103-1108.", "pmid": "28445360", "doi": "10.1097/PRS.0000000000003309"},
    "choi2025": {"citation": "Choi NR, Gil YC. Facial artery asymmetry and branching patterns: correlation with main "
                             "trunk diameter. J Craniofac Surg. 2025.", "pmid": "40762675",
                 "doi": "10.1097/SCS.0000000000011730"},
    "tansatit2021": {"citation": "Tansatit T, Jitaree B, Uruwan S, Rungsawang C. Anatomical study of the dorsal nasal "
                                 "artery to prevent visual complications during dorsal nasal augmentation. Plast "
                                 "Reconstr Surg Glob Open. 2021;9(11):e3924.", "pmid": "34796083",
                     "doi": "10.1097/GOX.0000000000003924"},
    "bodyparts3d": {"citation": "BodyParts3D, (c) The Database Center for Life Science, CC BY-SA 2.1 JP. "
                                "Anatomical meshes of skin, skeleton, cartilage and muscles.", "pmid": "-"},
}

# depth below the skin (mm) and diameter (mm) along the facial artery, with evidence
FACIAL_ARTERY = [
    # (station, depth, diameter, evidence)
    ("margine_mandibolare", 6.3, 2.14, "measured: Pourani 2025 (depth level 1 6.27 mm, diameter 2.14 mm)"),
    ("commissura", 9.7, 1.9, "measured: Trzeciak 2025 depth at cheilion 9.72 mm"),
    ("commissura_ala", 10.3, 1.7, "measured: Trzeciak 2025 depth 10.34 mm"),
    ("ala", 9.2, 1.46, "measured: Trzeciak 2025 depth 9.21 mm; Pourani 2025 diameter 1.46 mm"),
    ("ala_canto", 4.7, 1.2, "measured: Trzeciak 2025 depth 4.68 mm"),
    ("canto_mediale", 2.4, 0.9, "measured: Trzeciak 2025 depth 2.38 mm"),
]


def _surface_point(interp_S, x, z, y_front, y_back):
    ys = np.linspace(y_front, y_back, 900)
    col = np.stack([np.full_like(ys, x), ys, np.full_like(ys, z)], axis=1)
    s = interp_S(col)
    idx = np.nonzero(s < 0)[0]
    if not len(idx):
        return None
    i = idx[0]
    return np.array([x, ys[i], z])


def _inward_normal(interp_S, q, h=0.6):
    g = np.array([(interp_S([q + e])[0] - interp_S([q - e])[0]) / (2 * h) for e in np.eye(3) * h])
    return -g / max(np.linalg.norm(g), 1e-6)


def _trace(interp_S, ctrl_xz, depths, diam, y_front, y_back, n=60, wiggle=0.0, rng=None):
    ctrl_xz = np.asarray(ctrl_xz, float)
    u = np.linspace(0, 1, len(ctrl_xz))
    uu = np.linspace(0, 1, n)
    xs = np.interp(uu, u, ctrl_xz[:, 0])
    zs = np.interp(uu, u, ctrl_xz[:, 1])
    dd = np.interp(uu, u, depths)
    rr = np.interp(uu, u, diam) / 2.0
    if wiggle and rng is not None:
        env = np.sin(np.pi * uu)
        ph = rng.uniform(0, 2 * np.pi, 2)
        xs = xs + wiggle * env * np.sin(2 * np.pi * 5.5 * uu + ph[0])
        zs = zs + 0.5 * wiggle * env * np.sin(2 * np.pi * 4.0 * uu + ph[1])
    pts, rad = [], []
    for x, z, d, r in zip(xs, zs, dd, rr):
        q = _surface_point(interp_S, x, z, y_front, y_back)
        if q is None:
            continue
        pts.append(q + _inward_normal(interp_S, q) * d)
        rad.append(r)
    return np.array(pts), float(np.mean(rad)) if rad else 0.5


def trace_arteries(face, grid, skin_sdf, seed=5) -> list[dict]:
    """Return vessel dicts {name, label, points (mm), radius (mm), evidence}."""
    lm = face.landmarks
    interp = RegularGridInterpolator(grid.axes, skin_sdf, bounds_error=False, fill_value=10.0)
    y_front = lm["pronasale"][1] + 3.0
    y_back = grid.origin[1] + 2.0
    rng = np.random.default_rng(seed)
    out = []
    for s, side in ((1, "sx"), (-1, "dx")):
        mand = lm[f"incisura_facciale_{side}"]
        comm = lm[f"commissura_{side}"]
        ala = lm[f"base_alare_{side}"]
        cant = lm[f"canto_mediale_{side}"]
        # facial artery: tortuous from the mandibular notch, lateral to the commissure, along the
        # nasolabial fold (medial course, the most frequent type in Pourani 2025) to the alar base,
        # then as angular artery up the nasal sidewall to the medial canthus
        ctrl = [(mand[0], mand[2]), (comm[0] + s * 10.0, comm[2] - 4.0),
                (0.5 * (comm[0] + ala[0]) + s * 5.0, 0.5 * (comm[2] + ala[2])),
                (ala[0] + s * 2.5, ala[2] + 1.0), (0.5 * (ala[0] + cant[0]) + s * 1.0, 0.5 * (ala[2] + cant[2])),
                (cant[0] + s * 1.5, cant[2] + 1.0)]
        depths = [st[1] for st in FACIAL_ARTERY]
        diams = [st[2] for st in FACIAL_ARTERY]
        pts, r = _trace(interp, ctrl, depths, diams, y_front, y_back, n=90, wiggle=2.2, rng=rng)
        out.append(dict(name=f"facciale_{side}", label="facial", points=pts, radius=r,
                        evidence="Trzeciak 2025; Pourani 2025"))
        # superior and inferior labial arteries from the facial artery to the midline
        for lab, dz, depth in (("labiale_superiore", 5.0, 5.0), ("labiale_inferiore", -7.0, 5.0)):
            c = [(comm[0] + s * 8.0, comm[2] + dz * 0.4), (comm[0] * 0.55, comm[2] + dz),
                 (s * 1.0, comm[2] + dz * 1.15)]
            p, rr = _trace(interp, c, [8.0, depth, depth], [1.3, 1.1, 0.9], y_front, y_back, n=36,
                           wiggle=0.8, rng=rng)
            out.append(dict(name=f"{lab}_{side}", label="labial", points=p, radius=rr,
                            evidence="course: Scheuer 2017; depth illustrative"))
        # lateral nasal artery: from the facial artery at the alar base towards the tip
        tip = lm["pronasale"]
        c = [(ala[0] + s * 2.0, ala[2] + 2.0), (ala[0] * 0.55, ala[2] + 6.0), (s * 4.0, tip[2] + 3.0)]
        p, rr = _trace(interp, c, [8.0, 3.2, 2.5], [1.0, 0.9, 0.7], y_front, y_back, n=30, wiggle=0.6, rng=rng)
        out.append(dict(name=f"nasale_laterale_{side}", label="lateral_nasal", points=p, radius=rr,
                        evidence="diameter 1.0 mm: Jiang 2020"))
        # dorsal nasal artery: from the medial canthus down the paramedian dorsum
        c = [(cant[0], cant[2] + 2.0), (s * 6.0, cant[2] - 12.0), (s * 4.0, tip[2] + 6.0)]
        p, rr = _trace(interp, c, [2.4, 2.8, 2.5], [0.9, 0.8, 0.6], y_front, y_back, n=30, wiggle=0.5, rng=rng)
        out.append(dict(name=f"dorsale_naso_{side}", label="dorsal_nasal", points=p, radius=rr,
                        evidence="bilateral pattern 53.3%: Tansatit 2021"))
        # supratrochlear and supraorbital arteries up the forehead
        for tag, label, dx_top, depth, diam in (("sopratrocleare", "supratrochlear", 18.0, 3.34, 1.0),
                                                ("sopraorbitario", "supraorbital", 34.0, 3.54, 1.1)):
            rim = lm[f"{tag}_{side}"]
            c = [(rim[0], rim[2] + 1.0), (rim[0] + s * 1.5, rim[2] + 22.0), (s * dx_top, rim[2] + 60.0)]
            p, rr = _trace(interp, c, [depth + 1.5, depth, depth - 0.5], [diam, diam * 0.85, diam * 0.6],
                           y_front, y_back, n=40, wiggle=0.9, rng=rng)
            out.append(dict(name=f"{tag}_{side}", label=label, points=p, radius=rr,
                            evidence="depth: Cotofana 2020; distance from midline: Kliniec 2024"))
    return [v for v in out if len(v["points"]) >= 3]
