#!/usr/bin/env python3
"""Factory personalise: emboss text onto a base via its adapter transform.

    blender --background --python scripts/factory/personalize.py -- \
        --adapter scripts/factory/adapters/line_reader.json --text MARGARET \
        --out /tmp/MARGARET-reader.stl

Every product adapter owns its transform (surface origin/normal/size in mm).
Text is auto-fit to the surface box by measured bounds — never by character
count — then UNION-booleaned into the base. Same base + same adapter, only
the string varies: the name changes, the manufacturing recipe doesn't.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"

# local +Z (text extrude axis) -> euler mapping for axis-aligned normals
EULER_FOR_NORMAL = {
    (0, 0, 1): (0, 0, 0),
    (0, 0, -1): (math.pi, 0, 0),
    (0, 1, 0): (-math.pi / 2, 0, 0),
    (0, -1, 0): (math.pi / 2, 0, 0),
    (1, 0, 0): (0, math.pi / 2, 0),
    (-1, 0, 0): (0, -math.pi / 2, 0),
}


def parse_args(argv):
    p = argparse.ArgumentParser()
    p.add_argument("--adapter", required=True, help="scripts/factory/adapters/<line>.json")
    p.add_argument("--text", required=True)
    p.add_argument("--out", required=True)
    argv = argv[argv.index("--") + 1:] if "--" in argv else argv[1:]
    return p.parse_args(argv)


def main() -> int:
    args = parse_args(sys.argv)
    import bpy

    ad = json.loads(Path(args.adapter).read_text())
    surf = ad["surface"]
    txspec = ad.get("text", {})
    normal = tuple(surf["normal"])
    if normal not in EULER_FOR_NORMAL:
        print(f"adapter normal {normal} is not axis-aligned — refusing")
        return 2
    max_chars = int(txspec.get("max_chars", 16))
    text = args.text[:max_chars]
    size = float(txspec.get("size_mm", 10))
    depth = float(txspec.get("depth_mm", 1.2))
    embed = float(surf.get("embed_mm", 0.4))

    here = Path(args.adapter).resolve()
    repo = here.parent.parent.parent.parent  # adapters/ -> factory/ -> scripts/ -> repo
    base_path = repo / "data" / "3dprint" / ad["base"]
    if not base_path.is_file():
        print(f"base missing: {base_path}")
        return 2
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.wm.stl_import(filepath=str(base_path))
    base = [o for o in bpy.context.scene.objects if o.type == "MESH"][0]
    base.name = "base"
    base.data = base.data.copy()  # single-user: boolean apply needs it

    bpy.ops.object.text_add(location=(0, 0, 0))
    tx = bpy.context.active_object
    tx.name = "name"
    tx.data.body = text
    if not text.strip():
        print("empty text — nothing to emboss")
        return 2
    tx.data.size = size
    tx.data.extrude = depth / 2.0
    tx.data.align_x = "CENTER"
    tx.data.align_y = "CENTER"
    try:
        tx.data.font = bpy.data.fonts.load(FONT)
    except (RuntimeError, OSError):
        pass  # Blender's built-in font
    tx.rotation_euler = EULER_FOR_NORMAL[normal]
    bpy.ops.object.convert(target="MESH")
    tx = bpy.context.active_object
    if len(tx.data.vertices) == 0:
        print(f"text {text!r} produced no geometry — refusing")
        return 2

    # center in mesh space (object location gets overwritten at placement,
    # so shifting the object here would be silently lost)
    xs = [v.co.x for v in tx.data.vertices]
    ys = [v.co.y for v in tx.data.vertices]
    cx, cy = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2
    for v in tx.data.vertices:
        v.co.x -= cx
        v.co.y -= cy
    tx.data.update()

    # auto-fit: shrink text to the surface box by measured bounds
    if txspec.get("auto_fit", True):
        xs = [v.co.x for v in tx.data.vertices]
        ys = [v.co.y for v in tx.data.vertices]
        bw, bh = max(xs) - min(xs), max(ys) - min(ys)
        if bw > 0 and bh > 0:
            s = min(surf["width_mm"] / bw, surf["height_mm"] / bh, 1.0)
            if s < 1.0:
                tx.scale = (s, s, 1.0)
                bpy.ops.object.transform_apply(scale=True)
                print(f"  auto-fit {text!r}: scale {s:.2f} to "
                      f"{surf['width_mm']}x{surf['height_mm']}mm box")

    # placement: XY from the adapter origin, Z from the MEASURED base top
    # along the face normal (adapter z values drifted from the masters and
    # buried text inside the part — silent no-op output).
    bxs = [v.co.x for v in base.data.vertices]
    bys = [v.co.y for v in base.data.vertices]
    bzs = [v.co.z for v in base.data.vertices]
    ox, oy, oz = surf["origin_mm"]
    nx, ny, nz = normal
    top = max(bzs) if nz > 0 else (min(bzs) if nz < 0 else oz)
    tx.location = (ox, oy, top - nz * embed * 0.5)
    print(f"  place: base z [{min(bzs):.2f},{max(bzs):.2f}] top={top:.2f} "
          f"-> text z {tx.location[2]:.2f} (adapter z was {oz})")

    base_verts = len(base.data.vertices)
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
        bpy.ops.wm.stl_export(filepath=str(out), export_selected_objects=True)
    except (AttributeError, TypeError):
        bpy.ops.export_mesh.stl(filepath=str(out), use_selection=True)
    me = base.data
    print(f"personalised: {text!r} on {ad['base']} verts={len(me.vertices)} "
          f"polys={len(me.polygons)} -> {out}")
    # never silently return the untouched master: the boolean must add geometry
    if len(me.vertices) <= base_verts:
        print(f"REFUSED: boolean added no geometry (base {base_verts} verts, "
              f"out {len(me.vertices)}) — text buried or missed the part")
        try:
            out.unlink(missing_ok=True)
        except TypeError:
            pass
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
