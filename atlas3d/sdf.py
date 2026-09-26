"""Vectorised signed-distance primitives (numpy). Negative inside, positive outside.

Points are passed as an (N, 3) float array; every function returns an (N,) array.
Formulas follow the well-known closed forms collected by Inigo Quilez.
"""

from __future__ import annotations

import numpy as np


def _norm(v, axis=-1):
    return np.sqrt(np.sum(v * v, axis=axis))


def rotation(yaw=0.0, pitch=0.0, roll=0.0) -> np.ndarray:
    """Rotation matrix (degrees). yaw about z, pitch about x, roll about y."""
    y, p, r = np.radians([yaw, pitch, roll])
    rz = np.array([[np.cos(y), -np.sin(y), 0], [np.sin(y), np.cos(y), 0], [0, 0, 1]])
    rx = np.array([[1, 0, 0], [0, np.cos(p), -np.sin(p)], [0, np.sin(p), np.cos(p)]])
    ry = np.array([[np.cos(r), 0, np.sin(r)], [0, 1, 0], [-np.sin(r), 0, np.cos(r)]])
    return rz @ rx @ ry


def to_local(P, center, rot=None):
    q = P - np.asarray(center, dtype=P.dtype)
    if rot is not None:
        q = q @ np.asarray(rot, dtype=P.dtype)  # inverse rotation (R^T applied on the right)
    return q


def ellipsoid(P, center, radii, rot=None):
    q = to_local(P, center, rot)
    r = np.asarray(radii, dtype=P.dtype)
    k0 = _norm(q / r)
    k1 = _norm(q / (r * r))
    return k0 * (k0 - 1.0) / np.maximum(k1, 1e-9)


def sphere(P, center, radius):
    return _norm(P - np.asarray(center, dtype=P.dtype)) - radius


def round_cone(P, a, b, r1, r2):
    """Cone between a (radius r1) and b (radius r2) with spherical caps."""
    a = np.asarray(a, dtype=P.dtype)
    b = np.asarray(b, dtype=P.dtype)
    ba = b - a
    l2 = float(ba @ ba)
    rr = r1 - r2
    a2 = l2 - rr * rr
    il2 = 1.0 / l2
    pa = P - a
    y = pa @ ba
    z = y - l2
    xv = pa * l2 - y[:, None] * ba
    x2 = np.sum(xv * xv, axis=1)
    y2 = y * y * l2
    z2 = z * z * l2
    k = np.sign(rr) * rr * rr * x2
    out = (np.sqrt(x2 * a2 * il2) + y * rr) * il2 - r1
    cap_b = np.sign(z) * a2 * z2 > k
    cap_a = np.sign(y) * a2 * y2 < k
    out = np.where(cap_b, np.sqrt(x2 + z2) * il2 - r2, out)
    out = np.where(cap_a, np.sqrt(x2 + y2) * il2 - r1, out)
    return out


def capsule(P, a, b, r):
    a = np.asarray(a, dtype=P.dtype)
    b = np.asarray(b, dtype=P.dtype)
    pa = P - a
    ba = b - a
    h = np.clip((pa @ ba) / float(ba @ ba), 0.0, 1.0)
    return _norm(pa - h[:, None] * ba) - r


def smin(a, b, k):
    """Polynomial smooth minimum (smooth union)."""
    if k <= 0:
        return np.minimum(a, b)
    h = np.clip(0.5 + 0.5 * (b - a) / k, 0.0, 1.0)
    return b + (a - b) * h - k * h * (1.0 - h)


def smax(a, b, k):
    """Smooth maximum (smooth intersection)."""
    return -smin(-a, -b, k)


def ssub(a, b, k):
    """Smoothly subtract b from a."""
    return smax(a, -b, k)


def smoothstep(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)
