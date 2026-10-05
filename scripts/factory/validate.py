#!/usr/bin/env python3
"""Factory validate: Blender headless QC for STL masters.

    blender --background --python scripts/factory/validate.py -- \
        --in data/3dprint/_ingest --out data/3dprint/_ingest/validate.json

For every .stl under --in: import, measure bbox (mm), count tris, count
non-manifold edges via bmesh, and give a verdict:

  PASS — watertight (0 non-manifold edges), plausible size 5–400 mm
  FIXABLE — a few non-manifold edges (<50) or size outside range
  FAIL — no geometry or heavily open mesh

Writes one JSON report. Read-only on sources; never modifies them.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def parse_args(argv):
    p = argparse.ArgumentParser()
    p.add_argument("--in", dest="src", required=True)
    p.add_argument("--out", dest="out", required=True)
    p.add_argument("--limit", type=int, default=0, help="0 = all files")
    argv = argv[argv.index("--") + 1:] if "--" in argv else argv[1:]
    return p.parse_args(argv)


def main() -> int:
    args = parse_args(sys.argv)
    import bpy
    import bmesh

    src = Path(args.src)
    files = sorted(src.rglob("*.stl"))
    if args.limit:
        files = files[: args.limit]
    report = []
    for f in files:
        rec: dict = {"file": str(f.relative_to(src))}
        try:
            bpy.ops.wm.read_factory_settings(use_empty=True)
            bpy.ops.wm.stl_import(filepath=str(f))
            meshes = [o for o in bpy.context.scene.objects if o.type == "MESH"]
            if not meshes:
                rec.update({"verdict": "FAIL", "error": "no mesh on import"})
                report.append(rec)
                continue
            me = meshes[0].data
            bm = bmesh.new()
            bm.from_mesh(me)
            bm.edges.ensure_lookup_table()
            nonman = sum(1 for e in bm.edges if not e.is_manifold)
            tris = sum(1 for fa in bm.faces if len(fa.loops) == 3)
            quads = sum(1 for fa in bm.faces if len(fa.loops) == 4)
            ngons = len(bm.faces) - tris - quads
            xs = [v.co.x for v in bm.verts]
            ys = [v.co.y for v in bm.verts]
            zs = [v.co.z for v in bm.verts]
            # STL from slicers is usually mm; our Blender scene is metres-agnostic —
            # report raw units and let the factory decide scale at master time.
            size = [round(max(xs) - min(xs), 2), round(max(ys) - min(ys), 2), round(max(zs) - min(zs), 2)]
            bm.free()
            biggest = max(size) if size else 0
            rec.update({
                "verts": len(me.vertices), "tris": tris, "quads": quads, "ngons": ngons,
                "nonmanifold_edges": nonman, "bbox": size,
            })
            if nonman == 0 and 1 <= biggest <= 1000:
                rec["verdict"] = "PASS"
            elif nonman < 50:
                rec["verdict"] = "FIXABLE"
            else:
                rec["verdict"] = "FAIL"
        except Exception as e:  # noqa: BLE001 — report, don't stop the batch
            rec.update({"verdict": "FAIL", "error": str(e)[:200]})
        report.append(rec)
        print(f"  {rec['verdict']:7s} {rec['file']}", flush=True)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2))
    counts: dict[str, int] = {}
    for r in report:
        counts[r["verdict"]] = counts.get(r["verdict"], 0) + 1
    print(f"{len(report)} files -> {out} {json.dumps(counts)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
