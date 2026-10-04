#!/usr/bin/env python3
"""Export standalone product parts from the canonical dog — free Blender.

    blender --background --python scripts/export_parts.py -- \
        --out data/assets/parts

Parts (P0 reference: docs/p0-hat-coat.md):
  hat-santa.glb      santa hat alone, SEATED in dog space (bake world verts,
                     so composing = concatenate with the dog, no math)
  coat-<name>.glb    dog body geometry with a flat coat material (no photo
                     texture) — attaching a coat = swapping the body material

Inputs (never modified):
  data/productimg/prod/dog-santa.glb      dog + procedural santa nodes
  data/uploads/chibi-figure-hook.glb      canonical textured dog

0 Meshy credits. Blender 4.0+ (headless).
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path


def parse_args(argv):
    p = argparse.ArgumentParser()
    p.add_argument("--out", default="data/assets/parts")
    p.add_argument("--dog-santa", default="data/productimg/prod/dog-santa.glb")
    p.add_argument("--dog", default="data/uploads/chibi-figure-hook.glb")
    argv = argv[argv.index("--") + 1:] if "--" in argv else argv[1:]
    return p.parse_args(argv)


COATS = {
    "cream": (0.93, 0.86, 0.74),
    "golden": (0.90, 0.72, 0.42),
    "chocolate": (0.42, 0.26, 0.16),
    "black": (0.12, 0.11, 0.11),
    "fawn": (0.82, 0.68, 0.52),
    "grey": (0.55, 0.55, 0.56),
}

HAT_NODES = ("santa_cone", "santa_brim", "santa_pompom")


def main() -> int:
    args = parse_args(sys.argv)
    import bpy

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    # ── hat: extract seated santa nodes from dog-santa.glb ──────────
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=str(Path(args.dog_santa)))
    hat = [o for o in bpy.context.scene.objects
           if o.type == "MESH" and o.name in HAT_NODES]
    if len(hat) != 3:
        print(f"HAT FAIL: found {[o.name for o in hat]} — want {HAT_NODES}")
        return 1
    bpy.ops.object.select_all(action="DESELECT")
    for o in hat:
        o.select_set(True)
    bpy.context.view_layer.objects.active = hat[0]
    hat_path = out / "hat-santa.glb"
    bpy.ops.export_scene.gltf(
        filepath=str(hat_path),
        export_format="GLB",
        use_selection=True,
        export_yup=True,
        export_apply=True,  # bake world seat into the geometry
    )
    print(f"hat {sorted(o.name for o in hat)} -> {hat_path} "
          f"({hat_path.stat().st_size} bytes)")

    # ── coats: body geometry + flat coat material, no photo texture ──
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=str(Path(args.dog)))
    bodies = [o for o in bpy.context.scene.objects if o.type == "MESH"]
    if not bodies:
        print("COAT FAIL: no mesh in dog GLB")
        return 1
    print(f"dog bodies: {[(o.name, len(o.data.vertices)) for o in bodies]}")
    for name, rgb in COATS.items():
        mat = bpy.data.materials.new(f"coat_{name}")
        mat.use_nodes = True
        bsdf = mat.node_tree.nodes["Principled BSDF"]
        bsdf.inputs["Base Color"].default_value = (*rgb, 1.0)
        bsdf.inputs["Roughness"].default_value = 0.55
        for ob in bodies:
            ob.data.materials.clear()
            ob.data.materials.append(mat)
        bpy.ops.object.select_all(action="DESELECT")
        for ob in bodies:
            ob.select_set(True)
        bpy.context.view_layer.objects.active = bodies[0]
        coat_path = out / f"coat-{name}.glb"
        bpy.ops.export_scene.gltf(
            filepath=str(coat_path),
            export_format="GLB",
            use_selection=True,
            export_yup=True,
            export_apply=True,
        )
        print(f"coat {name} {rgb} -> {coat_path} "
              f"({coat_path.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
