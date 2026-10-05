# Provenance: copied from /home/ubuntu/petsy/engine/mesh_export.py (prx0r/bwick),
# read-only there. GLB -> OBJ/STL + the loader render3d.py shares.
#!/usr/bin/env python3
"""GLB -> print files (OBJ + STL). Pure Python, offline, no Blender.

Makr3D accepts STL/3MF/STEP/OBJ/ZIP, so an OBJ straight out of this file is a
quotable print file. That removes Blender from the print path entirely — it is
only still needed for USDZ (iOS AR) and turntable frames.

What we do:
  * parse the GLB container (JSON chunk + BIN chunk)
  * walk the scene graph and bake each node's transform into world space
  * write OBJ (positions/normals/uvs/materials) and binary STL (triangles)
  * optionally scale to a target print height in mm (glTF units are metres)

What we deliberately do not do:
  * skinning/animation — we export the bind pose, which is the pose you print
  * subdivision or repair — a mesh that will not slice fails at the slicer,
    not here; `postmesh.py` is where print-readiness is decided

Usage:
  python3 mesh_export.py mesh.glb --obj out.obj --stl out.stl --height-mm 70
"""
from __future__ import annotations

import argparse
import json
import struct
import sys
from pathlib import Path

import numpy as np

GLB_MAGIC = b"glTF"
COMPONENT = {5120: ("b", 1), 5121: ("B", 1), 5122: ("h", 2),
             5123: ("H", 2), 5125: ("I", 4), 5126: ("f", 4)}
TYPE_COUNT = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4,
              "MAT4": 16}


class MeshError(ValueError):
    """The GLB is not usable as a print file."""


# ------------------------------------------------------------------ parsing ---

def load_glb(path: Path | str) -> tuple[dict, bytes]:
    data = Path(path).read_bytes()
    if len(data) < 20 or data[:4] != GLB_MAGIC:
        raise MeshError(f"{path} is not a GLB (bad magic)")
    version = struct.unpack("<I", data[4:8])[0]
    if version != 2:
        raise MeshError(f"GLB version {version}, this reader handles 2")
    declared = struct.unpack("<I", data[8:12])[0]
    if declared != len(data):
        raise MeshError(f"header says {declared} bytes, file is {len(data)}")

    chunk_len, chunk_type = struct.unpack("<I4s", data[12:20])
    if chunk_type != b"JSON":
        raise MeshError("first chunk is not JSON")
    doc = json.loads(data[20:20 + chunk_len].decode("utf-8"))

    bin_chunk = b""
    start = 20 + chunk_len
    if start + 8 <= len(data):
        blen, btype = struct.unpack("<I4s", data[start:start + 8])
        if btype == b"BIN\x00":
            bin_chunk = data[start + 8:start + 8 + blen]
    return doc, bin_chunk


def _accessor(doc: dict, bin_chunk: bytes, index: int) -> np.ndarray:
    acc = doc["accessors"][index]
    if "bufferView" not in acc:                     # sparse / zero-filled
        n = acc["count"] * TYPE_COUNT[acc["type"]]
        return np.zeros(n, dtype=np.float32)
    view = doc["bufferViews"][acc["bufferView"]]
    fmt, size = COMPONENT[acc["componentType"]]
    ncomp = TYPE_COUNT[acc["type"]]
    stride = view.get("byteStride") or size * ncomp
    offset = view.get("byteOffset", 0) + acc.get("byteOffset", 0)

    raw = bin_chunk[offset:offset + stride * acc["count"]]
    if len(raw) < stride * acc["count"]:
        raise MeshError(f"accessor {index} overruns the BIN chunk")
    if stride == size * ncomp:                       # tightly packed: one slice
        arr = np.frombuffer(raw, dtype=np.dtype("<" + fmt),
                            count=acc["count"] * ncomp)
    else:                                            # strided: walk it
        arr = np.array([struct.unpack_from("<" + fmt * ncomp, raw, i * stride)
                        for i in range(acc["count"])])
        arr = arr.reshape(-1)
    if fmt == "f":
        return arr.astype(np.float32)
    return arr.astype(np.int64)


def _matrix(node: dict) -> np.ndarray:
    if "matrix" in node:
        return np.array(node["matrix"], dtype=np.float64).reshape(4, 4).T
    t = node.get("translation", [0, 0, 0])
    r = node.get("rotation", [0, 0, 0, 1])          # x, y, z, w
    s = node.get("scale", [1, 1, 1])
    x, y, z, w = r
    rot = np.array([
        [1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
        [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
        [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)],
    ], dtype=np.float64)
    m = np.eye(4)
    m[:3, :3] = rot * np.array(s, dtype=np.float64)
    m[:3, 3] = t
    return m


def node_world_matrices(doc: dict) -> dict[int, np.ndarray]:
    """node index -> world matrix, walked from the SCENE roots.

    Walking from scene roots (not from leaves) is what makes composed
    transforms work: a merged GLB puts every character under a role node, and
    a leaf-first walk never sees that role's translation. It also means nodes
    that exist in the file but are not in the scene are correctly not drawn.
    """
    nodes = doc.get("nodes", [])
    scenes = doc.get("scenes", [])
    if scenes:
        scene = scenes[doc.get("scene", 0)] if doc.get("scene", 0) < len(scenes) else scenes[0]
        roots = list(scene.get("nodes", []))
    else:
        roots = list(range(len(nodes)))
    if not roots:
        raise MeshError("GLB has no scene roots")

    out: dict[int, np.ndarray] = {}

    def walk(i: int, base: np.ndarray, seen: frozenset) -> None:
        if i in seen or i >= len(nodes):
            raise MeshError("cycle or dangling child in the node graph")
        m = base @ _matrix(nodes[i])
        out[i] = m
        for k in nodes[i].get("children", []):
            walk(k, m, seen | {i})

    for r in roots:
        walk(r, np.eye(4), frozenset())
    return out


def _triangles(doc: dict, bin_chunk: bytes, prim: dict) -> tuple[np.ndarray, ...]:
    attrs = prim.get("attributes", {})
    if "POSITION" not in attrs:
        raise MeshError("primitive has no POSITION")
    pos = _accessor(doc, bin_chunk, attrs["POSITION"]).reshape(-1, 3)
    if "indices" in prim:
        idx = _accessor(doc, bin_chunk, prim["indices"]).reshape(-1)
    else:
        idx = np.arange(len(pos), dtype=np.int64)
    if idx.max(initial=-1) >= len(pos):
        raise MeshError("indices reference vertices that do not exist")
    nrm = ( _accessor(doc, bin_chunk, attrs["NORMAL"]).reshape(-1, 3)
            if "NORMAL" in attrs else None)
    uv = ( _accessor(doc, bin_chunk, attrs["TEXCOORD_0"]).reshape(-1, 2)
           if "TEXCOORD_0" in attrs else None)
    return pos, idx.astype(np.int64), nrm, uv


def collect(doc: dict, bin_chunk: bytes) -> dict:
    """All triangles in world space: {positions, normals, uvs, material ids}."""
    worlds = node_world_matrices(doc)
    mats = doc.get("materials", [])
    P: list[np.ndarray] = []
    N: list[np.ndarray] = []
    UV: list[np.ndarray] = []
    M: list[np.ndarray] = []
    n_tri = 0

    # A file can mix textured and untextured parts (a merged character plus a
    # plain effect sphere, say). If ANY part has UVs we emit UVs for all of
    # them — zeros where there are none — so the per-triangle reshape stays
    # rectangular. If none do, we emit no UV array at all.
    has_uv = any(
        "TEXCOORD_0" in prim.get("attributes", {})
        for i, node in enumerate(doc.get("nodes", []))
        if "mesh" in node and i in worlds
        for prim in doc["meshes"][node["mesh"]].get("primitives", [])
    )

    for i, node in enumerate(doc.get("nodes", [])):
        if "mesh" not in node:
            continue
        if i not in worlds:
            # not reachable from the scene root: glTF says it does not render
            continue
        m = worlds[i]
        nm = np.linalg.inv(m).T[:3, :3]             # normal matrix
        for prim in doc["meshes"][node["mesh"]].get("primitives", []):
            if prim.get("mode", 4) != 4:
                raise MeshError(f"primitive mode {prim.get('mode')} is not TRIANGLES")
            pos, idx, nrm, uv = _triangles(doc, bin_chunk, prim)
            wp = (np.c_[pos, np.ones(len(pos))] @ m.T)[:, :3]
            wn = nrm @ nm if nrm is not None else None
            if wn is not None:                       # re-normalise after transform
                lens = np.linalg.norm(wn, axis=1, keepdims=True)
                wn = wn / np.where(lens == 0, 1, lens)
            n_tri += len(idx) // 3
            # primitive index != material index: a mesh may reuse materials,
            # and a merged file has many. Using `pi` painted every part with
            # whatever material 0 happened to be.
            mat_id = int(prim.get("material", 0) or 0)
            P.append(wp[idx]); M.append(np.full(len(idx) // 3, mat_id))
            if wn is not None:
                N.append(wn[idx])
            if uv is not None:
                UV.append(uv[idx])
            elif has_uv:
                UV.append(np.zeros((len(idx), 2), dtype=np.float32))
            if wn is None:
                # No NORMAL attribute: derive one flat normal per triangle and
                # write it out for all three corners so OBJ/STL both carry it.
                tri = wp[idx].reshape(-1, 3, 3)
                fn = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0])
                lens = np.linalg.norm(fn, axis=1, keepdims=True)
                fn = fn / np.where(lens == 0, 1, lens)
                N.append(np.repeat(fn, 3, axis=0))
    if not P:
        raise MeshError("GLB contains no triangles")
    return {"positions": np.vstack(P), "triangles": n_tri,
            "normals": np.vstack(N) if N else None,
            "uv": np.vstack(UV) if UV else None,
            "material_per_tri": np.concatenate(M),
            "materials": mats}


# ----------------------------------------------------------------- measure ---

def measure(glb: Path | str) -> dict:
    """Bounding box in model units (glTF says metres) -> mm, plus tri count."""
    doc, bin_chunk = load_glb(glb)
    geo = collect(doc, bin_chunk)
    p = geo["positions"]
    lo, hi = p.min(axis=0), p.max(axis=0)
    size = hi - lo
    return {
        "triangles": int(geo["triangles"]),
        "bbox_min": [round(float(v), 5) for v in lo],
        "bbox_max": [round(float(v), 5) for v in hi],
        "size_units": [round(float(v), 5) for v in size],
        "height_mm": round(float(size[1]) * 1000, 1),
        "width_mm": round(float(size[0]) * 1000, 1),
        "depth_mm": round(float(size[2]) * 1000, 1),
        "unit": "metres (glTF spec) -> mm by x1000",
    }


# ------------------------------------------------------------------ export ---

def _scale_for(geo: dict, height_mm: float | None) -> float:
    if not height_mm:
        return 1.0
    p = geo["positions"]
    h = float(p[:, 1].max() - p[:, 1].min())
    if h <= 0:
        raise MeshError("model has zero height; cannot scale to a print size")
    k = (height_mm / 1000.0) / h
    # A model whose vertices are garbage produces a scale like 1e39. Shipping
    # that to a printer is a very expensive way to find out.
    if not (1e-6 <= k <= 1e6):
        raise MeshError(
            f"implausible scale {k:.3g} for height {h:.3g} units -- the mesh "
            "coordinates do not look like metres"
        )
    return k


def export_obj(glb: Path | str, out: Path | str, height_mm: float | None = None) -> dict:
    doc, bin_chunk = load_glb(glb)
    geo = collect(doc, bin_chunk)
    k = _scale_for(geo, height_mm)

    pos = geo["positions"] * k
    nrm = geo["normals"]
    uv = geo["uv"]
    mids = geo["material_per_tri"]

    lines = ["# exported by mesh_export.py from " + str(Path(glb).name),
             f"# triangles {geo['triangles']}  scale x{k:.6f}"]
    for v in pos:
        lines.append(f"v {v[0]:.6f} {v[1]:.6f} {v[2]:.6f}")
    if nrm is not None:
        for v in nrm:
            lines.append(f"vn {v[0]:.6f} {v[1]:.6f} {v[2]:.6f}")
    if uv is not None:
        for v in uv:
            lines.append(f"vt {v[0]:.6f} {v[1]:.6f}")

    mats = geo["materials"]
    for i, m in enumerate(mats):
        name = _safe(m.get("name", f"material{i}"))
        lines.append(f"usemtl {name}")
        lines.append(f"o {name}")
        for t in np.where(mids == i)[0]:
            lines.append(_face(t, has_n=nrm is not None, has_uv=uv is not None))
    if not mats:
        lines.append("o mesh")
        for t in range(geo["triangles"]):
            lines.append(_face(t, has_n=nrm is not None, has_uv=uv is not None))

    Path(out).parent.mkdir(parents=True, exist_ok=True)
    Path(out).write_text("\n".join(lines) + "\n")
    return {"obj": str(out), "triangles": geo["triangles"],
            "scale": round(k, 6), "bytes": Path(out).stat().st_size}


def _face(t: int, has_n: bool, has_uv: bool) -> str:
    a, b, c = t * 3 + 1, t * 3 + 2, t * 3 + 3
    if has_uv and has_n:
        return f"f {a}/{a}/{a} {b}/{b}/{b} {c}/{c}/{c}"
    if has_uv:
        return f"f {a}/{a} {b}/{b} {c}/{c}"
    if has_n:
        return f"f {a}//{a} {b}//{b} {c}//{c}"
    return f"f {a} {b} {c}"


def _safe(name: str) -> str:
    return "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in name)[:60] or "m"


def export_stl(glb: Path | str, out: Path | str, height_mm: float | None = None) -> dict:
    """Binary STL: 80-byte header, uint32 count, 50 bytes per triangle."""
    doc, bin_chunk = load_glb(glb)
    geo = collect(doc, bin_chunk)
    k = _scale_for(geo, height_mm)

    # positions are stored 3 rows per triangle -> (tri, 3 corners, xyz)
    tri = (geo["positions"] * k).reshape(-1, 3, 3)
    if len(tri) != geo["triangles"]:
        raise MeshError("triangle count does not match the vertex stream")
    # STL carries one unit normal per facet, derived from the winding
    fn = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0])
    lens = np.linalg.norm(fn, axis=1, keepdims=True)
    fn = fn / np.where(lens == 0, 1, lens)

    header = f"mesh_export.py {Path(glb).name} tris={geo['triangles']}".encode()[:80]
    header = header.ljust(80, b"\0")
    buf = bytearray(header)
    buf += struct.pack("<I", int(geo["triangles"]))
    for i in range(geo["triangles"]):
        buf += struct.pack("<3f", *fn[i])
        buf += struct.pack("<3f", *tri[i][0])
        buf += struct.pack("<3f", *tri[i][1])
        buf += struct.pack("<3f", *tri[i][2])
        buf += struct.pack("<H", 0)
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    Path(out).write_bytes(bytes(buf))
    return {"stl": str(out), "triangles": geo["triangles"],
            "scale": round(k, 6), "bytes": Path(out).stat().st_size}


def export_print_bundle(glb: Path | str, outdir: Path | str,
                        height_mm: float | None = None) -> dict:
    """The physical body: OBJ + STL + manifest from one GLB.

    Split happens upstream (performance vs print variants); this is the
    print half only. Watertight repair runs before this (Meshy repair API),
    never after — a mesh that will not slice fails at the slicer, not here.
    """
    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    stem = Path(glb).stem
    obj = export_obj(glb, outdir / f"{stem}.obj", height_mm)
    stl = export_stl(glb, outdir / f"{stem}.stl", height_mm)
    manifest = {
        "source": str(glb), "height_mm": height_mm,
        "triangles": obj["triangles"], "scale": obj["scale"],
        "files": {"obj": obj["obj"], "stl": stl["stl"]},
        "print_ready": True,
    }
    (outdir / f"{stem}.print.json").write_text(json.dumps(manifest, indent=2))
    manifest["manifest"] = str(outdir / f"{stem}.print.json")
    return manifest


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("glb")
    ap.add_argument("--obj")
    ap.add_argument("--stl")
    ap.add_argument("--height-mm", type=float, default=None,
                    help="scale the export to this printed height")
    a = ap.parse_args(argv)
    try:
        if not (a.obj or a.stl):
            print(json.dumps(measure(a.glb), indent=2))
            return 0
        if a.obj:
            print(json.dumps(export_obj(a.glb, a.obj, a.height_mm), indent=2))
        if a.stl:
            print(json.dumps(export_stl(a.glb, a.stl, a.height_mm), indent=2))
    except MeshError as e:
        print(f"BLOCKED: {e}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
