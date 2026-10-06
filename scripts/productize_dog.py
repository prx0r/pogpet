#!/usr/bin/env python3
"""Make product GLBs from the canonical dog mesh.

  keychain: dog @ 60mm + printed ring (hole 4.0mm, plastic only)
  croc_tag: dog @ 28mm + printed pin stem (back mount for Croc holes)
  ornament: dog @ 80mm as-is (loop already in mesh)

    blender --background --python scripts/productize_dog.py -- \
      --in data/uploads/chibi-figure-hook.glb --product keychain --out data/productimg/prod

0 Meshy credits. Blender 5.x (4.0 lacks the denoiser; geometry works anywhere).
"""
from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path


def parse_args(argv):
    p = argparse.ArgumentParser()
    p.add_argument("--in", dest="src", required=True)
    p.add_argument("--product", required=True, choices=["keychain", "croc_tag", "ornament"])
    p.add_argument("--out", dest="outdir", required=True)
    return p.parse_args(argv[argv.index("--") + 1:] if "--" in argv else [])


SPECS = {
    # height_mm: overall figure height; hardware dims in mm
    "ornament": {"height": 80.0, "hardware": None},
    "keychain": {"height": 60.0, "hardware": "ring", "ring_hole": 4.0, "ring_wire": 2.0},
    "croc_tag": {"height": 28.0, "hardware": "pin", "pin_dia": 4.2, "pin_len": 9.0},
}


def main() -> int:
    import bpy
    from mathutils import Vector
    args = parse_args(sys.argv)
    spec = SPECS[args.product]

    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=args.src)
    objs = [o for o in bpy.context.scene.objects if o.type == "MESH"]
    if not objs:
        print("no meshes imported")
        return 1
    # join into one body
    bpy.ops.object.select_all(action="DESELECT")
    for o in objs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]
    bpy.ops.object.join()
    body = bpy.context.active_object
    body.name = f"dog_{args.product}"

    # scale so bbox height == target (Blender units = metres here)
    bb = [body.matrix_world @ Vector(c) for c in body.bound_box]
    xs = [v.x for v in bb]; ys = [v.y for v in bb]; zs = [v.z for v in bb]
    h = max(ys) - min(ys) if (max(ys) - min(ys)) >= (max(zs) - min(zs)) else max(zs) - min(zs)
    target = spec["height"] / 1000.0
    s = target / h if h > 0 else 1.0
    body.scale = (body.scale.x * s, body.scale.y * s, body.scale.z * s)
    bpy.ops.object.transform_apply(scale=True)
    bb = [body.matrix_world @ Vector(c) for c in body.bound_box]
    xs = [v.x for v in bb]; ys = [v.y for v in bb]; zs = [v.z for v in bb]
    cx, top = (min(xs) + max(xs)) / 2, max(zs)
    print(f"scaled to {spec['height']}mm; top z={top*1000:.1f}mm")

    hw = spec["hardware"]
    if hw == "ring":
        hole_r = spec["ring_hole"] / 2 / 1000.0
        wire_r = spec["ring_wire"] / 2 / 1000.0
        major = hole_r + wire_r
        bpy.ops.mesh.primitive_torus_add(
            major_radius=major, minor_radius=wire_r,
            major_segments=48, minor_segments=16,
            location=(cx, (min(ys) + max(ys)) / 2, top + major - 0.002))
        ring = bpy.context.active_object
        ring.name = "keychain_ring"
    elif hw == "pin":
        # stem on the back (-Y), centred; Croc holes are ~5mm, stem slightly under
        r = spec["pin_dia"] / 2 / 1000.0
        length = spec["pin_len"] / 1000.0
        bpy.ops.mesh.primitive_cylinder_add(
            radius=r, depth=length, vertices=32,
            location=(cx, min(ys) - length / 2 + 0.002, (min(zs) + max(zs)) / 2),
            rotation=(math.radians(90), 0, 0))
        ring = bpy.context.active_object
        ring.name = "croc_pin"
        # stopper disc so it clicks into the shoe hole
        bpy.ops.mesh.primitive_cylinder_add(
            radius=r * 1.5, depth=0.0015, vertices=32,
            location=(cx, min(ys) - length + 0.001, (min(zs) + max(zs)) / 2),
            rotation=(math.radians(90), 0, 0))
        disc = bpy.context.active_object
        disc.name = "croc_stopper"
        bpy.ops.object.select_all(action="DESELECT")
        ring.select_set(True); disc.select_set(True)
        bpy.context.view_layer.objects.active = ring
        bpy.ops.object.join()
        ring = bpy.context.active_object
    else:
        ring = None

    if ring is not None:
        bpy.ops.object.select_all(action="DESELECT")
        body.select_set(True); ring.select_set(True)
        bpy.context.view_layer.objects.active = body
        mod = body.modifiers.new("hw", "BOOLEAN")
        mod.operation = "UNION"
        mod.solver = "EXACT"
        mod.object = ring
        bpy.ops.object.modifier_apply(modifier=mod.name)
        bpy.data.objects.remove(ring, do_unlink=True)

    # manifold check
    import bmesh
    bm = bmesh.new()
    bm.from_mesh(body.data)
    bad = [e for e in bm.edges if not e.is_manifold]
    print(f"manifold edges bad={len(bad)}")
    bm.free()

    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    stem = f"dog-{args.product}"
    g = outdir / f"{stem}.glb"
    bpy.ops.object.select_all(action="DESELECT")
    body.select_set(True)
    bpy.context.view_layer.objects.active = body
    bpy.ops.export_scene.gltf(filepath=str(g), export_format="GLB", use_selection=True)
    print(f"wrote {g} ({g.stat().st_size}b)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
