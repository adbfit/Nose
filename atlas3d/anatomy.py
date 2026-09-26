"""Procedural anatomy of the external nose built from signed distance fields.

The skin surface is sculpted from the literature-backed profile landmarks
(nasofrontal / nasolabial angle, Goode ratio, nasal length and height, alar
width). Deeper layers are offsets of the skin surface driven by the soft-tissue
thickness profile, following the layer sequence of Letourneau & Daniel (1988).
The osteocartilaginous framework is the shell below the soft-tissue envelope,
partitioned into bone, upper lateral cartilages, lower lateral cartilages and
septum. Arteries are traced on the plane reported by Toriumi (1996).
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from scipy import ndimage
from scipy.interpolate import PchipInterpolator, RegularGridInterpolator

from . import sdf
from .params import Landmarks, Params, compute_landmarks

LAYER_ORDER = ["skin", "superficial_fat", "smas", "deep_fat", "periosteum"]

# Structures that can be rendered, in anatomical order from superficial to deep.
STRUCTURES = [
    "skin", "superficial_fat", "smas", "deep_fat",
    "bone", "upper_lateral_cartilage", "lower_lateral_cartilage", "septum",
    "filler",
]


@dataclass
class Grid:
    origin: np.ndarray
    spacing: float
    shape: tuple

    @property
    def axes(self):
        return [self.origin[i] + self.spacing * np.arange(self.shape[i]) for i in range(3)]

    def points(self, k0: int, k1: int) -> np.ndarray:
        """Grid points for x-slabs k0..k1 as an (N, 3) float32 array."""
        xs, ys, zs = self.axes
        X, Y, Z = np.meshgrid(xs[k0:k1], ys, zs, indexing="ij")
        return np.stack([X.ravel(), Y.ravel(), Z.ravel()], axis=1).astype(np.float32)


@dataclass
class Cut:
    """Keep only the part of a structure with x < limit (patient's right side)."""
    limit: float


@dataclass
class Window:
    """Dissection window: removes a structure inside an irregular ellipse drawn on the
    frontal (x, z) plane, like a layer excised through a skin incision."""
    center: tuple          # (x, z) in mm
    radii: tuple           # (a, b) in mm
    ragged: float = 0.8    # amplitude of the irregular margin (mm)
    seed: int = 1


@dataclass
class Fields:
    grid: Grid
    volumes: dict = field(default_factory=dict)   # structure -> 3D SDF array
    uncut: dict = field(default_factory=dict)     # structure -> SDF before cuts/windows
    skin_n: np.ndarray | None = None
    thickness: np.ndarray | None = None
    nose_weight: np.ndarray | None = None
    t_param: np.ndarray | None = None


def _vmax(arrays):
    out = arrays[0]
    for a in arrays[1:]:
        out = np.maximum(out, a)
    return out


def _unit(v):
    v = np.asarray(v, dtype=float)
    return v / np.linalg.norm(v)


class NoseModel:
    def __init__(self, params: Params):
        self.p = params
        self.lm: Landmarks = compute_landmarks(params)
        self._setup()

    # ------------------------------------------------------------------ setup
    def _setup(self):
        p, lm = self.p, self.lm
        self.L = float(np.linalg.norm(lm.pronasale - lm.nasion))
        d = lm.dorsum_dir
        self.n_ant = _unit([0.0, -d[2], d[1]])          # anterior normal of the dorsum
        c = lm.columella_dir
        self.n_col = _unit([0.0, -c[2], c[1]])           # points from the columella surface inwards

        self.half_x = 42.0
        self.z_max = lm.glabella[2] + 14.0
        self.z_min = lm.subnasale[2] - 16.0
        self.y_back = -16.0

        sn, T = lm.subnasale, lm.pronasale
        gy, gz, ny = lm.glabella[1], lm.glabella[2], lm.nasion[1]
        # Mid-sagittal profile of the face *behind* the nose (hidden where the nose sits).
        zs = [self.z_max + 2, gz + 8, gz, gz * 0.35, 0.0, -12.0, -26.0,
              sn[2] + 8, sn[2], sn[2] - 7, self.z_min - 2]
        ys = [gy - 2.5, gy - 0.6, gy, ny + 1.6, ny, ny - 1.5, 5.5,
              4.5, 4.0, 4.5, 4.5]
        self._mid = PchipInterpolator(np.array(zs[::-1]), np.array(ys[::-1]), extrapolate=True)
        self._lat = PchipInterpolator(
            np.array([self.z_min - 2, sn[2] - 4, sn[2] + 6, -24.0, 0.0, gz, self.z_max + 2]),
            np.array([0.016, 0.016, 0.016, 0.016, 0.017, 0.011, 0.009]), extrapolate=True)
        # Upper-lip mound: projects forward to subnasale in the midline only.
        self._lip = PchipInterpolator(
            np.array([self.z_min - 2, sn[2] - 8, sn[2] - 1.0, sn[2] + 1.5, sn[2] + 4.0, sn[2] + 7.0]),
            np.array([sn[1] - 2.5, sn[1] - 3.0, sn[1] - 4.5, sn[1] - 10.0, 3.0, 0.0]), extrapolate=False)

        dw = p["morphology.dorsal_width"] / 2.0
        hump = p["morphology.dorsal_hump"]
        brk = p["morphology.supratip_break"]
        self.r_nasion, self.r_rhinion, self.r_supratip = dw * 1.2, dw * 1.05 + hump * 0.15, dw * 1.1
        self.a_n = lm.nasion - self.n_ant * self.r_nasion - d * 5.0
        self.a_r = lm.rhinion - self.n_ant * self.r_rhinion
        self.a_s = lm.supratip - self.n_ant * (self.r_supratip + brk)

        tw = p["morphology.tip_width"] / 2.0
        self.dome_r = np.array([5.0, 5.4, 6.0])
        self.domes = [np.array([s * tw * 0.8, T[1] - self.dome_r[1] + 0.25, T[2] - 0.8]) for s in (1, -1)]
        self.infratip = (np.array([0.0, T[1] - 6.2, T[2] - 5.8]), np.array([5.2, 5.4, 5.2]))

        self.col_r = 3.2
        self.col_a = sn + self.n_col * self.col_r + c * 1.0
        run = max((T[2] - 6.0 - sn[2]) / max(c[2], 0.1), 6.0)
        self.col_b = sn + self.n_col * self.col_r + c * min(run, 20.0)
        self.footplate = (sn + self.n_col * 3.0 - np.array([0, 1.5, 0]), np.array([5.0, 4.0, 3.4]))

        aw = p["morphology.alar_width"] / 2.0
        self.alar_half = aw
        self.alae = [(np.array([s * (aw - 6.0), lm.face_y + 8.0, sn[2] + 5.2]),
                      np.array([5.3, 9.5, 5.6]), sdf.rotation(yaw=s * 32.0, pitch=-8.0))
                     for s in (1, -1)]
        # Alar rim / soft triangle: bridges each ala to the tip lobule.
        self.rims = [(np.array([s * 6.8, sn[1] + 3.5, sn[2] + 4.2]),
                      np.array([3.8, 7.5, 3.4]), sdf.rotation(yaw=s * 34.0, pitch=-4.0))
                     for s in (1, -1)]
        z_mid = 0.5 * (lm.rhinion[2] + sn[2]) + 1.0
        self.pyramid = (np.array([0.0, lm.face_y + 2.0, z_mid]),
                        np.array([max(aw - 8.0, 8.0), 13.0, 0.5 * (lm.rhinion[2] - sn[2]) + 8.0]))
        self.nostrils = [(np.array([s * 5.4, sn[1] + 2.2, sn[2] + 1.6]),
                          np.array([2.9, 6.0, 3.4]), sdf.rotation(yaw=s * 22.0, pitch=4.0))
                         for s in (1, -1)]

        # Thickness profile along the dorsum (t = 0 nasion, 1 pronasale).
        st = "soft_tissue."
        t_r = p["morphology.rhinion_position"]
        self._thick = PchipInterpolator(
            [-0.4, 0.0, t_r, 0.84, 1.0, 1.4],
            [p[st + "thickness_face"], p[st + "thickness_nasion"], p[st + "thickness_rhinion"],
             p[st + "thickness_supratip"], p[st + "thickness_tip"], p[st + "thickness_tip"]],
            extrapolate=True)
        fr = p[st + "layer_fractions"]
        total = sum(fr[k] for k in LAYER_ORDER)
        acc, self.depth_frac = 0.0, {}
        for k in LAYER_ORDER:
            self.depth_frac[k] = (acc / total, (acc + fr[k]) / total)
            acc += fr[k]

        self._setup_filler()

    def _setup_filler(self):
        p, lm = self.p, self.lm
        self.filler = None
        if not p["filler.enabled"]:
            return
        volume_mm3 = p["filler.volume"] * 1000.0
        ratio = np.array([1.0, 0.6, 2.4])  # lateral : anteroposterior : along the dorsum
        # Only the half above the framework is filled: V = 2/3 * pi * a * b * c.
        a = (volume_mm3 / ((2.0 / 3.0) * np.pi * np.prod(ratio))) ** (1.0 / 3.0)
        radii = a * ratio
        t = p["filler.site"]
        depth = float(self._thick(t)) * self.depth_frac["periosteum"][0]
        center = lm.dorsum_point(t) - self.n_ant * depth
        rot = np.stack([[1.0, 0.0, 0.0], self.n_ant, lm.dorsum_dir], axis=1)
        self.filler = (center, radii, rot)

    # --------------------------------------------------------------- surfaces
    def _face_height(self, x, z):
        f = self._mid(z) - self._lat(z) * x * x
        canth = 5.0 * np.exp(-(((np.abs(x) - 18.0) / 7.5) ** 2 + ((z + 5.0) / 9.0) ** 2))
        cheek = 3.5 * np.exp(-(((np.abs(x) - 27.0) / 8.0) ** 2 + ((z + 34.0) / 10.0) ** 2))
        philtrum = 0.8 * np.exp(-((x / 3.0) ** 2)) * sdf.smoothstep(
            self.lm.subnasale[2] - 2, self.lm.subnasale[2] - 10, z)
        lip = np.nan_to_num(self._lip(z), nan=0.0)
        sn_z = self.lm.subnasale[2]
        lip = np.where(z > sn_z + 7, 0.0, np.maximum(lip, 0.0))
        sigma = 9.0 + 10.0 * sdf.smoothstep(sn_z + 2.0, sn_z - 10.0, z)
        lip = lip * np.exp(-((x / sigma) ** 2))
        return f - canth + cheek + philtrum + lip

    def face_sdf(self, P):
        x, y, z = P[:, 0], P[:, 1], P[:, 2]
        h = 0.05
        f = self._face_height(x, z)
        fx = (self._face_height(x + h, z) - self._face_height(x - h, z)) / (2 * h)
        fz = (self._face_height(x, z + h) - self._face_height(x, z - h)) / (2 * h)
        return (y - f) / np.sqrt(1.0 + fx * fx + fz * fz)

    def nose_parts(self, P):
        dorsum = sdf.smin(sdf.round_cone(P, self.a_n, self.a_r, self.r_nasion, self.r_rhinion),
                          sdf.round_cone(P, self.a_r, self.a_s, self.r_rhinion, self.r_supratip), 2.0)
        body = sdf.smin(dorsum, sdf.ellipsoid(P, *self.pyramid), 6.0)
        tip = sdf.smin(sdf.ellipsoid(P, self.domes[0], self.dome_r),
                       sdf.ellipsoid(P, self.domes[1], self.dome_r), 4.0)
        tip = sdf.smin(tip, sdf.ellipsoid(P, *self.infratip), 3.0)
        nose = sdf.smin(body, tip, 4.5)
        nose = sdf.smin(nose, sdf.capsule(P, self.col_a, self.col_b, self.col_r), 2.5)
        nose = sdf.smin(nose, sdf.ellipsoid(P, *self.footplate), 2.0)
        alae = np.minimum(sdf.ellipsoid(P, *self.alae[0]), sdf.ellipsoid(P, *self.alae[1]))
        rims = np.minimum(sdf.ellipsoid(P, *self.rims[0]), sdf.ellipsoid(P, *self.rims[1]))
        alae = sdf.smin(alae, rims, 3.5)
        nostrils = np.minimum(sdf.ellipsoid(P, *self.nostrils[0]), sdf.ellipsoid(P, *self.nostrils[1]))
        return nose, alae, nostrils

    def bounding_box_sdf(self, P):
        x, y, z = P[:, 0], P[:, 1], P[:, 2]
        return _vmax([np.abs(x) - self.half_x, z - self.z_max, self.z_min - z, self.y_back - y])

    def raw_fields(self, P):
        """Unnormalised skin SDF, nose dominance weight and dorsal parameter t."""
        face = self.face_sdf(P)
        nose, alae, nostrils = self.nose_parts(P)
        # Alae blend smoothly into the lobule but keep a crisp alar-facial groove.
        skin = sdf.smin(sdf.smin(face, nose, 5.0), sdf.smin(nose, alae, 5.0), 1.4)
        skin = sdf.ssub(skin, nostrils, 0.8)
        nose_all = sdf.smin(nose, alae, 2.0)
        w = sdf.smoothstep(-1.0, 3.0, face - nose_all)
        t = ((P - self.lm.nasion) @ self.lm.dorsum_dir) / self.L
        return skin, w, t

    # ----------------------------------------------------------------- grid
    def make_grid(self, spacing: float) -> Grid:
        lo = np.array([-self.half_x - 1.5, self.y_back - 1.5, self.z_min - 1.5])
        hi = np.array([self.half_x + 1.5, self.lm.pronasale[1] + 3.0, self.z_max + 1.5])
        shape = tuple(int(np.ceil((hi[i] - lo[i]) / spacing)) + 1 for i in range(3))
        return Grid(origin=lo, spacing=spacing, shape=shape)

    def evaluate(self, spacing: float = 0.35, cut: Cut | None = None,
                 per_structure_cut: dict | None = None, nose_only=(), windows: dict | None = None,
                 detail: bool = False, drape: bool = False, progress=None) -> Fields:
        grid = self.make_grid(spacing)
        nx, ny, nz = grid.shape
        skin = np.empty(grid.shape, np.float32)
        w = np.empty(grid.shape, np.float32)
        t = np.empty(grid.shape, np.float32)
        slab = max(1, int(2_000_000 // (ny * nz)))
        for k0 in range(0, nx, slab):
            k1 = min(nx, k0 + slab)
            P = grid.points(k0, k1)
            s, ww, tt = self.raw_fields(P)
            skin[k0:k1] = s.reshape(k1 - k0, ny, nz)
            w[k0:k1] = ww.reshape(k1 - k0, ny, nz)
            t[k0:k1] = tt.reshape(k1 - k0, ny, nz)
            if progress:
                progress(k1 / nx)

        # Normalise so that offsets are (close to) true distances in millimetres.
        g = np.gradient(skin, spacing)
        gn = np.sqrt(g[0] ** 2 + g[1] ** 2 + g[2] ** 2)
        del g
        skin_n = skin / np.clip(gn, 0.35, 3.0)
        del skin, gn
        skin_n = self._exact_distance(skin_n, spacing)

        T = np.where(w > 0,
                     self.p["soft_tissue.thickness_face"] * (1 - w) + self._thick(np.clip(t, -0.4, 1.4)) * w,
                     self.p["soft_tissue.thickness_face"]).astype(np.float32)
        fields = Fields(grid=grid, skin_n=skin_n, thickness=T, nose_weight=w, t_param=t)
        self._build_structures(fields)
        for name in nose_only:
            if name in fields.volumes:
                fields.volumes[name] = np.maximum(fields.volumes[name], (0.3 - w) * 12.0)
        if detail:
            self._add_fat_lobules(fields)
        if drape:
            fields.volumes["drape"] = self._drape(fields)
        fields.uncut = {k: v.copy() for k, v in fields.volumes.items()}
        self._apply_windows(fields, windows or {})
        self._apply_cuts(fields, cut, per_structure_cut or {})
        return fields

    # ------------------------------------------------------ dissection detail
    def _noise2d(self, grid: Grid, scale_mm: float, seed: int) -> np.ndarray:
        """Smooth random field on the (x, z) plane, unit standard deviation, shape (nx, 1, nz)."""
        rng = np.random.default_rng(seed)
        nx, _, nz = grid.shape
        field2 = ndimage.gaussian_filter(rng.normal(size=(nx, nz)), scale_mm / grid.spacing, mode="wrap")
        field2 /= field2.std() + 1e-9
        return field2[:, None, :].astype(np.float32)

    def _apply_windows(self, f: Fields, windows: dict):
        X, _, Z = self._grid_xyz(f.grid)
        for name, win in windows.items():
            if name not in f.volumes:
                continue
            a, b = win.radii
            cx, cz = win.center
            e = (np.sqrt(((X - cx) / a) ** 2 + ((Z - cz) / b) ** 2) - 1.0) * min(a, b)
            e = e + win.ragged * (self._noise2d(f.grid, 3.0, win.seed)
                                  + 0.35 * self._noise2d(f.grid, 0.8, win.seed + 99))
            f.volumes[name] = np.maximum(f.volumes[name], -e)

    def _add_fat_lobules(self, f: Fields, seed: int = 3):
        """Fat lobules separated by fibrous septa: Voronoi relief on the adipose layers."""
        from scipy.spatial import cKDTree
        rng = np.random.default_rng(seed)
        g = f.grid
        lo, hi = g.origin, g.origin + g.spacing * (np.array(g.shape) - 1)
        for name, cell, amp in (("superficial_fat", 2.2, 0.32), ("deep_fat", 1.8, 0.25)):
            vol = f.volumes.get(name)
            if vol is None:
                continue
            n_seeds = int(np.prod(hi - lo) / cell ** 3)
            tree = cKDTree(rng.uniform(lo, hi, size=(n_seeds, 3)))
            idx = np.nonzero(np.abs(vol) < 1.2)
            pts = np.stack([g.origin[i] + g.spacing * idx[i] for i in range(3)], axis=1)
            d, _ = tree.query(pts, k=2, workers=-1)
            edge = np.clip((d[:, 1] - d[:, 0]) / (0.45 * cell), 0.0, 1.0)
            vol[idx] -= (amp * np.sqrt(edge)).astype(np.float32)

    def _drape(self, f: Fields) -> np.ndarray:
        """Fenestrated dissection drape lying on the face around the operative field."""
        lm = self.lm
        X, _, Z = self._grid_xyz(f.grid)
        S = f.skin_n
        folds = 1.4 * np.abs(self._noise2d(f.grid, 7.0, 11)) + 0.5 * self._noise2d(f.grid, 2.5, 12)
        cz = 0.5 * (lm.nasion[2] + lm.subnasale[2]) - 2.0
        a, b = self.alar_half + 9.0, 0.5 * (lm.nasion[2] - lm.subnasale[2]) + 17.0
        e = (np.sqrt((X / a) ** 2 + ((Z - cz) / b) ** 2) - 1.0) * a
        e = e + 1.2 * self._noise2d(f.grid, 5.0, 13)
        lift = 1.2 + folds + 0.06 * np.clip(e, 0, None)     # the drape rises away from the opening
        shell = np.maximum(lift - S, S - (lift + 0.9))
        return np.maximum(shell, -e)

    @staticmethod
    def _exact_distance(field, h):
        """Replace the far field with a Euclidean distance transform so that deep offsets
        (layers, framework) stay free of the artefacts of an approximate SDF."""
        inside = field < 0
        d_out = ndimage.distance_transform_edt(~inside, sampling=h).astype(np.float32)
        d_in = ndimage.distance_transform_edt(inside, sampling=h).astype(np.float32)
        edt = np.where(inside, -(d_in - 0.5 * h), d_out - 0.5 * h)
        near = np.abs(field) < 1.5 * h
        return np.where(near, field, edt).astype(np.float32)

    # ---------------------------------------------------------- structures
    def _grid_xyz(self, grid: Grid):
        xs, ys, zs = grid.axes
        return (xs[:, None, None].astype(np.float32), ys[None, :, None].astype(np.float32),
                zs[None, None, :].astype(np.float32))

    def _filler_field(self, grid: Grid):
        if self.filler is None:
            return None
        center, radii, rot = self.filler
        nx, ny, nz = grid.shape
        out = np.empty(grid.shape, np.float32)
        slab = max(1, int(2_000_000 // (ny * nz)))
        for k0 in range(0, nx, slab):
            k1 = min(nx, k0 + slab)
            out[k0:k1] = sdf.ellipsoid(grid.points(k0, k1), center, radii, rot).reshape(k1 - k0, ny, nz)
        return out

    def _build_structures(self, f: Fields):
        p, lm = self.p, self.lm
        S, T, w, t = f.skin_n, f.thickness, f.nose_weight, f.t_param
        X, Y, Z = self._grid_xyz(f.grid)
        B = self._filler_field(f.grid)

        def boundary(frac):
            depth = T * frac
            b = S + depth
            if B is not None:
                b = sdf.smin(b, B - (T - depth), 2.0)
            return b

        depths = [self.depth_frac[k][0] for k in LAYER_ORDER] + [1.0]
        bnd = [boundary(d) for d in depths]
        vols = f.volumes
        vols["skin"] = np.maximum(bnd[0], -bnd[1])
        vols["superficial_fat"] = np.maximum(bnd[1], -bnd[2])
        vols["smas"] = np.maximum(bnd[2], -bnd[3])
        deep = np.maximum(bnd[3], -bnd[4])   # periosteum is merged into the framework shell

        outer = S + T * depths[4]          # top of the osteocartilaginous framework
        L = self.L
        t_r = p["morphology.rhinion_position"]
        t_s = p["framework.scroll_position"]
        bone_t = p["framework.bone_thickness"]
        cart_t = p["framework.cartilage_thickness"]
        nose_mask = (0.5 - w) * 12.0                 # < 0 where the nose dominates
        absx = np.abs(X)

        # Piriform aperture: pear-shaped, narrow under the nasal bones, widest near the floor.
        sn = lm.subnasale
        z_floor, z_top = sn[2] + 3.0, lm.rhinion[2]
        u = np.clip((Z - z_floor) / (z_top - z_floor), 0.0, 1.0)
        half_w = (self.alar_half - 4.0) * np.sqrt(1.0 - u ** 2) * (1.0 - 0.5 * u) + 3.0
        aperture = _vmax([absx - half_w, z_floor - Z, Z - z_top])

        # Nasal cavity: behind the piriform aperture and, higher up, under the nasal bones.
        cav_top = lm.nasion[2] - 6.0
        upper_cav = _vmax([absx - (5.0 + 0.12 * (lm.rhinion[2] - Z).clip(0)), Z - cav_top,
                           lm.rhinion[2] - Z - 2.0])
        cavity = np.minimum(aperture, upper_cav)

        # Bone: nasal bones and frontal processes as a cortical shell over the cavity, the rest of
        # the facial skeleton (frontal bone, maxillae) solid so that sections look like sections.
        bone_shell = np.maximum(outer, -(outer + bone_t))
        shell = _vmax([bone_shell, -aperture, (lm.face_y - 9.0) - Y])
        vols["bone"] = np.minimum(shell, np.maximum(outer, -cavity))

        # Upper lateral cartilages: from under the nasal bones (keystone overlap) to the scroll.
        cart_shell = np.maximum(outer, -(outer + cart_t))
        vols["upper_lateral_cartilage"] = _vmax([cart_shell, aperture - 0.3, (t_r - 0.06 - t) * L,
                                                 (t - t_s) * L + 0.5])

        # Lower lateral cartilages: domes + lateral crura running cephalolaterally as a
        # ~9 mm wide band that stops short of the piriform aperture (the ala is fibro-fatty).
        T_ = lm.pronasale
        band = np.full(X.shape, np.inf, np.float32)
        for s_ in (1.0, -1.0):
            a2 = np.array([s_ * 3.0, T_[2] + 3.0])
            b2 = np.array([s_ * (self.alar_half - 5.0), sn[2] + 17.5])
            ab = b2 - a2
            px, pz = X - a2[0], Z - a2[1]
            hh = np.clip((px * ab[0] + pz * ab[1]) / float(ab @ ab), 0.0, 1.0)
            dist = np.sqrt((px - hh * ab[0]) ** 2 + (pz - hh * ab[1]) ** 2) - (6.2 - 1.6 * hh)
            band = np.minimum(band, dist)
        band = _vmax([band, (lm.face_y + 3.0) - Y, (sn[2] + 7.0) - Z])
        llc = _vmax([cart_shell, band, nose_mask * 0.6])
        vols["upper_lateral_cartilage"] = np.maximum(vols["upper_lateral_cartilage"], -(band - 0.6))
        # Medial crura: paired plates inside the columella, joining the domes.
        dome_mid = 0.5 * (self.domes[0] + self.domes[1])
        P_axis_a = sn + self.n_col * 2.2 + lm.columella_dir * 1.5
        col_d = self._capsule_grid(X, Y, Z, P_axis_a, dome_mid - np.array([0, 1.0, 0]), 4.5)
        crura = _vmax([np.abs(absx - 1.5) - 0.45, col_d, S + 1.1])
        vols["lower_lateral_cartilage"] = np.minimum(llc, crura)

        septum_region = _vmax([(t_r - 0.18 - t) * L, (t - 0.97) * L, (sn[2] + 3.0) - Z,
                                           (lm.face_y - 6.0) - Y])
        vols["septum"] = _vmax([absx - 0.9, outer + 0.4, septum_region, S + 1.0])

        # Respiratory mucosa: lines the inner surface of the framework and both faces of the septum.
        inner = outer + np.where(t < t_r, bone_t, cart_t)
        lining = _vmax([-inner, inner + 1.3, cavity + 0.5, (lm.face_y - 6.0) - Y])
        septal_region = _vmax([(t_r - 0.18 - t) * L, (sn[2] + 3.0) - Z, outer + 0.9, S + 1.0, cavity - 0.5])
        septal = _vmax([np.abs(absx - 1.45) - 0.55, septal_region])
        # bony septum (perpendicular plate of the ethmoid / vomer) behind the cartilage
        bony_septum = _vmax([absx - 0.9, septal_region, Y - (lm.face_y - 5.5)])
        vols["bone"] = np.minimum(vols["bone"], bony_septum)
        vols["mucosa"] = np.minimum(lining, septal)

        if B is not None:
            fill = np.maximum(B, -outer)
            vols["filler"] = fill
            deep = np.maximum(deep, -fill)
        vols["deep_fat"] = deep

    @staticmethod
    def _capsule_grid(X, Y, Z, a, b, r):
        a = np.asarray(a, np.float32)
        ba = np.asarray(b, np.float32) - a
        px, py, pz = X - a[0], Y - a[1], Z - a[2]
        h = np.clip((px * ba[0] + py * ba[1] + pz * ba[2]) / float(ba @ ba), 0.0, 1.0)
        dx, dy, dz = px - h * ba[0], py - h * ba[1], pz - h * ba[2]
        return np.sqrt(dx * dx + dy * dy + dz * dz) - r

    def _apply_cuts(self, f: Fields, cut: Cut | None, per_structure: dict):
        X, Y, Z = self._grid_xyz(f.grid)
        box = _vmax([np.abs(X) - self.half_x, Z - self.z_max, self.z_min - Z, self.y_back - Y])
        for name, vol in f.volumes.items():
            vol = np.maximum(vol, box)
            limit = per_structure.get(name, cut.limit if cut else None)
            if limit is not None:
                vol = np.maximum(vol, X - limit)
            f.volumes[name] = vol

    # -------------------------------------------------------------- arteries
    def arteries(self, f: Fields, seed: int = 7) -> list[dict]:
        """Arterial centrelines as polylines (mm) with radius and label."""
        p, lm = self.p, self.lm
        interp_S = RegularGridInterpolator(f.grid.axes, f.skin_n, bounds_error=False, fill_value=10.0)
        interp_T = RegularGridInterpolator(f.grid.axes, f.thickness, bounds_error=False, fill_value=5.0)
        rng = np.random.default_rng(seed)
        sn, N, Tp = lm.subnasale, lm.nasion, lm.pronasale
        aw = self.alar_half
        v = "vasculature."
        plane_frac = self.depth_frac["smas"][0]   # on the superficial surface of the SMAS

        def surface_points(xz, depth_fn, wiggle=0.35):
            pts = []
            y_axis = np.linspace(lm.pronasale[1] + 2.5, self.y_back, 1400)
            for x, z in xz:
                col = np.stack([np.full_like(y_axis, x), y_axis, np.full_like(y_axis, z)], axis=1)
                s = interp_S(col)
                idx = np.nonzero(s < 0)[0]
                if len(idx) == 0:
                    continue
                i = idx[0]
                y0 = y_axis[i - 1] + (y_axis[i] - y_axis[i - 1]) * s[i - 1] / (s[i - 1] - s[i]) if i > 0 else y_axis[i]
                q = np.array([x, y0, z])
                h = 0.2
                grad = np.array([(interp_S([q + e])[0] - interp_S([q - e])[0]) / (2 * h)
                                 for e in np.eye(3) * h])
                n = grad / max(np.linalg.norm(grad), 1e-6)
                depth = depth_fn(q, float(interp_T([q])[0]))
                pts.append(q - n * depth)
            pts = np.array(pts)
            if len(pts) > 3 and wiggle > 0:
                # gentle, low-frequency tortuosity (tangential to the surface)
                u = np.linspace(0, 1, len(pts))
                env = np.sin(np.pi * u)
                for axis in (0, 2):
                    phase, freq = rng.uniform(0, 2 * np.pi, 2), rng.uniform(2.0, 4.5, 2)
                    pts[:, axis] += wiggle * 2.0 * env * (np.sin(2 * np.pi * freq[0] * u + phase[0])
                                                          + 0.4 * np.sin(2 * np.pi * freq[1] * u + phase[1]))
            return pts

        def dense(ctrl, n=48):
            ctrl = np.asarray(ctrl, float)
            u = np.linspace(0, 1, len(ctrl))
            uu = np.linspace(0, 1, n)
            return np.stack([np.interp(uu, u, ctrl[:, 0]), np.interp(uu, u, ctrl[:, 1])], axis=1)

        on_smas = lambda q, T: T * plane_frac
        vessels = []
        for s in (1, -1):
            side = "sx" if s > 0 else "dx"
            # Angular artery: along the nasofacial groove up to the medial canthus.
            ang = dense([(s * (aw + 3.5), sn[2] + 1.0), (s * (aw + 2.2), sn[2] + 12.0),
                         (s * (aw - 0.5), sn[2] + 24.0), (s * 13.5, -12.0), (s * 12.5, -3.0)])
            vessels.append(dict(name=f"angular_{side}", label="angular",
                                points=surface_points(ang, lambda q, T: p[v + "angular_depth"]),
                                radius=p[v + "angular_diameter"] / 2))
            # Lateral nasal artery: above the alar groove towards the tip (alar arcade).
            lat = dense([(s * (aw + 1.5), sn[2] + 11.0), (s * (aw - 3.0), sn[2] + 13.5),
                         (s * (aw - 8.0), sn[2] + 14.5), (s * 6.0, Tp[2] + 5.0), (s * 3.0, Tp[2] + 1.5)])
            vessels.append(dict(name=f"lateral_nasal_{side}", label="lateral_nasal",
                                points=surface_points(lat, on_smas),
                                radius=p[v + "lateral_nasal_diameter"] / 2))
            # Columellar artery: from the superior labial artery up the columella.
            col_ctrl = [sn + np.array([s * 2.0, 0, -2.0]), sn + lm.columella_dir * 4 + np.array([s * 2.3, 0, 0]),
                        sn + lm.columella_dir * 9 + np.array([s * 2.3, 0, 0]), Tp + np.array([s * 2.0, 0, -3.5])]
            col_xz = dense([(c[0], c[2]) for c in col_ctrl], 32)
            depth_col = p[v + "columellar_depth"]
            vessels.append(dict(name=f"columellar_{side}", label="columellar",
                                points=self._columella_points(interp_S, col_xz, col_ctrl, depth_col),
                                radius=p[v + "columellar_diameter"] / 2))

        pattern = p[v + "dorsal_nasal_pattern"]
        r_dn = p[v + "dorsal_nasal_diameter"] / 2
        if pattern == "bilateral":
            for s in (1, -1):
                dn = dense([(s * 10.5, -3.0), (s * 6.0, lm.rhinion[2] * 0.4), (s * 4.2, lm.rhinion[2]),
                            (s * 3.6, lm.supratip[2]), (s * 3.2, Tp[2] + 3.0)])
                vessels.append(dict(name=f"dorsal_nasal_{'sx' if s > 0 else 'dx'}", label="dorsal_nasal",
                                    points=surface_points(dn, on_smas), radius=r_dn))
        elif pattern == "single_dominant":
            dn = dense([(9.5, -3.0), (3.0, lm.rhinion[2] * 0.5), (0.8, lm.rhinion[2]),
                        (0.6, lm.supratip[2]), (0.5, Tp[2] + 3.0)])
            vessels.append(dict(name="dorsal_nasal_dominante", label="dorsal_nasal",
                                points=surface_points(dn, on_smas), radius=r_dn * 1.25))
        else:  # plexus of minute arteries
            for i in range(7):
                x0 = rng.uniform(-6, 6)
                zz = np.linspace(-2 - rng.uniform(0, 6), lm.supratip[2] + rng.uniform(0, 10), 5)
                xs = x0 + np.cumsum(rng.normal(0, 1.4, 5))
                vessels.append(dict(name=f"dorsal_plexus_{i}", label="dorsal_nasal",
                                    points=surface_points(list(zip(xs, zz)), on_smas, wiggle=0.6),
                                    radius=r_dn * 0.45))
        return [vv for vv in vessels if len(vv["points"]) >= 2]

    def _columella_points(self, interp_S, xz, ctrl, depth):
        """The columella faces antero-inferiorly: search along its normal instead of y."""
        pts = []
        n_out = -self.n_col
        ctrl = np.asarray(ctrl)
        for x, z in xz:
            # nearest control point gives the local plane position
            base = ctrl[np.argmin(np.abs(ctrl[:, 2] - z))].copy()
            base[0], base[2] = x, z
            start = base + n_out * 8.0
            ray = start[None, :] - n_out[None, :] * np.linspace(0, 16, 800)[:, None]
            s = interp_S(ray)
            idx = np.nonzero(s < 0)[0]
            if len(idx):
                pts.append(ray[idx[0]] - n_out * depth * 0.8)
        return np.array(pts)

    # --------------------------------------------------------------- labels
    def label_anchors(self, f: Fields) -> dict:
        """Representative 3D points for annotation (mm)."""
        lm = self.lm
        aw = self.alar_half
        t_r = self.p["morphology.rhinion_position"]
        t_s = self.p["framework.scroll_position"]
        def on_dorsum(t, depth=0.0, x=0.0):
            q = lm.dorsum_point(t) + np.array([x, 0, 0])
            return q - self.n_ant * depth
        T = lambda t: float(self._thick(t))
        return {
            "nasion": lm.nasion, "rhinion": lm.rhinion, "pronasale": lm.pronasale,
            "subnasale": lm.subnasale, "supratip": lm.supratip,
            "skin": on_dorsum(0.55, 0.3, 3.5),
            "superficial_fat": on_dorsum(0.2, T(0.2) * 0.45, 5.0),
            "smas": on_dorsum(0.3, T(0.3) * 0.65, 4.0),
            "deep_fat": on_dorsum(0.12, T(0.12) * 0.84, 3.0),
            "bone": on_dorsum(t_r * 0.5, T(t_r * 0.5) + 0.4, 4.0),
            "upper_lateral_cartilage": on_dorsum(0.5 * (t_r + t_s), T(0.5 * (t_r + t_s)) + 0.2, 5.0),
            "lower_lateral_cartilage": self.domes[0] + np.array([1.5, -1.0, 2.5]),
            "septum": on_dorsum(0.6, T(0.6) + 6.0, 0.0),
            "ala": self.alae[0][0] + np.array([2.5, 2.0, 0.0]),
            "columella": self.col_b - self.n_col * 3.0,
            "piriform_aperture": np.array([aw - 3.0, lm.face_y - 3.0, lm.subnasale[2] + 15.0]),
            "filler": self.filler[0] if self.filler is not None else None,
        }
