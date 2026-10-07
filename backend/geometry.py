"""Dependency-free STL geometry checks (stdlib + numpy).

Used by design_save when a model uploads its STL: envelope fit, manifoldness,
stem preservation vs the line adapter, base-preserved proof, and measured
dims/volume that override self-reported numbers. Binary and ASCII STL both
parse; a file starting with b"solid" is still treated as binary when its
size matches the binary header count (the standard ambiguity).
"""
from __future__ import annotations

import struct

import numpy as np

MAX_STL_BYTES = 8 * 1024 * 1024


def parse_stl(blob: bytes) -> np.ndarray:
    """Raw triangle soup: float64 array shaped (n, 3, 3). Raises ValueError."""
    if len(blob) < 84 or len(blob) > MAX_STL_BYTES:
        raise ValueError(f"STL must be 84B–8MB, got {len(blob)}B")
    n, = struct.unpack("<I", blob[80:84])
    if n > 0 and 84 + 50 * n == len(blob):
        tris = np.frombuffer(blob, dtype=np.uint8, count=n * 50, offset=84)
        tris = tris.reshape(n, 50)[:, :48].reshape(n, 12)
        floats = tris.view("<f4").reshape(n, 4, 3).astype(np.float64)
        return floats[:, 1:, :]  # skip facet normals, keep 3 vertices
    text = blob.decode("utf-8", errors="strict")
    verts, cur = [], []
    for line in text.splitlines():
        p = line.split()
        if p[:1] == ["vertex"]:
            cur.append([float(p[1]), float(p[2]), float(p[3])])
            if len(cur) == 3:
                verts.append(cur)
                cur = []
    if not verts:
        raise ValueError("no triangles parsed")
    return np.array(verts, dtype=np.float64)


def bbox(tris: np.ndarray) -> list[float]:
    lo = tris.min(axis=(0, 1))
    hi = tris.max(axis=(0, 1))
    return [round(float(hi[i] - lo[i]), 2) for i in range(3)]


def volume_cm3(tris: np.ndarray) -> float:
    v0, v1, v2 = tris[:, 0], tris[:, 1], tris[:, 2]
    vol = float(np.sum(np.einsum("ij,ij->i", v0, np.cross(v1, v2))) / 6.0)
    return round(abs(vol) / 1000.0, 2)


def manifold_gaps(tris: np.ndarray) -> list[str]:
    """Every edge shared by exactly two triangles (rounded to 1µm)."""
    v = np.round(tris.reshape(-1, 3), 3)
    n = len(v) // 3
    e = np.concatenate([v.reshape(n, 3, 3)[:, [0, 1]],
                        v.reshape(n, 3, 3)[:, [1, 2]],
                        v.reshape(n, 3, 3)[:, [2, 0]]]).reshape(-1, 2, 3)
    e = np.sort(e, axis=1)
    _, counts = np.unique(e.reshape(-1, 6), axis=0, return_counts=True)
    bad = int(np.sum(counts != 2))
    if bad:
        return [f"non-manifold: {bad} boundary/dangling edges"]
    return []


def stem_gaps(tris: np.ndarray, stem: dict) -> list[str]:
    """Pin-band verts must sit inside the locked diameter (axis = Z)."""
    try:
        z0, z1, dia = float(stem["z_min"]), float(stem["z_max"]), float(stem["dia_mm"])
    except (KeyError, TypeError, ValueError):
        return []
    v = tris.reshape(-1, 3)
    band = v[(v[:, 2] > z0) & (v[:, 2] < z1)]
    if len(band) < 3:
        return ["stem band empty — locked pin missing"]
    rmax = float(np.hypot(band[:, 0], band[:, 1]).max())
    if rmax > dia / 2 + 0.3:
        return [f"stem r {rmax:.2f}mm exceeds locked dia {dia}mm"]
    return []


def base_preserved_gaps(upload: np.ndarray, base: np.ndarray,
                        tol: float = 0.15, need: float = 0.90) -> list[str]:
    """Share of base verts still present in the upload (chunked, 0.15mm)."""
    bv = base.reshape(-1, 3)
    uv = upload.reshape(-1, 3)
    found = np.zeros(len(bv), dtype=bool)
    for i in range(0, len(uv), 20000):
        d = np.linalg.norm(uv[i:i + 20000, None, :] - bv[None, :, :], axis=2)
        found |= d.min(axis=0) <= tol
        if found.mean() >= need:
            break
    share = float(found.mean())
    if share < need:
        return [f"base geometry {share:.0%} preserved, need {need:.0%} — design inside the base"]
    return []
