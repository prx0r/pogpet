#!/usr/bin/env python3
"""Factory stills: white-studio product photos for ANY mesh (STL or GLB).

    blender --background --python scripts/factory/stills.py -- \\
        --in data/3dprint/masters/line_reader.stl \\
        --out /tmp/stills/line_reader --size 768 --samples 32

Imports, centers, normalizes to a 0.2-unit stage, applies the proven white
recipe (AgX Punchy, dimmed 7-light rig, transparent film), shoots
hero/front/side/back as RGBA PNGs. A finish step composites onto pure white:

    python3 scripts/factory/stills_finish.py /tmp/stills/line_reader \\
        --line line_reader --dest data/productimg/prod

Output names <line>-{hero,front,side,back}.png — exactly what
_studio_stills_for() picks up once it tries the "{line}-" prefix first.
Untextured STLs get a neutral warm-grey PLA material; GLBs keep theirs.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path


def parse_args(argv):
    p = argparse.ArgumentParser()
    p.add_argument("--in", dest="src", required=True)
    p.add_argument("--out", dest="outdir", required=True)
    p.add_argument("--size", type=int, default=768)
    p.add_argument("--samples", type=int, default=32)
    argv = argv[argv.index("--") + 1:] if "--" in argv else argv[1:]
    return p.parse_args(argv)


def main() -> int:
    args = parse_args(sys.argv)
    import bpy
    from mathutils import Vector

    src = Path(args.src)
    out = Path(args.outdir)
    out.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.read_factory_settings(use_empty=True)

    if src.suffix.lower() == ".stl":
        bpy.ops.wm.stl_import(filepath=str(src))
    elif src.suffix.lower() in (".glb", ".gltf"):
        try:
            bpy.ops.import_scene.gltf(filepath=str(src))
        except (AttributeError, TypeError):
            bpy.ops.wm.gltf_import(filepath=str(src))
    else:
        print(f"unsupported {src.suffix}")
        return 2
    objs = [o for o in bpy.context.scene.objects if o.type == "MESH"]
    if not objs:
        print("no mesh on import")
        return 2

    # normalize: center horizontally, rest on z=0, max dim -> 0.2
    bpy.ops.object.select_all(action="SELECT")
    bpy.context.view_layer.objects.active = objs[0]
    bpy.ops.object.join()
    body = bpy.context.active_object
    body.data = body.data.copy()
    xs = [v.co.x for v in body.data.vertices]
    ys = [v.co.y for v in body.data.vertices]
    zs = [v.co.z for v in body.data.vertices]
    cx, cy, zmn = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2, min(zs)
    maxd = max(max(xs) - min(xs), max(ys) - min(ys), max(zs) - min(zs)) or 1.0
    k = 0.2 / maxd
    body.location = (-cx * k, -cy * k, -zmn * k)
    body.scale = (k, k, k)
    bpy.ops.object.transform_apply(location=True, scale=True)
    cx2 = [v.co.x for v in body.data.vertices]
    cz2 = [v.co.z for v in body.data.vertices]
    half = (max(cx2) - min(cx2)) / 2 if cx2 else 0.1
    top = max(cz2) if cz2 else 0.2
    center = Vector((0, 0, top / 2))

    if src.suffix.lower() == ".stl":
        mat = bpy.data.materials.new("factory_pla")
        mat.use_nodes = True
        bsdf = mat.node_tree.nodes["Principled BSDF"]
        bsdf.inputs["Base Color"].default_value = (0.52, 0.49, 0.45, 1)
        bsdf.inputs["Roughness"].default_value = 0.6
        body.data.materials.append(mat)

    scn = bpy.context.scene
    scn.render.engine = "CYCLES"
    scn.cycles.device = "CPU"
    scn.cycles.samples = args.samples
    scn.cycles.use_denoising = True
    scn.view_settings.view_transform = "AgX"
    scn.view_settings.look = "AgX - Punchy"
    scn.view_settings.exposure = -0.55
    scn.cycles.max_bounces = 6
    scn.cycles.diffuse_bounces = 3
    scn.cycles.glossy_bounces = 3
    scn.render.resolution_x = args.size
    scn.render.resolution_y = args.size
    scn.render.film_transparent = True
    scn.render.image_settings.file_format = "PNG"
    scn.render.image_settings.color_mode = "RGBA"
    scn.world = bpy.data.worlds.new("w")
    scn.world.use_nodes = True
    scn.world.node_tree.nodes["Background"].inputs[0].default_value = (0.55, 0.55, 0.58, 1)
    scn.world.node_tree.nodes["Background"].inputs[1].default_value = 0.7

    def light(name, loc, tgt, e, s):
        ld = bpy.data.lights.new(name, "AREA")
        ld.energy, ld.size = e, s
        lo = bpy.data.objects.new(name, ld)
        bpy.context.collection.objects.link(lo)
        lo.location = loc
        lo.rotation_euler = (Vector(tgt) - Vector(loc)).to_track_quat("-Z", "Y").to_euler()
        lo.visible_camera = False
        try:
            lo.data.visible_camera = False
        except Exception:
            pass

    t = (0, 0, top / 2)
    light("key", (0.28, -0.28, 0.40), t, 34, 0.7)
    light("fill", (-0.32, -0.22, 0.18), t, 30, 1.1)
    light("rim", (-0.08, 0.38, 0.32), t, 20, 0.5)
    light("bounce", (0.35, -0.28, 0.00), t, 21, 1.0)
    light("flank", (0.08, -0.40, 0.06), t, 25, 0.9)
    light("under", (-0.12, -0.18, -0.08), t, 18, 0.8)
    light("top", (0.00, -0.05, 0.55), t, 18, 1.3)

    def shot(name, offset, lens=55):
        cam_d = bpy.data.cameras.new("c")
        cam = bpy.data.objects.new("c", cam_d)
        bpy.context.collection.objects.link(cam)
        cam.location = center + Vector(offset)
        cam_d.lens = lens
        cam.rotation_euler = (center - cam.location).to_track_quat("-Z", "Y").to_euler()
        scn.camera = cam
        bpy.context.view_layer.update()
        scn.render.filepath = str(out / f"{name}.png")
        bpy.ops.render.render(write_still=True)
        print("shot:", name, flush=True)
        bpy.data.objects.remove(cam, do_unlink=True)

    d = half * 3.2 + 0.15
    shot("front", (0.00, -d, d * 0.30))
    shot("back", (0.00, d, d * 0.30))
    shot("side", (d, 0.00, d * 0.30))
    shot("hero", (d * 0.65, -d * 0.75, d * 0.55), 58)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
