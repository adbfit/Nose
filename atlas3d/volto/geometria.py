"""Whole-face geometry from BodyParts3D meshes.

Real anatomical meshes are used as they are for bone, cartilage, muscles, eyes and teeth.
Dermis and subcutaneous fat, which BodyParts3D does not segment, are derived volumetrically
as the space between the skin surface and the underlying structures.

Coordinates are converted to the atlas convention: millimetres, x = patient's left,
y = anterior, z = superior, origin at the soft-tissue nasion.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import trimesh
from scipy import ndimage

from ..anatomy import Grid, Window


@dataclass
class HalfWindow(Window):
    """Dissection window restricted to one side of the face (side=+1 patient's left)."""
    side: int = 1
from ..meshing import Mesh, taubin_smooth
from .catalogo import STRUTTURE
from .scarica import fetch

# frontal half of the head around the face (atlas coordinates, mm; refined after loading)
BOX = dict(x=(-92.0, 92.0), y=(-78.0, 40.0), z=(-118.0, 88.0))


def _to_atlas(v: np.ndarray, origin: np.ndarray) -> np.ndarray:
    out = np.empty_like(v)
    out[:, 0] = v[:, 0]
    out[:, 1] = -v[:, 1]
    out[:, 2] = v[:, 2]
    return out - origin


@dataclass
class Face:
    origin: np.ndarray                         # BodyParts3D coordinates of the atlas origin
    meshes: dict = field(default_factory=dict)  # fma -> trimesh (atlas coords, cropped)
    landmarks: dict = field(default_factory=dict)


def _load(fma: str) -> trimesh.Trimesh:
    return trimesh.load(fetch(fma), force="mesh", process=False)


def load_face(ids=None) -> Face:
    """Load the catalogue, move it to atlas coordinates and crop it to the face box."""
    ids = list(ids or STRUTTURE)
    raw = {fma: _load(fma) for fma in ids}

    # soft-tissue nasion: most posterior skin point on the midline between the eyes
    skin = raw["FMA7163"]
    eyes = raw["FMA12513"].bounds
    z_eye = 0.5 * (eyes[0][2] + eyes[1][2])
    v = skin.vertices
    band = v[(np.abs(v[:, 0]) < 4.0) & (v[:, 2] > z_eye - 6.0) & (v[:, 2] < z_eye + 30.0)
             & (v[:, 1] < eyes[0][1] + 10)]
    levels = np.arange(np.ceil(band[:, 2].min()), np.floor(band[:, 2].max()))
    prof = np.array([band[np.abs(band[:, 2] - z) < 1.5][:, 1].min() if np.any(np.abs(band[:, 2] - z) < 1.5)
                     else np.nan for z in levels])            # most anterior skin (min y) per level
    ok = ~np.isnan(prof)
    prof_s = ndimage.median_filter(np.interp(levels, levels[ok], prof[ok]), size=5)
    k = int(np.argmax(prof_s))                                 # deepest point of the soft-tissue profile
    origin = np.array([0.0, -prof_s[k], levels[k]])

    face = Face(origin=origin)
    lo = np.array([BOX["x"][0], BOX["y"][0], BOX["z"][0]])
    hi = np.array([BOX["x"][1], BOX["y"][1], BOX["z"][1]])
    for fma, m in raw.items():
        verts = _to_atlas(np.asarray(m.vertices, float), origin)
        faces = np.asarray(m.faces)[:, ::-1]            # the y flip mirrors: restore winding
        mesh = trimesh.Trimesh(verts, faces, process=False)
        if fma == "FMA7163":
            keep = np.all((mesh.triangles_center > lo - 20) & (mesh.triangles_center < hi + 20), axis=1)
            mesh = mesh.submesh([np.nonzero(keep)[0]], append=True)
        else:
            c = mesh.bounds.mean(axis=0)
            if np.any(c < lo) or np.any(c > hi):
                continue
        face.meshes[fma] = mesh
    face.landmarks = find_landmarks(face)
    return face


def find_landmarks(face: Face) -> dict:
    m = face.meshes
    skin = m["FMA7163"].vertices
    mid = skin[np.abs(skin[:, 0]) < 1.5]
    lm = {"nasion": np.zeros(3)}
    lm["pronasale"] = mid[np.argmax(mid[:, 1])]
    below = mid[(mid[:, 2] < lm["pronasale"][2] - 5) & (mid[:, 2] > lm["pronasale"][2] - 30)]
    # subnasale: deepest point of the profile between the tip and the upper lip
    zs = np.round(below[:, 2])
    prof = {z: below[zs == z][:, 1].max() for z in np.unique(zs)}
    z_sn = min(sorted(prof)[len(prof) // 3:], key=lambda z: prof[z]) if prof else lm["pronasale"][2] - 15
    lm["subnasale"] = np.array([0.0, prof.get(z_sn, 0.0), z_sn])
    eye = m["FMA12513"].vertices
    for s, name in ((1, "sx"), (-1, "dx")):
        e = eye[eye[:, 0] * s > 0]
        lm[f"canto_mediale_{name}"] = e[np.argmin(np.abs(e[:, 0]))] + np.array([0, 2.0, 0])
        lm[f"centro_occhio_{name}"] = e.mean(axis=0)
    oo = m["FMA46841"].vertices
    for s, name in ((1, "sx"), (-1, "dx")):
        side = oo[oo[:, 0] * s > 0]
        lm[f"commissura_{name}"] = side[np.argmax(np.abs(side[:, 0]))]
    mand = m["FMA52748"].vertices
    for s, name, mas in ((1, "sx", "FMA49002"), (-1, "dx", "FMA49001")):
        if mas in m:
            mv = m[mas].vertices
            ant = mv[np.argmax(mv[:, 1])]            # anterior border of the masseter
        else:
            ant = np.array([s * 45.0, -40.0, -95.0])
        side = mand[(mand[:, 0] * s > 0) & (np.abs(mand[:, 1] - ant[1]) < 4)]
        lm[f"incisura_facciale_{name}"] = side[np.argmin(side[:, 2])] if len(side) else ant
    fr = m["FMA52734"].vertices
    for s, name in ((1, "sx"), (-1, "dx")):
        # orbital rim of the frontal bone at 17 mm (supratrochlear) and 27 mm (supraorbital)
        for dx, tag in ((17.0, "sopratrocleare"), (27.0, "sopraorbitario")):
            sel = fr[(np.abs(fr[:, 0] - s * dx) < 2.0) & (fr[:, 1] > -25)]
            rim = sel[np.argmin(sel[:, 2])] if len(sel) else np.array([s * dx, 0, 5.0])
            lm[f"{tag}_{name}"] = rim
    ala = skin[(np.abs(skin[:, 2] - (lm["subnasale"][2] + 5)) < 2) & (np.abs(skin[:, 0]) < 24)]
    for s, name in ((1, "sx"), (-1, "dx")):
        side = ala[ala[:, 0] * s > 0]
        side = side[side[:, 1] > lm["subnasale"][1] - 12]
        lm[f"base_alare_{name}"] = side[np.argmax(np.abs(side[:, 0]))] if len(side) else np.array([s * 17, 0, -45])
    return lm


# ------------------------------------------------------------------ volumes
def _voxelize(mesh: trimesh.Trimesh, grid: Grid) -> np.ndarray:
    """Solid occupancy of a closed mesh on the grid (surface sampling + hole filling)."""
    h = grid.spacing
    lo = mesh.bounds[0] - 2 * h
    hi = mesh.bounds[1] + 2 * h
    i0 = np.clip(np.floor((lo - grid.origin) / h).astype(int), 0, np.array(grid.shape) - 1)
    i1 = np.clip(np.ceil((hi - grid.origin) / h).astype(int) + 1, 1, np.array(grid.shape))
    sub = np.zeros(tuple(i1 - i0), bool)
    tris = mesh.triangles
    # sample each triangle densely enough to leave no gaps at the grid spacing
    edge = np.max(np.linalg.norm(tris - np.roll(tris, 1, axis=1), axis=2), axis=1)
    n = np.clip(np.ceil(edge / (0.5 * h)).astype(int), 1, 64)
    for k in np.unique(n):
        t = tris[n == k]
        u, v = np.meshgrid(np.linspace(0, 1, k + 1), np.linspace(0, 1, k + 1))
        m = (u + v) <= 1.0
        u, v = u[m], v[m]
        pts = (t[:, None, 0] * (1 - u - v)[None, :, None] + t[:, None, 1] * u[None, :, None]
               + t[:, None, 2] * v[None, :, None]).reshape(-1, 3)
        idx = np.floor((pts - grid.origin) / h + 0.5).astype(int) - i0
        ok = np.all((idx >= 0) & (idx < sub.shape), axis=1)
        idx = idx[ok]
        sub[idx[:, 0], idx[:, 1], idx[:, 2]] = True
    sub = ndimage.binary_fill_holes(sub)
    full = np.zeros(grid.shape, bool)
    full[i0[0]:i1[0], i0[1]:i1[1], i0[2]:i1[2]] = sub
    return full


def _inside_winding(mesh: trimesh.Trimesh, grid: Grid) -> np.ndarray:
    """Inside test by generalised winding number: robust to the openings of the cropped skin
    (neck, eyelid fissures)."""
    import igl
    V = np.asarray(mesh.vertices, np.float64)
    F = np.ascontiguousarray(np.asarray(mesh.faces, np.int64))
    xs, ys, zs = grid.axes
    out = np.zeros(grid.shape, bool)
    step = max(1, int(2_000_000 // (len(ys) * len(zs))))
    for i in range(0, len(xs), step):
        X, Y, Z = np.meshgrid(xs[i:i + step], ys, zs, indexing="ij")
        Q = np.stack([X.ravel(), Y.ravel(), Z.ravel()], axis=1)
        out[i:i + step] = (igl.fast_winding_number(V, F, Q) > 0.5).reshape(X.shape)
    return out


def _exact_band(sdf: np.ndarray, mesh: trimesh.Trimesh, grid: Grid, band: float) -> np.ndarray:
    """Replace the voxel-quantised distance near the surface with the exact signed distance to the
    mesh, so the skin comes out smooth instead of terraced."""
    import igl
    idx = np.nonzero(np.abs(sdf) < band)
    Q = np.stack([grid.origin[i] + grid.spacing * idx[i] for i in range(3)], axis=1).astype(np.float64)
    V = np.asarray(mesh.vertices, np.float64)
    F = np.ascontiguousarray(np.asarray(mesh.faces, np.int64))
    out = sdf.copy()
    step = 1_000_000
    for i in range(0, len(Q), step):
        d = igl.signed_distance(Q[i:i + step], V, F, igl.SIGNED_DISTANCE_TYPE_FAST_WINDING_NUMBER)[0]
        sel = tuple(a[i:i + step] for a in idx)
        out[sel] = d.astype(np.float32)
    return out


def _sdf_from_mask(mask: np.ndarray, h: float, blur: float = 0.8) -> np.ndarray:
    """Smooth signed distance (negative inside) from a boolean mask."""
    soft = ndimage.gaussian_filter(mask.astype(np.float32), blur)
    inside = soft > 0.5
    d_in = ndimage.distance_transform_edt(inside, sampling=h)
    d_out = ndimage.distance_transform_edt(~inside, sampling=h)
    return np.where(inside, -(d_in - 0.5 * h), d_out - 0.5 * h).astype(np.float32)


@dataclass
class FaceFields:
    grid: Grid
    volumes: dict
    uncut: dict
    skin_depth: np.ndarray       # distance below the skin surface (mm, > 0 inside)
    deep_dist: np.ndarray        # distance to the nearest deep structure (mm)
    skin_sdf: np.ndarray         # signed distance to the skin surface (negative inside)


def build_fields(face: Face, spacing: float = 0.6, dermis_mm: float = 1.8, max_fat_mm: float = 20.0,
                 windows: dict | None = None, drape: bool = True) -> FaceFields:
    lo = np.array([BOX["x"][0], BOX["y"][0], BOX["z"][0]])
    hi = np.array([BOX["x"][1], face.landmarks["pronasale"][1] + 4.0, BOX["z"][1]])
    shape = tuple(int(np.ceil((hi[i] - lo[i]) / spacing)) + 1 for i in range(3))
    grid = Grid(origin=lo, spacing=spacing, shape=shape)

    skin_in = _inside_winding(face.meshes["FMA7163"], grid)
    deep = np.zeros(grid.shape, bool)
    for fma, mesh in face.meshes.items():
        if STRUTTURE[fma][1] in ("bone", "muscle", "cartilage", "eye", "tooth"):
            deep |= _voxelize(mesh, grid)

    h = spacing
    depth = ndimage.distance_transform_edt(skin_in, sampling=h).astype(np.float32)
    deep_dist = ndimage.distance_transform_edt(~deep, sampling=h).astype(np.float32)
    dermis = skin_in & (depth <= dermis_mm)
    fat = skin_in & (depth > dermis_mm) & ~ndimage.binary_dilation(deep, iterations=1) & (depth < max_fat_mm)

    out_d = ndimage.distance_transform_edt(~skin_in, sampling=h).astype(np.float32)
    skin_sdf = np.where(skin_in, -depth, out_d).astype(np.float32)
    del out_d
    skin_sdf = _exact_band(skin_sdf, face.meshes["FMA7163"], grid, band=max(dermis_mm + 2.0, 4 * h))
    deep_sdf = _sdf_from_mask(deep, h, 1.0)
    # continuous layers: dermis = first `dermis_mm` below the skin surface; subcutaneous fat = the
    # rest of the soft tissue down to the muscles / bone (at most `max_fat_mm` deep)
    dermis_sdf = np.maximum(skin_sdf, -(skin_sdf + dermis_mm))
    fat_sdf = np.maximum.reduce([skin_sdf + dermis_mm, -(deep_sdf - 0.3), -(skin_sdf + max_fat_mm)])
    vols = {"skin": dermis_sdf.astype(np.float32), "superficial_fat": fat_sdf.astype(np.float32)}
    if drape:
        vols["drape"] = _drape(face, grid, depth, skin_in)
    X, Y, Z = (grid.axes[0][:, None, None], grid.axes[1][None, :, None], grid.axes[2][None, None, :])
    uncut = {k: v.copy() for k, v in vols.items()}
    for name, win in (windows or {}).items():
        if name in vols:
            a, b = win.radii
            cx, cz = win.center
            e = (np.sqrt(((X - cx) / a) ** 2 + ((Z - cz) / b) ** 2) - 1.0) * min(a, b)
            e = e + win.ragged * _noise2d(grid, 3.0, win.seed) + 0.35 * win.ragged * _noise2d(grid, 0.8, win.seed + 9)
            side = getattr(win, "side", 0)
            if side:
                # keep the dissection on one half of the face, with an irregular midline margin
                e = np.maximum(e, -side * X + 1.5 + win.ragged * _noise2d(grid, 2.5, win.seed + 5))
            vols[name] = np.maximum(vols[name], -e)
    box = np.maximum.reduce([np.broadcast_to(np.abs(X) - (hi[0] - 2), grid.shape),
                             np.broadcast_to(Z - (hi[2] - 2), grid.shape),
                             np.broadcast_to((lo[2] + 2) - Z, grid.shape),
                             np.broadcast_to((lo[1] + 2) - Y, grid.shape)])
    for k in vols:
        vols[k] = np.maximum(vols[k], box)
    return FaceFields(grid=grid, volumes=vols, uncut=uncut, skin_depth=depth, deep_dist=deep_dist,
                      skin_sdf=skin_sdf)


def _noise2d(grid: Grid, scale_mm: float, seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    nx, _, nz = grid.shape
    f = ndimage.gaussian_filter(rng.normal(size=(nx, nz)), scale_mm / grid.spacing, mode="wrap")
    f /= f.std() + 1e-9
    return f[:, None, :].astype(np.float32)


def _drape(face: Face, grid: Grid, depth: np.ndarray, skin_in: np.ndarray) -> np.ndarray:
    """Fenestrated drape over hair, ears and neck; the opening frames the face."""
    h = grid.spacing
    out_d = ndimage.distance_transform_edt(~skin_in, sampling=h).astype(np.float32)
    S = np.where(skin_in, -depth, out_d)
    X = grid.axes[0][:, None, None]
    Z = grid.axes[2][None, None, :]
    lm = face.landmarks
    cz = 0.5 * (lm["nasion"][2] + lm["commissura_sx"][2]) + 4.0
    a, b = 70.0, 88.0
    e = (np.sqrt((X / a) ** 2 + ((Z - cz) / b) ** 2) - 1.0) * a + 2.0 * _noise2d(grid, 6.0, 21)
    folds = 1.6 * np.abs(_noise2d(grid, 9.0, 22)) + 0.6 * _noise2d(grid, 3.0, 23)
    lift = 1.5 + folds + 0.08 * np.clip(e, 0, None)
    shell = np.maximum(lift - S, S - (lift + 1.0))
    return np.maximum(shell, -e).astype(np.float32)


def mesh_from_sdf(name: str, vol: np.ndarray, grid: Grid, smooth: int = 3) -> Mesh:
    from skimage import measure
    if vol.min() >= 0 or vol.max() <= 0:
        return Mesh(name, np.zeros((0, 3)), np.zeros((0, 3), int))
    pad = np.pad(vol, 1, constant_values=float(np.abs(vol).max()))
    h = grid.spacing
    v, f, _, _ = measure.marching_cubes(pad, 0.0, spacing=(h, h, h), allow_degenerate=False)
    v = v - h + grid.origin
    if smooth:
        v = taubin_smooth(v, f, smooth)
    return Mesh(name, v, f.astype(np.int64))


def mesh_from_trimesh(name: str, m: trimesh.Trimesh) -> Mesh:
    # BodyParts3D winding is outward; our add_mesh flips normals (marching-cubes convention)
    return Mesh(name, np.asarray(m.vertices, float), np.asarray(m.faces)[:, ::-1].astype(np.int64))
