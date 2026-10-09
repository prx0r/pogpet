#!/usr/bin/env python3
"""Parametric Stone enclosure (runs INSIDE blender headless).

Usage:
  blender -b --python scripts/parametric_stone.py -- \
    --variant river --out /tmp/stone-river.stl [--preview /tmp/stone.png]
Variants: river (asymmetric lentil), worry (flatter + thumb hollow),
seed (tapered sculptural). 78x58x29mm envelope, common electronics
cavity (60x40x14mm), diffuser shell at 0.94 scale. STL + QC report.
"""
import argparse
import sys

import bmesh
import bpy


def parse():
    argv = sys.argv
    if "--" in argv:
        argv = sys.argv[argv.index("--") + 1:]
    ap = argparse.ArgumentParser()
    ap.add_argument("--variant", default="river", choices=["river", "worry", "seed"])
    ap.add_argument("--out", required=True)
    ap.add_argument("--preview", default="")
    return ap.parse_args(argv)


def main():
    a = parse()
    bpy.ops.wm.read_factory_settings(use_empty=True)
    # base lentil: sphere scaled to envelope
    bpy.ops.mesh.primitive_uv_sphere_add(segments=48, ring_count=24, radius=1.0)
    o = bpy.context.object
    o.scale = (0.039, 0.029, 0.0145)
    bpy.ops.object.transform_apply(scale=True)
    me = o.data
    # variant shaping on verts (x length, y width, z thick)
    for v in me.vertices:
        x, y, z = v.co
        nx, ny = x / 0.039, y / 0.029
        if a.variant in ("river", "seed"):
            # fuller left edge + tapered right end
            v.co.x += 0.004 * max(0.0, -nx) * (1 - abs(ny))
            v.co.x -= 0.006 * max(0.0, nx) * (1 - abs(ny)) * (1.5 if a.variant == "seed" else 1.0)
        if a.variant == "worry":
            v.co.z *= 0.82
            # thumb hollow top centre
            d = (nx ** 2 / 0.25 + ny ** 2 / 0.16)
            if d < 1.0 and z > 0:
                v.co.z -= 0.004 * (1.0 - d)
    bpy.context.view_layer.update()
    # electronics cavity: boolean box 60x40x14 centred low
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=(0, 0, -0.004))
    cav = bpy.context.object
    cav.scale = (0.06, 0.04, 0.014)
    bpy.ops.object.select_all(action="DESELECT")
    o.select_set(True)
    bpy.context.view_layer.objects.active = o
    mod = o.modifiers.new("cavity", "BOOLEAN")
    mod.operation = "DIFFERENCE"
    mod.object = cav
    bpy.ops.object.modifier_apply(modifier=mod.name)
    bpy.data.objects.remove(cav)
    # diffuser: inner copy at 0.94
    bpy.ops.object.select_all(action="DESELECT")
    o.select_set(True)
    bpy.ops.object.duplicate()
    diff = bpy.context.view_layer.objects.active
    diff.scale = (0.94, 0.94, 0.94)
    # audit shell
    bm = bmesh.new()
    bm.from_mesh(o.data)
    nm = sum(1 for e in bm.edges if not e.is_manifold)
    n = len(bm.verts)
    bm.free()
    ws = [o.matrix_world @ v.co for v in o.data.vertices]
    dims = [round((max(v[i] for v in ws) - min(v[i] for v in ws)) * 1000, 1) for i in range(3)]
    bpy.ops.object.select_all(action="DESELECT")
    o.select_set(True)
    diff.select_set(True)
    bpy.ops.wm.stl_export(filepath=a.out, export_selected_objects=True)
    if a.preview:
        sc = bpy.context.scene
        sc.render.engine = "BLENDER_WORKBENCH"
        sc.display.shading.light = "MATCAP"
        bpy.ops.object.camera_add(location=(0, -0.14, 0.07))
        sc.camera = bpy.context.object
        sc.camera.data.clip_start = 0.001
        tgt = sc.camera.constraints.new("TRACK_TO")
        empty = bpy.data.objects.new("f", None)
        sc.collection.objects.link(empty)
        tgt.target = empty
        tgt.track_axis = "TRACK_NEGATIVE_Z"
        tgt.up_axis = "UP_Y"
        sc.render.resolution_x = 800
        sc.render.resolution_y = 800
        sc.render.filepath = a.preview
        sc.render.image_settings.file_format = "PNG"
        bpy.ops.render.render(write_still=True)
    print(f"STONE DONE variant={a.variant} verts={n} nonman={nm} dims={dims} {a.out}")


main()
