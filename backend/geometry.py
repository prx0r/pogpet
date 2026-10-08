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

MAX_STL_BYTES = 32 * 1024 * 1024


def parse_stl(blob: bytes) -> np.ndarray:
    """Raw triangle soup: float64 array shaped (n, 3, 3). Raises ValueError."""
    if len(blob) < 84 or len(blob) > MAX_STL_BYTES:
        raise ValueError(f"STL must be 84B–8MB, got {len(blob)}B")
    n, = struct.unpack("<I", blob[80:84])
    if n > 0 and 84 + 50 * n == len(blob):
        raw = np.frombuffer(blob, dtype=np.uint8, count=n * 50, offset=84)
        floats = raw.reshape(n, 50)[:, :48].reshape(n, 12, 4).view("<f4")
        return np.ascontiguousarray(floats.reshape(n, 4, 3)[:, 1:, :], dtype=np.float64)
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


def nonmanifold_spots(tris: np.ndarray, limit: int = 3) -> list[list[float]]:
    """Centroids of boundary/dangling edges, for pointing at the failure."""
    v = np.round(tris.reshape(-1, 3), 3)
    n = len(v) // 3
    tris3 = v.reshape(n, 3, 3)
    e = np.concatenate([tris3[:, [0, 1]], tris3[:, [1, 2]],
                        tris3[:, [2, 0]]]).reshape(-1, 2, 3)
    es = np.sort(e, axis=1)
    keys, counts = np.unique(es.reshape(-1, 6), axis=0, return_counts=True)
    bad = keys[counts != 2][:limit]
    return [[round(float(x), 2) for x in edge.reshape(2, 3).mean(axis=0)]
            for edge in bad]


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
        spots = nonmanifold_spots(tris)
        where = (" near " + ", ".join(f"({s[0]},{s[1]},{s[2]})" for s in spots)
                 if spots else "")
        return [f"non-manifold: {bad} boundary/dangling edges{where}"]
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


def base_match(upload: np.ndarray, base: np.ndarray, tol: float = 0.15) -> float:
    """Share of base verts still present in the upload (chunked, 0.15mm).
    Booleans move base verts legitimately, so this is a scored signal, not
    a hard gate: ≥0.9 intact, 0.6–0.9 derived, below is a remodel."""
    bv = base.reshape(-1, 3)
    uv = upload.reshape(-1, 3)
    found = np.zeros(len(bv), dtype=bool)
    for i in range(0, len(uv), 20000):
        d = np.linalg.norm(uv[i:i + 20000, None, :] - bv[None, :, :], axis=2)
        found |= d.min(axis=0) <= tol
        if found.mean() >= 0.9:
            break
    return round(float(found.mean()), 3)


def base_preserved_gaps(upload: np.ndarray, base: np.ndarray,
                        tol: float = 0.15, need: float = 0.60) -> list[str]:
    """Hard gate at `need` (default 0.6: derived-from-base). The exact share
    comes from base_match() for honest reporting above the bar."""
    if base_match(upload, base, tol) < need:
        return [f"base geometry under {need:.0%} preserved — design inside the base"]
    return []


def parse_glb(blob: bytes) -> np.ndarray:
    """GLB -> triangle soup (n,3,3) float64. De-indexed; no new deps."""
    import json as _json
    if len(blob) < 12 or blob[:4] != b"glTF":
        raise ValueError("not a GLB")
    off, json_doc,buffer = 12, None, b""
    while off + 8 <= len(blob):
        (ln,) = struct.unpack("<I", blob[off:off + 4])
        typ = blob[off + 4:off + 8]
        data = blob[off + 8:off + 8 + ln]
        if typ == b"JSON":
            json_doc = _json.loads(data.decode("utf-8"))
        elif typ == b"BIN\x00":
            buffer = bytes(data)
        off += 8 + ln
    if json_doc is None:
        raise ValueError("GLB has no JSON chunk")
    accessors = json_doc.get("accessors", [])
    views = json_doc.get("bufferViews", [])

    def read_acc(idx: int) -> np.ndarray:
        acc = accessors[idx]
        view = views[acc["bufferView"]]
        start = int(view.get("byteOffset", 0)) + int(acc.get("byteOffset", 0))
        ctype = {5121: "u1", 5123: "u2", 5125: "u4", 5126: "f4"}[acc["componentType"]]
        ncomp = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4}[acc["type"]]
        count = int(acc["count"])
        stride = int(view.get("byteStride", 0)) or (np.dtype(ctype).itemsize * ncomp)
        raw = np.frombuffer(buffer, dtype=np.uint8)
        rows = []
        for i in range(count):
            seg = raw[start + i * stride:start + i * stride + np.dtype(ctype).itemsize * ncomp]
            rows.append(np.frombuffer(seg.tobytes(), dtype=ctype))
        return np.array(rows, dtype=np.float64)

    tris = []
    for mesh in json_doc.get("meshes", []):
        for prim in mesh.get("primitives", []):
            pos = read_acc(prim["attributes"]["POSITION"])
            if "indices" in prim:
                idx = read_acc(prim["indices"]).astype(int).reshape(-1)
                if len(idx) % 3:
                    continue
                tris.append(pos[idx.reshape(-1, 3)].reshape(-1, 3, 3))
            else:
                tris.append(pos.reshape(-1, 3, 3))
    if not tris:
        raise ValueError("GLB has no POSITION geometry")
    return np.concatenate(tris, axis=0)


def mesh_report(blob: bytes, *, envelope_mm: list | None = None,
                stem: dict | None = None, units: str = "mm",
                check_manifold: bool = True) -> dict:
    """Deterministic acceptance facts for any mesh (STL or GLB): dims,
    volume, manifold gaps, stem-lock gaps. Pure numbers — Jev judges on top.
    units: mm for STL/print, m for GLB display meshes. Manifold only gates
    print-bound geometry; display meshes are rarely watertight."""
    data = parse_glb(blob) if blob[:4] == b"glTF" else parse_stl(blob)
    if units == "m":
        data = data * 1000.0  # work in mm throughout
    gaps: list[str] = []
    dims = bbox(data)
    if envelope_mm:
        for got, maxv, ax in zip(dims, envelope_mm, "XYZ"):
            if got > maxv:
                gaps.append(f"{ax} {got}mm exceeds envelope {maxv}mm")
    mani = manifold_gaps(data) if check_manifold else []
    gaps += mani
    if stem:
        gaps += stem_gaps(data, stem)
    vol = volume_cm3(data) * (1e6 if units == "m" else 1.0)
    return {"dims_mm": dims, "volume_cm3": round(vol, 2), "tris": int(len(data)),
            "manifold_issues": len(mani), "gaps": gaps, "accepted": not gaps}
