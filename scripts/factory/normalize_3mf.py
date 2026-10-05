#!/usr/bin/env python3
"""Factory normalize: unlock 3MF sources into plain STL masters.

    python3 scripts/factory/normalize_3mf.py [--redo]

A .3mf is a ZIP. Inside there are two shapes in the wild:
  1. Bambu/Orca plate files: 3D/Objects/*.model — usually raw (binary or
     ASCII) STL bytes wearing a .model suffix. We sniff and rename.
  2. Spec 3D/3dmodel.model XML: <mesh><vertices>/<triangles>. We parse the
     vertex/triangle lists (namespace-aware) and emit binary STL.

Reads loose data/3dprint/*.3mf plus data/3dprint/_ingest/*/<*.3mf>.
Writes data/3dprint/_ingest/<slug>/converted/*.stl.
Anything still locked prints as needs-slicer (open in Orca -> export STL).

Stdlib only: zipfile, xml.etree, struct.
"""
from __future__ import annotations

import argparse
import struct
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parent.parent.parent
SRC = ROOT / "data" / "3dprint"
INGEST = SRC / "_ingest"


def looks_like_stl(raw: bytes) -> str | None:
    """'binary' | 'ascii' | None for a blob that may be STL bytes."""
    if not raw:
        return None
    head = raw[:6].lower()
    if head.startswith(b"solid") and b"\n" in raw[:200] and len(raw) > 84:
        # ASCII STL starts with 'solid' and is text; binary may too, so check
        try:
            raw[:500].decode("ascii")
            if b"facet" in raw[:500].lower():
                return "ascii"
        except UnicodeDecodeError:
            pass
    if len(raw) >= 84:
        (n,) = struct.unpack("<I", raw[80:84])
        if n > 0 and len(raw) == 84 + 50 * n:
            return "binary"
    return None


def stl_from_3mf_xml(xml_bytes: bytes) -> bytes | None:
    """Parse a 3MF 3dmodel.model XML doc -> binary STL, or None."""
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError:
        return None
    ns = {"m": "http://schemas.microsoft.com/3dmanufacturing/core/2015/02"}
    meshes = root.findall(".//m:mesh", ns) or root.findall(".//{*}mesh")
    tris: list[tuple] = []
    for mesh in meshes:
        verts = []
        for v in list(mesh.find("{*}vertices") or []) if mesh.find("{*}vertices") is not None else []:
            try:
                verts.append((float(v.get("x")), float(v.get("y")), float(v.get("z"))))
            except (TypeError, ValueError):
                pass
        # namespace-safe fallback: iterate children by local tag
        if not verts:
            for child in mesh:
                if child.tag.endswith("vertices"):
                    for v in child:
                        try:
                            verts.append((float(v.get("x")), float(v.get("y")), float(v.get("z"))))
                        except (TypeError, ValueError):
                            pass
                if child.tag.endswith("triangles"):
                    for t in child:
                        try:
                            tris.append((int(t.get("v1")), int(t.get("v2")), int(t.get("v3")), verts))
                        except (TypeError, ValueError):
                            pass
            continue
        for child in mesh:
            if child.tag.endswith("triangles"):
                for t in child:
                    try:
                        tris.append((int(t.get("v1")), int(t.get("v2")), int(t.get("v3")), verts))
                    except (TypeError, ValueError):
                        pass
    if not tris:
        return None
    out = bytearray(b"factory-normalize" .ljust(80, b"\0")[:80])
    # count first: flatten per-mesh verts (indices are per-mesh in 3MF)
    count = len(tris)
    out += struct.pack("<I", count)
    for a, b, c, verts in tris:
        try:
            pa, pb, pc = verts[a], verts[b], verts[c]
        except IndexError:
            continue
        ux, uy, uz = pb[0] - pa[0], pb[1] - pa[1], pb[2] - pa[2]
        vx, vy, vz = pc[0] - pa[0], pc[1] - pa[1], pc[2] - pa[2]
        nx, ny, nz = uy * vz - uz * vy, uz * vx - ux * vz, ux * vy - uy * vx
        out += struct.pack("<3f", nx, ny, nz)
        out += struct.pack("<3f", *pa) + struct.pack("<3f", *pb) + struct.pack("<3f", *pc)
        out += struct.pack("<H", 0)
    return bytes(out)


def normalize_one(threemf: Path, dest: Path, redo: bool = False) -> list[str]:
    """Extract STL(s) from one .3mf into dest/. Returns written filenames."""
    written: list[str] = []
    try:
        z = zipfile.ZipFile(threemf)
    except zipfile.BadZipFile:
        return [f"BADZIP:{threemf.name}"]
    with z:
        for name in z.namelist():
            if name.endswith("/"):
                continue
            raw = z.read(name)
            kind = looks_like_stl(raw)
            out_name = f"{threemf.stem}--{Path(name).stem}.stl"
            target = dest / out_name
            if kind in ("binary", "ascii"):
                if redo or not target.exists():
                    target.write_bytes(raw if kind == "binary" else raw)
                written.append(out_name)
                continue
            if name.endswith(".model") and raw.lstrip().startswith(b"<"):
                stl = stl_from_3mf_xml(raw)
                if stl and len(stl) > 84:
                    if redo or not target.exists():
                        target.write_bytes(stl)
                    written.append(out_name)
    return written


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--redo", action="store_true")
    a = ap.parse_args()
    jobs: list[tuple[Path, Path]] = []
    for f in sorted(SRC.glob("*.3mf")):
        d = INGEST / "loose-3mf" / "converted"
        d.mkdir(parents=True, exist_ok=True)
        jobs.append((f, d))
    if INGEST.exists():
        for slug_dir in sorted(INGEST.iterdir()):
            if not slug_dir.is_dir():
                continue
            for f in sorted(slug_dir.glob("*.3mf")):
                d = slug_dir / "converted"
                d.mkdir(parents=True, exist_ok=True)
                jobs.append((f, d))
    ok, stuck = 0, []
    for f, d in jobs:
        got = normalize_one(f, d, redo=a.redo)
        if got and not got[0].startswith("BADZIP"):
            ok += len(got)
            print(f"  {f.name} -> {len(got)} stl")
        else:
            stuck.append(f.name)
    print(f"{ok} STL extracted from {len(jobs)} 3mf sources")
    if stuck:
        print("needs-slicer (open in Orca -> export STL):", ", ".join(stuck))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
