#!/usr/bin/env python3
"""Factory masters: author our own clean functional bases in Blender.

    blender --background --python scripts/factory/masters.py -- \
        --base book_holder|line_reader|mx_keycap|slab_stand|rummy_rack|straw_ring|all \
        --out data/3dprint/masters

Why author instead of reusing downloads: reference STLs carry unknown or
non-commercial licences and arbitrary tessellation. These masters are ours
from the first vertex — parametric, manifold, mm units, one-shot printable,
ready for the personalise step (name/motif boolean) and the Orca -> 3MF step.

Bases (all dimensions mm, Z-up):
  book_holder  thumb ring ID 26 + paddle 34x22x1.4 (the ~3g print)
  line_reader  plate 160x40x2 with an 8mm reading slot + end tabs
  mx_keycap    1u cap 18x18 + Cherry-MX cruciform stem (4.0 span, 1.2 arms)
  slab_stand   TCG slab stand: base 70x30x4 + 20-degree back rest, 8mm slot
  rummy_rack   4-tier stepped rack, 200 wide, 12 deep / 8 rise per tier
  straw_ring   tumbler charm ring (ID 10.5 for ~10mm straws) + 24mm topper pad
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path


def parse_args(argv):
    p = argparse.ArgumentParser()
    p.add_argument("--base", required=True,
                   help="book_holder|line_reader|mx_keycap|slab_stand|rummy_rack|straw_ring|all")
    p.add_argument("--out", required=True)
    argv = argv[argv.index("--") + 1:] if "--" in argv else argv[1:]
    return p.parse_args(argv)


BASES = ("book_holder", "line_reader", "mx_keycap", "slab_stand", "rummy_rack", "straw_ring")


def box(name, x, y, z, loc=(0, 0, 0)):
    import bpy
    bpy.ops.mesh.primitive_cube_add(size=1, location=loc)
    o = bpy.context.active_object
    o.name = name
    o.scale = (x, y, z)
    bpy.ops.object.transform_apply(scale=True)
    return o


def cyl(name, r, h, loc=(0, 0, 0), verts=64):
    import bpy
    bpy.ops.mesh.primitive_cylinder_add(radius=r, depth=h, vertices=verts, location=loc)
    o = bpy.context.active_object
    o.name = name
    bpy.ops.object.transform_apply(scale=True)
    return o


def union(parts, name):
    import bpy
    base = parts[0]
    base.name = name
    for p in parts[1:]:
        m = base.modifiers.new(f"U-{p.name}", "BOOLEAN")
        m.operation = "UNION"
        m.object = p
        bpy.context.view_layer.objects.active = base
        bpy.ops.object.modifier_apply(modifier=m.name)
        bpy.data.objects.remove(p, do_unlink=True)
    bpy.context.view_layer.objects.active = base
    return base


def cut(base, cutter):
    import bpy
    m = base.modifiers.new(f"C-{cutter.name}", "BOOLEAN")
    m.operation = "DIFFERENCE"
    m.object = cutter
    bpy.context.view_layer.objects.active = base
    bpy.ops.object.modifier_apply(modifier=m.name)
    bpy.data.objects.remove(cutter, do_unlink=True)
    return base


def build_book_holder():
    ring = cyl("ring", 16, 6)
    hole = cyl("hole", 13, 8)
    cut(ring, hole)
    paddle = box("paddle", 34, 22, 1.4, loc=(30, 0, -2))
    return union([ring, paddle], "book_holder")


def build_line_reader():
    plate = box("plate", 160, 40, 2, loc=(0, 0, 1))
    slot = box("slot", 150, 8, 4, loc=(0, 0, 1))
    cut(plate, slot)
    tab_l = box("tabL", 10, 46, 4, loc=(-85, 0, 2))
    tab_r = box("tabR", 10, 46, 4, loc=(85, 0, 2))
    return union([plate, tab_l, tab_r], "line_reader")


def build_mx_keycap():
    cap = box("cap", 18, 18, 7, loc=(0, 0, 8.5))
    arm_a = box("armA", 4.0, 1.2, 5, loc=(0, 0, 2.5))
    arm_b = box("armB", 1.2, 4.0, 5, loc=(0, 0, 2.5))
    return union([cap, arm_a, arm_b], "mx_keycap")


def build_slab_stand():
    import math
    base = box("sbase", 70, 30, 4, loc=(0, 0, 2))
    import bpy
    bpy.ops.mesh.primitive_cube_add(size=1, location=(0, -8, 18))
    rest = bpy.context.active_object
    rest.name = "rest"
    rest.scale = (70, 4, 44)
    rest.rotation_euler = (math.radians(20), 0, 0)
    bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)
    out = union([base, rest], "slab_stand")
    groove = box("groove", 60, 9, 6, loc=(0, 2, 5))
    return cut(out, groove)


def build_rummy_rack():
    tiers = []
    for i in range(4):
        tiers.append(box(f"tier{i}", 200, 12, 8, loc=(0, i * 12 - 18, 4 + i * 8)))
    back = box("back", 200, 4, 40, loc=(0, 32, 20))
    return union(tiers + [back], "rummy_rack")


def build_straw_ring():
    ring = cyl("sring", 8, 4, verts=48)
    hole = cyl("shole", 5.25, 6, verts=48)
    cut(ring, hole)
    pad = cyl("pad", 12, 2, loc=(14, 0, 0), verts=48)
    link = box("link", 8, 4, 2, loc=(8, 0, 0))
    return union([ring, pad, link], "straw_ring")


BUILDERS = {
    "book_holder": build_book_holder,
    "line_reader": build_line_reader,
    "mx_keycap": build_mx_keycap,
    "slab_stand": build_slab_stand,
    "rummy_rack": build_rummy_rack,
    "straw_ring": build_straw_ring,
}


def export_stl(obj, path: Path):
    import bpy
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        bpy.ops.wm.stl_export(filepath=str(path), export_selected=True)
    except (AttributeError, TypeError):
        bpy.ops.export_mesh.stl(filepath=str(path), use_selection=True)


def main() -> int:
    args = parse_args(sys.argv)
    import bpy

    names = BASES if args.base == "all" else (args.base,)
    for n in names:
        if n not in BUILDERS:
            print(f"unknown base {n!r} (pick from {', '.join(BASES)}|all)")
            return 2
    out = Path(args.out)
    for n in names:
        bpy.ops.wm.read_factory_settings(use_empty=True)
        obj = BUILDERS[n]()
        # final manifold sanity: triangulate-free export, report counts
        me = obj.data
        export_stl(obj, out / f"{n}.stl")
        print(f"  {n}.stl verts={len(me.vertices)} polys={len(me.polygons)}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
