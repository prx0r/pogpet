#!/usr/bin/env python3
"""Factory personalise: emboss a name/motif string onto a base master.

    blender --background --python scripts/factory/personalize.py -- \
        --base data/3dprint/masters/line_reader.stl --text MARGARET \
        --size 10 --depth 1.2 --loc 0,0 --out /tmp/MARGARET-reader.stl

Imports the base STL, builds a text object in a free system font, converts
to mesh, seats it embedded ~0.4mm into the top surface at (loc_x, loc_y),
UNION-booleans it into the base, exports one watertight-ish STL.

This is the "name changes, manufacturing recipe doesn't" step from the
thesis: same base + same placement rules, only the string varies.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"


def parse_args(argv):
    p = argparse.ArgumentParser()
    p.add_argument("--base", required=True)
    p.add_argument("--text", required=True)
    p.add_argument("--size", type=float, default=10.0, help="cap height mm")
    p.add_argument("--depth", type=float, default=1.2, help="emboss height mm")
    p.add_argument("--loc", default="0,0", help="x,y mm on the face")
    p.add_argument("--top", type=float, default=0.0,
                   help="surface z mm (0 = auto: bbox max)")
    p.add_argument("--out", required=True)
    argv = argv[argv.index("--") + 1:] if "--" in argv else argv[1:]
    return p.parse_args(argv)


def main() -> int:
    args = parse_args(sys.argv)
    import bpy

    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.wm.stl_import(filepath=args.base)
    base = [o for o in bpy.context.scene.objects if o.type == "MESH"][0]
    base.name = "base"
    base.data = base.data.copy()  # single-user: boolean apply needs it

    xs = [v.co.x for v in base.data.vertices]
    ys = [v.co.y for v in base.data.vertices]
    zs = [v.co.z for v in base.data.vertices]
    top = args.top or max(zs)
    lx, ly = (float(v) for v in args.loc.split(","))

    bpy.ops.object.text_add(location=(0, 0, 0))
    tx = bpy.context.active_object
    tx.name = "name"
    tx.data.body = args.text[:16]
    tx.data.size = args.size
    tx.data.extrude = args.depth / 2.0
    tx.data.align_x = "CENTER"
    tx.data.align_y = "CENTER"
    try:
        f = bpy.data.fonts.load(FONT)
        tx.data.font = f
    except (RuntimeError, OSError):
        pass  # fall back to Blender's built-in font
    bpy.ops.object.convert(target="MESH")
    tx = bpy.context.active_object
    # seat: text local z=0 plane at (top - 0.4) so it embeds into the face
    tx.location = (lx, ly, top - 0.4)

    m = base.modifiers.new("NAME", "BOOLEAN")
    m.operation = "UNION"
    m.object = tx
    bpy.context.view_layer.objects.active = base
    bpy.ops.object.modifier_apply(modifier=m.name)
    bpy.data.objects.remove(tx, do_unlink=True)

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.object.select_all(action="DESELECT")
    base.select_set(True)
    bpy.context.view_layer.objects.active = base
    try:
        bpy.ops.wm.stl_export(filepath=str(out), export_selected=True)
    except (AttributeError, TypeError):
        bpy.ops.export_mesh.stl(filepath=str(out), use_selection=True)
    me = base.data
    print(f"personalised: {args.text!r} on {Path(args.base).name} "
          f"verts={len(me.vertices)} polys={len(me.polygons)} -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
