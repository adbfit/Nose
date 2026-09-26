"""Marching cubes extraction of the anatomical structures."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from skimage import measure

from .anatomy import Fields


@dataclass
class Mesh:
    name: str
    vertices: np.ndarray   # (N, 3) millimetres
    faces: np.ndarray      # (M, 3)

    @property
    def empty(self) -> bool:
        return len(self.faces) == 0


def extract(fields: Fields, name: str, smooth_iterations: int = 4) -> Mesh:
    vol = fields.volumes[name]
    if vol.min() >= 0 or vol.max() <= 0:
        return Mesh(name, np.zeros((0, 3)), np.zeros((0, 3), dtype=np.int64))
    padded = np.pad(vol, 1, mode="constant", constant_values=float(np.abs(vol).max()))
    h = fields.grid.spacing
    verts, faces, _, _ = measure.marching_cubes(padded, level=0.0, spacing=(h, h, h),
                                                allow_degenerate=False)
    verts = verts - h + fields.grid.origin
    if smooth_iterations:
        verts = taubin_smooth(verts, faces, smooth_iterations)
    return Mesh(name, verts.astype(np.float64), faces.astype(np.int64))


def taubin_smooth(verts, faces, iterations=4, lam=0.5, mu=-0.53):
    """Volume-preserving Laplacian smoothing to remove voxel stair-steps."""
    n = len(verts)
    edges = np.concatenate([faces[:, [0, 1]], faces[:, [1, 2]], faces[:, [2, 0]]])
    edges = np.concatenate([edges, edges[:, ::-1]])
    deg = np.bincount(edges[:, 0], minlength=n).astype(np.float64)
    deg[deg == 0] = 1
    v = verts.astype(np.float64).copy()
    for _ in range(iterations):
        for factor in (lam, mu):
            acc = np.zeros_like(v)
            np.add.at(acc, edges[:, 0], v[edges[:, 1]])
            v += factor * (acc / deg[:, None] - v)
    return v
