#!/usr/bin/env python3
"""Factory normalize: unlock 3MF sources into plain STL masters.

    python3 scripts/factory/normalize_3mf.py [--redo]

REFERENCE EXTRACTION ONLY — not production normalization.

A .3mf is a ZIP. Inside there are two shapes in the wild:
  1. Bambu/Orca plate files: 3D/Objects/*.model — usually raw (binary or
     ASCII) STL bytes wearing a .model suffix. We sniff and rename.
  2. Spec 3D/3dmodel.model XML: <mesh><vertices>/<triangles>. We parse the
     vertex/triangle lists (namespace-aware) and emit binary STL.

What this converter DELIBERATELY does not resolve: build-plate assembly
(item transforms, per-object transforms, component nesting) and slicer
settings. Output can have right triangles but wrong scale/placement, so it
is for measuring interfaces and eyeballing geometry only. Production masters
go through the Orca/Blender path (open -> arrange -> export). Anything this
script cannot unlock prints as needs-slicer.

Reads loose data/3dprint/*.3mf plus data/3dprint/_ingest/*/<*.3mf>.
Writes data/3dprint/_ingest/<slug>/converted/*.stl.

Stdlib only: zipfile, xml.etree, struct.
"""

from __future__ import annotations

import argparse
import struct
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

# 3MF core spec default unit is millimeter; files may declare otherwise.
UNIT_TO_MM = {
    "millimeter": 1.0, "micron": 0.001, "centimeter": 10.0,
    "inch": 25.4, "foot": 304.8, "meter": 1000.0,
}

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


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def stl_from_3mf_xml(xml_bytes: bytes) -> tuple[bytes | None, dict]:
    """Parse a 3MF 3dmodel.model XML doc -> (binary STL or None, info).

    Units: the model tag's `unit` attribute scales vertices to mm
    (spec default millimeter). Info reports unit/scale/meshes so callers
    can distrust appropriately.
    """
    info: dict = {"unit": "millimeter", "scale": 1.0, "meshes": 0, "skipped_tris": 0}
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError:
        return None, info
    unit = (root.get("unit") or "millimeter").lower()
    scale = UNIT_TO_MM.get(unit, 1.0)
    info.update({"unit": unit, "scale": scale})
    facets: list[tuple] = []  # validated (pa, pb, pc) only — count written last
    for mesh in root.iter():
        if _local(mesh.tag) != "mesh":
            continue
        info["meshes"] += 1
        verts: list[tuple] = []
        for child in mesh:
            if _local(child.tag) == "vertices":
                for v in child:
                    try:
                        verts.append((float(v.get("x")) * scale,
                                      float(v.get("y")) * scale,
                                      float(v.get("z")) * scale))
                    except (TypeError, ValueError):
                        pass
        for child in mesh:
            if _local(child.tag) == "triangles":
                for t in child:
                    try:
                        a, b, c = int(t.get("v1")), int(t.get("v2")), int(t.get("v3"))
                        pa, pb, pc = verts[a], verts[b], verts[c]
                    except (TypeError, ValueError, IndexError):
                        info["skipped_tris"] += 1
                        continue
                    if len({pa, pb, pc}) < 3:
                        info["skipped_tris"] += 1
                        continue
                    facets.append((pa, pb, pc))
    if not facets:
        return None, info
    out = bytearray(b"factory-normalize".ljust(80, b"\0")[:80])
    out += struct.pack("<I", len(facets))  # final count AFTER validation
    for pa, pb, pc in facets:
        ux, uy, uz = pb[0] - pa[0], pb[1] - pa[1], pb[2] - pa[2]
        vx, vy, vz = pc[0] - pa[0], pc[1] - pa[1], pc[2] - pa[2]
        nx, ny, nz = uy * vz - uz * vy, uz * vx - ux * vz, ux * vy - uy * vx
        out += struct.pack("<3f", nx, ny, nz)
        out += struct.pack("<3f", *pa) + struct.pack("<3f", *pb) + struct.pack("<3f", *pc)
        out += struct.pack("<H", 0)
    return bytes(out), info


def normalize_one(threemf: Path, dest: Path, redo: bool = False,
                    prefix: str = "") -> list[str]:
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
            out_name = f"{prefix}{threemf.stem}--{Path(name).stem}.stl"
            target = dest / out_name
            if kind in ("binary", "ascii"):
                if redo or not target.exists():
                    target.write_bytes(raw if kind == "binary" else raw)
                written.append(out_name)
                continue
            if name.endswith(".model") and raw.lstrip().startswith(b"<"):
                stl, info = stl_from_3mf_xml(raw)
                if info.get("scale", 1.0) != 1.0 or info.get("skipped_tris"):
                    print(f"    note {threemf.name}:{Path(name).name} "
                          f"unit={info['unit']} skipped={info['skipped_tris']}")
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
            for f in sorted(slug_dir.rglob("*.3mf")):
                if "converted" in f.parts:
                    continue
                d = slug_dir / "converted"
                d.mkdir(parents=True, exist_ok=True)
                jobs.append((f, d))
    ok, stuck = 0, []
    seen: dict[tuple[str, str], int] = {}
    for f, d in jobs:
        # disambiguate same-stem 3mfs from archive subfolders (V1 vs V2)
        key = (str(d), f.stem)
        seen[key] = seen.get(key, 0) + 1
        tag = "" if seen[key] == 1 else f"{f.parent.name}-"
        got = normalize_one(f, d, redo=a.redo, prefix=tag)
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
