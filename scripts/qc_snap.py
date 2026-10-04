#!/usr/bin/env python3
"""QC snapshots (debugging only — NOT product stills).

Renders small EEVEE 3/4 views of composed GLBs so a human can SEE fit
issues (hat seat, jacket clearance) instead of guessing from numbers.
Output: data/qc/<name>.png  (never published to /img/).

    blender --background --python scripts/qc_snap.py -- \\
        --in /tmp/opencode/dog-jacket-chocolate.glb --out data/qc --size 800
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path


def parse_args(argv):
    p = argparse.ArgumentParser()
    p.add_argument("--in", dest="src", required=True)
    p.add_argument("--out", default="data/qc")
    p.add_argument("--size", type=int, default=800)
    argv = argv[argv.index("--") + 1:] if "--" in argv else argv[1:]
    return p.parse_args(argv)


def main() -> int:
    args = parse_args(sys.argv)
    import bpy
    from mathutils import Vector

    src = Path(args.src)
    outdir = Path(args.out)
    outdir.mkdir(parents=True, exist_ok=True)

    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=str(src))

    # flat debug colors: body gray, hat red, jacket/harness blue, else green
    for o in bpy.context.scene.objects:
        if o.type != "MESH":
            continue
        nm = (o.name or "").lower()
        if "hat" in nm or "santa" in nm or "cone" in nm or "brim" in nm or "pompom" in nm:
            col = (1.0, 0.15, 0.15, 1.0)
        elif "jacket" in nm or "harness" in nm:
            col = (0.15, 0.35, 1.0, 1.0)
        elif "mesh_0" in nm or len(o.data.vertices) > 50000:
            col = (0.55, 0.55, 0.55, 1.0)
        else:
            col = (0.2, 0.8, 0.2, 1.0)
        m = bpy.data.materials.new("qc_" + o.name)
        m.use_nodes = True
        bsdf = m.node_tree.nodes["Principled BSDF"]
        bsdf.inputs["Base Color"].default_value = col
        bsdf.inputs["Roughness"].default_value = 0.9
        o.data.materials.clear()
        o.data.materials.append(m)

    # frame everything
    pts = [o.matrix_world @ v.co for o in bpy.context.scene.objects
           if o.type == "MESH" for v in o.data.vertices]
    mn = Vector((min(p.x for p in pts), min(p.y for p in pts),
                 min(p.z for p in pts)))
    mx = Vector((max(p.x for p in pts), max(p.y for p in pts),
                 max(p.z for p in pts)))
    ctr = (mn + mx) / 2
    rad = max((mx - mn).x, (mx - mn).y, (mx - mn).z)

    # flat studio HDRI-ish light: 3 area lights + mid-gray world
    for name, loc, e in (("k", (1, -1, 1.2), 60), ("f", (-1, -0.6, 0.8), 30),
                         ("r", (0, 1, 0.9), 40)):
        bpy.ops.object.light_add(type="AREA", location=(ctr + Vector(loc) * rad * 2))
        bpy.context.active_object.data.energy = e
        bpy.context.active_object.data.size = rad

    world = bpy.data.worlds.new("W")
    bpy.context.scene.world = world
    world.use_nodes = True
    world.node_tree.nodes["Background"].inputs[0].default_value = (0.55,) * 3 + (1,)

    scene = bpy.context.scene
    scene.render.engine = "BLENDER_EEVEE_NEXT"
    scene.render.resolution_x = args.size
    scene.render.resolution_y = args.size
    scene.render.film_transparent = False
    scene.render.image_settings.file_format = "PNG"

    for view, off in (("front", Vector((0.0, -1.0, 0.35))),
                      ("side", Vector((1.0, -0.15, 0.3))),
                      ("top", Vector((0.15, -0.2, 1.0)))):
        bpy.ops.object.camera_add(location=ctr + off.normalized() * rad * 2.6)
        cam = bpy.context.active_object
        d = ctr - cam.location
        cam.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()
        scene.camera = cam
        bpy.context.view_layer.update()
        scene.render.filepath = str(outdir / f"{src.stem}-{view}.png")
        bpy.ops.render.render(write_still=True)
        print(f"saved {scene.render.filepath}")
        bpy.data.objects.remove(cam, do_unlink=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
