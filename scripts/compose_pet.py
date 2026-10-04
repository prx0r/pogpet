#!/usr/bin/env python3
"""Compose product meshes from parts — free Blender, 0 Meshy credits.

    blender --background --python scripts/compose_pet.py -- \\
        --dog data/uploads/chibi-figure-hook.glb \\
        --hat data/assets/parts/hat-santa.glb \\
        --coat cream --out data/productimg/prod/dog-santa-cream.glb

Parts are pre-seated in dog space (see scripts/export_parts.py), so composing
is concatenation — no measuring, no math. Coat = flat material on the body.
P0 reference: docs/p0-hat-coat.md.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path


def parse_args(argv):
    p = argparse.ArgumentParser()
    p.add_argument("--dog", required=True)
    p.add_argument("--hat", default="none",
                   help="path to hat part GLB, or 'none'")
    p.add_argument("--coat", default="none",
                   help="cream|golden|chocolate|black|fawn|grey|none")
    p.add_argument("--out", required=True)
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


def main() -> int:
    args = parse_args(sys.argv)
    import bpy

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.read_factory_settings(use_empty=True)

    bpy.ops.import_scene.gltf(filepath=str(Path(args.dog)))
    body = [o for o in bpy.context.scene.objects if o.type == "MESH"]
    if not body:
        raise SystemExit("no mesh in dog GLB")
    print(f"dog: {[(o.name, len(o.data.vertices)) for o in body]}")

    hat_objs = []
    if args.hat and args.hat != "none":
        before = set(bpy.context.scene.objects)
        bpy.ops.import_scene.gltf(filepath=str(Path(args.hat)))
        hat_objs = [o for o in bpy.context.scene.objects
                    if o not in before and o.type == "MESH"]
        if not hat_objs:
            raise SystemExit(f"no mesh in hat part {args.hat}")
        print(f"hat: {[o.name for o in hat_objs]} (pre-seated, untouched)")

    coat = (args.coat or "none").lower()
    if coat != "none":
        rgb = COATS.get(coat)
        if rgb is None:
            raise SystemExit(f"unknown coat {coat!r}")
        mat = bpy.data.materials.new(f"coat_{coat}")
        mat.use_nodes = True
        bsdf = mat.node_tree.nodes["Principled BSDF"]
        bsdf.inputs["Base Color"].default_value = (*rgb, 1.0)
        bsdf.inputs["Roughness"].default_value = 0.55
        for ob in body:
            ob.data.materials.clear()
            ob.data.materials.append(mat)
        print(f"coat grade {coat} {rgb}")

    all_objs = body + hat_objs
    bpy.ops.object.select_all(action="DESELECT")
    for o in all_objs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = all_objs[0]
    bpy.ops.export_scene.gltf(
        filepath=str(out),
        export_format="GLB",
        use_selection=True,
        export_yup=True,
        export_apply=True,
    )
    print(f"composed dog+{Path(args.hat).stem if hat_objs else 'nohat'}+"
          f"{coat} -> {out} ({out.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
