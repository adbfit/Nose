"""Loading, validating and overriding the literature-backed anatomical parameters."""

from __future__ import annotations

import copy
import math
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import yaml

DEFAULT_PARAMS = Path(__file__).parent / "params" / "naso_adulto.yaml"

# Presets applied on top of the YAML defaults. They only encode the direction of
# the sex differences reported by Ballin 2017 (men: sharper nasofrontal angle,
# higher tip projection) and Farkas 2005 (larger male dimensions); magnitudes are
# illustrative.
PRESETS = {
    "female": {},
    "male": {
        "morphology.nasal_length": 51.0,
        "morphology.nasal_height": 54.0,
        "morphology.alar_width": 35.5,
        "morphology.dorsal_width": 12.5,
        "morphology.nasofrontal_angle": 124.0,
        "morphology.nasolabial_angle": 95.0,
        "morphology.goode_ratio": 0.60,
        "soft_tissue.thickness_nasion": 6.8,
        "soft_tissue.thickness_supratip": 4.2,
    },
}


class ParameterError(ValueError):
    pass


@dataclass
class Params:
    """Parameter tree as loaded from YAML plus convenience accessors."""

    tree: dict
    source: Path
    overrides: dict = field(default_factory=dict)

    def get(self, dotted: str):
        section, key = dotted.split(".", 1)
        return self.tree[section][key]["value"]

    def entry(self, dotted: str) -> dict:
        section, key = dotted.split(".", 1)
        return self.tree[section][key]

    def __getitem__(self, dotted: str):
        return self.get(dotted)

    def items(self):
        for section, entries in self.tree.items():
            if section == "references":
                continue
            for key, entry in entries.items():
                yield f"{section}.{key}", entry

    @property
    def references(self) -> dict:
        return self.tree.get("references", {})


def _coerce(raw: str, current):
    if isinstance(current, bool):
        return raw.lower() in ("1", "true", "yes", "si", "sì", "on")
    if isinstance(current, (int, float)):
        return float(raw)
    return raw


def _resolve_key(tree: dict, key: str) -> str:
    if "." in key:
        section, name = key.split(".", 1)
        if section in tree and name in tree[section]:
            return key
        raise ParameterError(f"Parametro sconosciuto: {key}")
    matches = [
        f"{s}.{key}" for s, entries in tree.items() if s != "references" and key in entries
    ]
    if len(matches) != 1:
        raise ParameterError(
            f"Parametro {'ambiguo' if matches else 'sconosciuto'}: {key} {matches or ''}".strip()
        )
    return matches[0]


def load_params(path: str | Path | None = None, preset: str = "female",
                overrides: dict | None = None) -> Params:
    source = Path(path) if path else DEFAULT_PARAMS
    with open(source, encoding="utf-8") as fh:
        tree = yaml.safe_load(fh)
    tree = copy.deepcopy(tree)

    if preset not in PRESETS:
        raise ParameterError(f"Preset sconosciuto: {preset} (disponibili: {', '.join(PRESETS)})")
    applied = dict(PRESETS[preset])
    applied.update(overrides or {})

    resolved = {}
    for key, raw in applied.items():
        dotted = _resolve_key(tree, key)
        entry = tree[dotted.split(".")[0]][dotted.split(".", 1)[1]]
        value = _coerce(raw, entry["value"]) if isinstance(raw, str) else raw
        lo_hi = entry.get("range")
        if lo_hi and isinstance(value, (int, float)) and not isinstance(value, bool):
            lo, hi = lo_hi
            if not lo <= value <= hi:
                raise ParameterError(
                    f"{dotted}={value} fuori dall'intervallo plausibile [{lo}, {hi}] {entry.get('unit', '')}"
                )
        entry["value"] = value
        resolved[dotted] = value

    params = Params(tree=tree, source=source, overrides=resolved)
    _check_references(params)
    return params


def _check_references(params: Params):
    known = set(params.references)
    for dotted, entry in params.items():
        for ref in entry.get("refs", []) or []:
            if ref not in known:
                raise ParameterError(f"{dotted} cita un riferimento inesistente: {ref}")


def parse_overrides(pairs: list[str]) -> dict:
    out = {}
    for pair in pairs or []:
        if "=" not in pair:
            raise ParameterError(f"Override non valido (atteso chiave=valore): {pair}")
        k, v = pair.split("=", 1)
        out[k.strip()] = v.strip()
    return out


# ---------------------------------------------------------------------------
# Landmarks
# ---------------------------------------------------------------------------
# Coordinate system (millimetres): x = patient's left (+) / right (-),
# y = anterior (projection out of the face), z = superior. Nasion at z = 0.


@dataclass
class Landmarks:
    nasion: np.ndarray
    rhinion: np.ndarray
    supratip: np.ndarray
    pronasale: np.ndarray
    subnasale: np.ndarray
    glabella: np.ndarray
    alar_crease: np.ndarray   # left alar-facial groove (x > 0)
    dorsum_dir: np.ndarray    # unit vector nasion -> pronasale
    columella_dir: np.ndarray  # unit vector subnasale -> pronasale region
    lip_dir: np.ndarray       # unit vector subnasale -> labrale superius
    face_y: float             # depth of the cheek plane at the alar groove

    def dorsum_point(self, t: float) -> np.ndarray:
        return self.nasion + (self.pronasale - self.nasion) * t


def _unit(v):
    v = np.asarray(v, dtype=float)
    return v / np.linalg.norm(v)


def compute_landmarks(p: Params) -> Landmarks:
    L = p["morphology.nasal_length"]
    H = p["morphology.nasal_height"]
    goode = p["morphology.goode_ratio"]
    nfa = math.radians(p["morphology.nasofrontal_angle"])
    nla = math.radians(p["morphology.nasolabial_angle"])

    face_y = 0.0
    nasion_y = 9.0  # nasion sits in front of the medial canthal plane

    # Goode: tip projection measured from the alar-facial groove.
    projection = goode * L
    tip_y = face_y + projection
    dy = tip_y - nasion_y
    dz = -math.sqrt(max(L * L - dy * dy, 1.0))
    nasion = np.array([0.0, nasion_y, 0.0])
    pronasale = np.array([0.0, tip_y, dz])
    dorsum_dir = _unit(pronasale - nasion)

    # Glabella: the nasofrontal angle is measured between nasion->glabella and
    # nasion->pronasale; rotate the dorsum direction by that angle in the
    # sagittal plane, towards the forehead.
    a = math.atan2(dorsum_dir[2], dorsum_dir[1]) + nfa
    glabella = nasion + 14.0 * np.array([0.0, math.cos(a), math.sin(a)])

    # Subnasale and columella: the nasolabial angle opens between the upper lip
    # (tilted forward by ~10°) and the columella tangent.
    lip_tilt = math.radians(10.0)
    lip_dir = np.array([0.0, math.sin(lip_tilt), -math.cos(lip_tilt)])
    phi = lip_tilt + nla
    columella_dir = np.array([0.0, math.sin(phi), -math.cos(phi)])
    sn_z = -H
    # The columella meets the lobule a few millimetres below pronasale.
    col_top_z = pronasale[2] - 5.0
    run = (col_top_z - sn_z) / max(columella_dir[2], 0.05)
    sn_y = pronasale[1] - 3.0 - run * columella_dir[1]
    subnasale = np.array([0.0, max(sn_y, face_y + 6.0), sn_z])

    rhinion = nasion + (pronasale - nasion) * p["morphology.rhinion_position"]
    rhinion = rhinion + np.array([0.0, p["morphology.dorsal_hump"] * 0.6, 0.0])
    supratip = nasion + (pronasale - nasion) * 0.84
    alar_crease = np.array([p["morphology.alar_width"] / 2 - 1.5, face_y + 3.0, sn_z + 5.5])

    return Landmarks(nasion=nasion, rhinion=rhinion, supratip=supratip, pronasale=pronasale,
                     subnasale=subnasale, glabella=glabella, alar_crease=alar_crease,
                     dorsum_dir=dorsum_dir, columella_dir=columella_dir, lip_dir=lip_dir,
                     face_y=face_y)


def measured_profile(lm: Landmarks) -> dict:
    """Recompute the profile metrics from the landmarks (used as a self-check)."""
    def angle(a, b):
        return math.degrees(math.acos(np.clip(np.dot(_unit(a), _unit(b)), -1, 1)))
    L = np.linalg.norm(lm.pronasale - lm.nasion)
    return {
        "nasal_length": L,
        "nasofrontal_angle": angle(lm.glabella - lm.nasion, lm.pronasale - lm.nasion),
        "nasolabial_angle": angle(lm.columella_dir, lm.lip_dir),
        "goode_ratio": (lm.pronasale[1] - lm.face_y) / L,
    }
