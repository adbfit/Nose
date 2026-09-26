"""Download (once) and cache the BodyParts3D meshes of the face."""

from __future__ import annotations

import os
import sys
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from .catalogo import ATTRIBUTION, SOURCE, STRUTTURE

CACHE = Path(os.environ.get("ATLAS3D_CACHE", Path.home() / ".cache" / "atlas3d" / "bodyparts3d"))


def path_for(fma: str) -> Path:
    return CACHE / f"{fma}.stl"


def fetch(fma: str, retries: int = 4) -> Path:
    dst = path_for(fma)
    if dst.exists() and dst.stat().st_size > 1000:
        return dst
    dst.parent.mkdir(parents=True, exist_ok=True)
    url = SOURCE.format(fma=fma)
    last = None
    for _ in range(retries):
        try:
            tmp = dst.with_suffix(".part")
            with urllib.request.urlopen(url, timeout=300) as r, open(tmp, "wb") as fh:
                while chunk := r.read(1 << 20):
                    fh.write(chunk)
            tmp.replace(dst)
            return dst
        except Exception as exc:  # network hiccups: retry
            last = exc
    raise RuntimeError(f"download fallito per {fma}: {last}")


def fetch_all(ids=None, workers: int = 6) -> dict:
    ids = list(ids or STRUTTURE)
    with ThreadPoolExecutor(workers) as ex:
        paths = dict(zip(ids, ex.map(fetch, ids)))
    (CACHE / "ATTRIBUTION.txt").write_text(ATTRIBUTION + "\n", encoding="utf-8")
    return paths


if __name__ == "__main__":
    for fma, p in fetch_all(sys.argv[1:] or None).items():
        print(fma, p, p.stat().st_size)
