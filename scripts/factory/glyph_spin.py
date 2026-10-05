#!/usr/bin/env python3
"""Factory glyph spin: extrude the canonical SVG mark, shoot a turntable.

    blender --background --python scripts/factory/glyph_spin.py -- \\
        --svg data/logo1/oddhobb-canonical\\(1\\).svg \\
        --out /tmp/glyphspin --frames 12 --size 384

What CSS rotateY fakes, this bakes for real: true thickness, true shading,
12 frames ready for a snapshot-style spin strip (loader, waiting states).
White studio, warm-brown plastic, transparent film (composite like stills).
"""
from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path


def parse_args(argv):
    p = argparse.ArgumentParser()
    p.add_argument("--svg", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--frames", type=int, default=12)
    p.add_argument("--size", type=int, default=384)
    p.add_argument("--samples", type=int, default=24)
    argv = argv[argv.index("--") + 1:] if "--" in argv else argv[1:]
    return p.parse_args(argv)


def main() -> int:
    args = parse_args(sys.argv)
    import bpy
    from mathutils import Vector

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_curve.svg(filepath=args.svg)

    curves = [o for o in bpy.context.scene.objects if o.type == "CURVE"]
    if not curves:
        print("no curves imported")
        return 2
    for cu in curves:
        # SVG imports near unit scale (~0.7 wide), so extrude/bevel are in
        # the same units: thin relief, not a fat puck. 3D keeps open loops
        # from capping; the boundary ring stays a clean tube.
        cu.data.dimensions = "3D"
        cu.data.extrude = 0.012
        cu.data.bevel_depth = 0.004
        cu.data.bevel_resolution = 2
    bpy.ops.object.select_all(action="SELECT")
    bpy.context.view_layer.objects.active = curves[0]
    bpy.ops.object.join()
    coin = bpy.context.active_object
    bpy.ops.object.convert(target="MESH")
    coin = bpy.context.active_object
    coin.data = coin.data.copy()
    # normalize to 0.2 stage, centered
    xs = [v.co.x for v in coin.data.vertices]
    ys = [v.co.y for v in coin.data.vertices]
    zs = [v.co.z for v in coin.data.vertices]
    maxd = max(max(xs) - min(xs), max(ys) - min(ys), max(zs) - min(zs)) or 1.0
    k = 0.2 / maxd
    coin.location = (-(min(xs) + max(xs)) / 2 * k, -(min(ys) + max(ys)) / 2 * k,
                     -min(zs) * k)
    coin.scale = (k, k, k)
    bpy.ops.object.transform_apply(location=True, scale=True)

    mat = bpy.data.materials.new("glyph_plastic")
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = (0.42, 0.28, 0.16, 1)
    bsdf.inputs["Roughness"].default_value = 0.45
    coin.data.materials.append(mat)

    scn = bpy.context.scene
    scn.render.engine = "CYCLES"
    scn.cycles.device = "CPU"
    scn.cycles.samples = args.samples
    scn.cycles.use_denoising = True
    scn.cycles.max_bounces = 6
    scn.view_settings.view_transform = "AgX"
    scn.view_settings.look = "AgX - Punchy"
    scn.view_settings.exposure = -0.4
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

    t = (0, 0, 0.05)
    light("key", (0.28, -0.28, 0.40), t, 34, 0.7)
    light("fill", (-0.32, -0.22, 0.18), t, 30, 1.1)
    light("rim", (-0.08, 0.38, 0.32), t, 20, 0.5)

    cam_d = bpy.data.cameras.new("c")
    cam = bpy.data.objects.new("c", cam_d)
    bpy.context.collection.objects.link(cam)
    cam_d.lens = 55
    scn.camera = cam
    for i in range(args.frames):
        a = 2 * math.pi * i / args.frames
        cam.location = (0.42 * math.sin(a), -0.42 * math.cos(a), 0.16)
        cam.rotation_euler = (Vector((0, 0, 0.05)) - cam.location).to_track_quat("-Z", "Y").to_euler()
        bpy.context.view_layer.update()
        scn.render.filepath = str(out / f"coin-{i:02d}.png")
        bpy.ops.render.render(write_still=True)
        print("frame:", i, flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
