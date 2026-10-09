#!/usr/bin/env python3
"""Parametric seal generator (runs INSIDE blender headless).

Usage:
  blender -b --python scripts/parametric_seal.py -- \
    --text CHRIS --dia_mm 35 --out /tmp/seal.stl [--preview /tmp/seal.png]
35mm aluminium-seal pattern: disc + raised rim + extruded initials
(>=0.8mm per JLC emboss floor). Proves generative design from scratch;
pair with laser_text_ok() before manufacture.
"""
import argparse
import sys

import bpy


def parse():
    argv = sys.argv
    if "--" in argv:
        argv = sys.argv[argv.index("--") + 1:]
    ap = argparse.ArgumentParser()
    ap.add_argument("--text", default="C")
    ap.add_argument("--dia_mm", type=float, default=35.0)
    ap.add_argument("--out", required=True)
    ap.add_argument("--preview", default="")
    return ap.parse_args(argv)


def main():
    a = parse()
    bpy.ops.wm.read_factory_settings(use_empty=True)
    r = a.dia_mm / 1000.0 / 2
    bpy.ops.mesh.primitive_cylinder_add(radius=r, depth=0.003, location=(0, 0, 0.0015))
    bpy.ops.mesh.primitive_torus_add(major_radius=r * 0.88, minor_radius=0.0006,
                                     location=(0, 0, 0.003))
    bpy.ops.object.text_add(location=(0, 0, 0.003))
    t = bpy.context.object
    t.data.body = a.text[:10].upper()
    t.data.size = r * 0.9
    t.data.extrude = 0.0008
    t.data.align_x = "CENTER"
    t.data.align_y = "CENTER"
    try:
        fp = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
        t.data.font = bpy.data.fonts.load(fp)
    except Exception:
        pass
    bpy.ops.object.convert(target="MESH")
    sc = bpy.context.scene
    sc.render.engine = "BLENDER_WORKBENCH"
    sc.display.shading.light = "MATCAP"
    if a.preview:
        bpy.ops.object.camera_add(location=(0, -0.09, 0.07), rotation=(1.2, 0, 0))
        sc.camera = bpy.context.object
        sc.render.resolution_x = 800
        sc.render.resolution_y = 800
        sc.render.filepath = a.preview
        sc.render.image_settings.file_format = "PNG"
        bpy.ops.render.render(write_still=True)
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.wm.stl_export(filepath=a.out, export_selected_objects=True)
    print("SEAL DONE", a.out)


main()
