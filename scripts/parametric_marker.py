#!/usr/bin/env python3
"""Parametric golf ball marker (runs INSIDE blender headless).

Usage:
  blender -b --python scripts/parametric_marker.py -- \
    --text BUSTER --dia_mm 24 --out /tmp/marker.stl [--preview /tmp/marker.png]
24mm dia, 2mm thick per golf_marker contract, raised initials (>=0.8mm),
hat-clip notch. QC via brick_qc-style manifold audit on export.
"""
import argparse
import sys

import bmesh
import bpy
from mathutils import Vector


def parse():
    argv = sys.argv
    if "--" in argv:
        argv = sys.argv[argv.index("--") + 1:]
    ap = argparse.ArgumentParser()
    ap.add_argument("--text", default="B")
    ap.add_argument("--dia_mm", type=float, default=24.0)
    ap.add_argument("--out", required=True)
    ap.add_argument("--preview", default="")
    return ap.parse_args(argv)


def main():
    a = parse()
    bpy.ops.wm.read_factory_settings(use_empty=True)
    r = a.dia_mm / 1000.0 / 2
    bpy.ops.mesh.primitive_cylinder_add(radius=r, depth=0.002, location=(0, 0, 0.001))
    disc = bpy.context.object
    bpy.ops.mesh.primitive_torus_add(major_radius=r * 0.8, minor_radius=0.0006,
                                     location=(0, 0, 0.002))
    bpy.ops.object.text_add(location=(0, 0, 0.002))
    t = bpy.context.object
    t.data.body = a.text[:8].upper()
    t.data.size = r * 0.55
    t.data.extrude = 0.0008
    t.data.align_x = "CENTER"
    t.data.align_y = "CENTER"
    try:
        t.data.font = bpy.data.fonts.load("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf")
    except Exception:
        pass
    bpy.ops.object.convert(target="MESH")
    # hat-clip notch: small slot box subtracted via boolean
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=(0, r * 0.92, 0.001))
    notch = bpy.context.object
    notch.scale = (0.006, 0.003, 0.004)
    bpy.context.view_layer.update()
    bpy.ops.object.select_all(action="DESELECT")
    disc.select_set(True)
    bpy.context.view_layer.objects.active = disc
    mod = disc.modifiers.new("notch", "BOOLEAN")
    mod.operation = "DIFFERENCE"
    mod.object = notch
    bpy.ops.object.modifier_apply(modifier=mod.name)
    bpy.data.objects.remove(notch)
    me = disc.data
    bm = bmesh.new()
    bm.from_mesh(me)
    nm = sum(1 for e in bm.edges if not e.is_manifold)
    bm.free()
    ws = [disc.matrix_world @ v.co for v in me.vertices]
    dims = [round((max(v[i] for v in ws) - min(v[i] for v in ws)) * 1000, 1) for i in range(3)]
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.wm.stl_export(filepath=a.out, export_selected_objects=True)
    if a.preview:
        sc = bpy.context.scene
        sc.render.engine = "CYCLES"
        sc.cycles.samples = 48
        sc.cycles.use_denoising = True
        sc.cycles.device = "CPU"
        if sc.world is None:
            sc.world = bpy.data.worlds.new("World")
        sc.world.use_nodes = True
        sc.world.node_tree.nodes["Background"].inputs[0].default_value = (1, 1, 1, 1)
        sc.world.node_tree.nodes["Background"].inputs[1].default_value = 2.0
        bpy.ops.object.light_add(type="AREA", location=(0.05, -0.06, 0.08))
        key = bpy.context.object
        key.data.energy = 8
        key.data.size = 0.1
        bpy.ops.object.light_add(type="AREA", location=(-0.06, -0.02, 0.05))
        fill = bpy.context.object
        fill.data.energy = 3
        fill.data.size = 0.12
        bpy.ops.object.camera_add(location=(0, -0.055, 0.045))
        sc.camera = bpy.context.object
        sc.camera.data.clip_start = 0.001
        sc.camera.data.clip_end = 10.0
        tgt = sc.camera.constraints.new("TRACK_TO")
        empty = bpy.data.objects.new("focus", None)
        sc.collection.objects.link(empty)
        empty.location = (0, 0, 0.002)
        tgt.target = empty
        tgt.track_axis = "TRACK_NEGATIVE_Z"
        tgt.up_axis = "UP_Y"
        sc.render.resolution_x = 800
        sc.render.resolution_y = 800
        sc.render.filepath = a.preview
        sc.render.image_settings.file_format = "PNG"
        bpy.ops.render.render(write_still=True)
    print(f"MARKER DONE nonman={nm} dims={dims} {a.out}")


main()
