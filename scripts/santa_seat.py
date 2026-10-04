#!/usr/bin/env python3
"""Seat a procedural santa hat on the canonical dog — explicit measured values.

    blender --background --python scripts/santa_seat.py -- \
      --in data/uploads/chibi-figure-hook.glb \
      --out data/santa_seat --size 800

Measured on chibi-figure-hook.glb (2026-10-03):
  bbox x±0.052  y[-0.152,0.152]  z[0, 0.20]
  skull between ears: w≈0.05, ymid≈-0.107, upper skull z≈0.155
  ears: x±0.052 up to z≈0.187
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path


def parse_args(argv):
    p = argparse.ArgumentParser()
    p.add_argument("--in", dest="src", required=True)
    p.add_argument("--out", dest="outdir", required=True)
    p.add_argument("--size", type=int, default=800)
    p.add_argument("--coat", default="cream")
    argv = argv[argv.index("--") + 1:] if "--" in argv else argv[1:]
    return p.parse_args(argv)


COAT = {
    "none": None,
    "cream": (0.93, 0.86, 0.74),
    "golden": (0.90, 0.72, 0.42),
    "chocolate": (0.42, 0.26, 0.16),
    "black": (0.12, 0.11, 0.11),
    "fawn": (0.82, 0.68, 0.52),
    "grey": (0.55, 0.55, 0.56),
}


def main() -> int:
    args = parse_args(sys.argv)
    import bpy
    from mathutils import Vector

    src = Path(args.src)
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=str(src))
    body = [o for o in bpy.context.scene.objects if o.type == "MESH"]
    if not body:
        raise SystemExit("no mesh")

    # measure dog only
    pts = [body[0].matrix_world @ v.co for v in body[0].data.vertices]
    xs = [p.x for p in pts]; ys = [p.y for p in pts]; zs = [p.z for p in pts]
    print(f"DOG bbox x=[{min(xs):.4f},{max(xs):.4f}] "
          f"y=[{min(ys):.4f},{max(ys):.4f}] z=[{min(zs):.4f},{max(zs):.4f}]")

    # Explicit seat (measured). Brim must be SMALLER than the dog body —
    # skull between ears is ~0.05 wide; a brim at 0.076 looked like a UFO.
    HEAD_W = 0.050          # skull width between ears
    HEAD_Y = -0.107         # head centre (nose is toward -Y)
    BRIM_Z = 0.145          # upper skull, below ear tips (~0.187)
    BRIM_R = 0.022          # outer ≈ 0.03 — hugs the skull
    BRIM_MINOR = 0.007
    CONE_D = 0.055
    print(f"SEAT head_w={HEAD_W} y={HEAD_Y} brim_z={BRIM_Z} brim_r={BRIM_R} cone_d={CONE_D}")

    # optional coat grade on body
    coat_rgb = COAT.get((args.coat or "none").lower())
    if coat_rgb:
        for ob in body:
            mat = bpy.data.materials.new(f"coat_{args.coat}")
            mat.use_nodes = True
            b = mat.node_tree.nodes["Principled BSDF"]
            b.inputs["Base Color"].default_value = (*coat_rgb, 1)
            b.inputs["Roughness"].default_value = 0.55
            if ob.data.materials:
                ob.data.materials[0] = mat
            else:
                ob.data.materials.append(mat)
        print(f"coat grade {args.coat} {coat_rgb}")

    red = bpy.data.materials.new("santa_red")
    red.use_nodes = True
    rb = red.node_tree.nodes["Principled BSDF"]
    rb.inputs["Base Color"].default_value = (0.12, 0.004, 0.004, 1)
    rb.inputs["Roughness"].default_value = 0.9
    if "Specular IOR Level" in rb.inputs:
        rb.inputs["Specular IOR Level"].default_value = 0.05

    white = bpy.data.materials.new("santa_white")
    white.use_nodes = True
    wb = white.node_tree.nodes["Principled BSDF"]
    wb.inputs["Base Color"].default_value = (0.90, 0.89, 0.84, 1)
    wb.inputs["Roughness"].default_value = 0.92

    # cone: base at brim, tip up — small enough for a 50mm skull
    bpy.ops.mesh.primitive_cone_add(
        vertices=24,
        radius1=BRIM_R * 0.90,
        radius2=0.004,
        depth=CONE_D,
        location=(0.0, HEAD_Y + 0.003, BRIM_Z + CONE_D * 0.5),
    )
    cone = bpy.context.active_object
    cone.name = "santa_cone"
    cone.rotation_euler = (0.18, 0.04, 0)
    cone.data.materials.append(red)

    # brim torus — Blender 4: major_radius = centre-of-tube radius (WORKS).
    # abso_* kwargs are ignored by the operator (falls back to defaults).
    bpy.ops.mesh.primitive_torus_add(
        major_radius=BRIM_R,
        minor_radius=BRIM_MINOR,
        major_segments=32,
        minor_segments=12,
        location=(0.0, HEAD_Y, BRIM_Z + 0.001),
    )
    brim = bpy.context.active_object
    brim.name = "santa_brim"
    brim.scale = (1.0, 0.90, 0.70)
    brim.data.materials.append(white)
    print(f"brim dims={tuple(round(x,4) for x in brim.dimensions)}")

    # pompom at cone tip
    bpy.ops.mesh.primitive_uv_sphere_add(
        segments=16, ring_count=12,
        radius=BRIM_R * 0.35,
        location=(0.012, HEAD_Y + 0.015, BRIM_Z + CONE_D * 0.95),
    )
    pomp = bpy.context.active_object
    pomp.name = "santa_pompom"
    pomp.data.materials.append(white)

    print("HAT objects:", [o.name for o in bpy.context.scene.objects if o.type == "MESH"])

    # lights + white world
    def area(name, loc, energy, size):
        bpy.ops.object.light_add(type="AREA", location=loc)
        L = bpy.context.active_object
        L.name = name
        L.data.energy = energy
        L.data.size = size
        # lights must never appear as white discs in the still
        try:
            L.visible_camera = False
        except Exception:
            pass
        try:
            L.data.visible_camera = False
        except Exception:
            pass
        d = Vector((0, 0, 0.1)) - Vector(loc)
        L.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()
        return L

    area("key", (0.35, -0.45, 0.45), 80, 0.5)
    area("fill", (-0.40, -0.30, 0.30), 40, 0.5)
    area("rim", (0.05, 0.40, 0.35), 50, 0.4)

    world = bpy.data.worlds.new("W")
    bpy.context.scene.world = world
    world.use_nodes = True
    bg = world.node_tree.nodes["Background"]
    bg.inputs[0].default_value = (1, 1, 1, 1)
    bg.inputs[1].default_value = 0.9

    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    scene.cycles.samples = 32
    scene.cycles.use_denoising = True
    scene.render.resolution_x = args.size
    scene.render.resolution_y = args.size
    scene.render.film_transparent = False
    scene.render.image_settings.file_format = "PNG"
    try:
        scene.view_settings.view_transform = "AgX"
        scene.view_settings.look = "AgX - Punchy"
    except Exception:
        pass

    shots = {
        "hero":  Vector((0.28, -0.42, 0.28)),
        "front": Vector((0.0, -0.55, 0.16)),
        "side":  Vector((0.50, -0.05, 0.14)),
    }
    target = Vector((0.0, -0.05, 0.10))
    for name, loc in shots.items():
        bpy.ops.object.camera_add(location=loc)
        cam = bpy.context.active_object
        cam.name = f"cam_{name}"
        d = target - loc
        cam.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()
        scene.camera = cam
        bpy.context.view_layer.update()
        scene.render.filepath = str(outdir / f"santa-{name}.png")
        bpy.ops.render.render(write_still=True)
        print(f"Saved {scene.render.filepath}")
        bpy.data.objects.remove(cam, do_unlink=True)

    # export GLB with hat
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.export_scene.gltf(
        filepath=str(outdir / "dog-santa.glb"),
        export_format="GLB",
        use_selection=True,
        export_yup=True,
        export_apply=True,
    )
    print(f"wrote {outdir / 'dog-santa.glb'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
