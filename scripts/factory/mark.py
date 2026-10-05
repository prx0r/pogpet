#!/usr/bin/env python3
"""Factory mark: canonical SVG -> source-of-truth GLB family + poker chip.

    blender --background --python scripts/factory/mark.py -- \
        --svg "data/logo1/oddhobb-canonical(1).svg" \
        --out data/3dprint/masters/mark

Deterministic only — never Meshy for the logo (drift). Outputs:
  oddhobb_mark_flat.glb       curves as flat relief (loader start state)
  oddhobb_mark_mesh.glb       lightly beveled master (spin/flip/emboss work)
  oddhobb_mark_embossed.glb   deeper relief (seals, stamps, ornaments)
  oddhobb_poker_chip.glb      chip body + raised mark both faces + edge ridges

Import scale note (measured): SVG lands near unit scale, so extrude/bevel
values are in the same units — thin numbers, like glyph_spin.py.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path


CANONICAL_SVG = str(Path(__file__).resolve().parent.parent.parent /
                     "assets" / "logo" / "oddhobb-canonical.svg")


def parse_args(argv):
    p = argparse.ArgumentParser()
    p.add_argument("--svg", default=CANONICAL_SVG,
                   help="defaults to the canonical mark (assets/logo/)")
    p.add_argument("--out", required=True)
    argv = argv[argv.index("--") + 1:] if "--" in argv else argv[1:]
    return p.parse_args(argv)


def import_mark():
    import bpy
    curves = [o for o in bpy.context.scene.objects if o.type == "CURVE"]
    for cu in curves:
        cu.data.dimensions = "3D"
    return curves


def to_mesh(objs, bevel_depth=0.0, extrude=0.0):
    import bpy
    for cu in objs:
        if extrude:
            cu.data.extrude = extrude
        if bevel_depth:
            cu.data.bevel_depth = bevel_depth
            cu.data.bevel_resolution = 2
    bpy.ops.object.select_all(action="DESELECT")
    for o in objs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]
    bpy.ops.object.join()
    bpy.ops.object.convert(target="MESH")
    body = bpy.context.active_object
    body.data = body.data.copy()
    return body


def normalize(body, target=0.2):
    import bpy
    xs = [v.co.x for v in body.data.vertices]
    ys = [v.co.y for v in body.data.vertices]
    zs = [v.co.z for v in body.data.vertices]
    maxd = max(max(xs) - min(xs), max(ys) - min(ys), max(zs) - min(zs)) or 1.0
    k = target / maxd
    body.location = (-(min(xs) + max(xs)) / 2 * k, -(min(ys) + max(ys)) / 2 * k,
                     -min(zs) * k)
    body.scale = (k, k, k)
    bpy.ops.object.transform_apply(location=True, scale=True)
    return body


def export_glb(obj, path: Path):
    import bpy
    bpy.ops.object.select_all(action="DESELECT")
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)
    bpy.context.view_layer.update()
    path.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.export_scene.gltf(filepath=str(path), use_selection=True,
                              export_format="GLB")


def plastic(obj, rgb=(0.42, 0.28, 0.16, 1)):
    mat = obj.data.materials.get("mark_plastic")
    if mat is None:
        import bpy
        mat = bpy.data.materials.new("mark_plastic")
        mat.use_nodes = True
        bsdf = mat.node_tree.nodes["Principled BSDF"]
        bsdf.inputs["Base Color"].default_value = rgb
        bsdf.inputs["Roughness"].default_value = 0.45
    obj.data.materials.clear()
    obj.data.materials.append(mat)


def build_mark_set(svg: str, out: Path):
    import bpy
    # flat: strokes as thin relief (hairline extrude: edge-only meshes
    # export as empty GLBs, so flat still gets real, minimal faces)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_curve.svg(filepath=svg)
    flat = normalize(to_mesh(import_mark(), extrude=0.002))
    plastic(flat)
    export_glb(flat, out / "oddhobb_mark_flat.glb")
    print("flat verts:", len(flat.data.vertices), flush=True)
    # master: light bevel, the working mesh for spin/flip/emboss/boolean
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_curve.svg(filepath=svg)
    master = normalize(to_mesh(import_mark(), bevel_depth=0.004, extrude=0.008))
    plastic(master)
    export_glb(master, out / "oddhobb_mark_mesh.glb")
    print("master verts:", len(master.data.vertices), flush=True)
    # embossed: deep relief for seals and stamps
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_curve.svg(filepath=svg)
    emb = normalize(to_mesh(import_mark(), bevel_depth=0.006, extrude=0.02))
    plastic(emb)
    export_glb(emb, out / "oddhobb_mark_embossed.glb")
    print("embossed verts:", len(emb.data.vertices), flush=True)


def build_poker_chip(svg: str, out: Path):
    import bpy
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_curve.svg(filepath=svg)
    mark = normalize(to_mesh(import_mark(), bevel_depth=0.003, extrude=0.006))
    # chip body: 40mm dia x 4mm, edge ridges as 12 small boxes
    bpy.ops.mesh.primitive_cylinder_add(radius=0.1, depth=0.02, vertices=64,
                                        location=(0, 0, 0.01))
    chip = bpy.context.active_object
    chip.name = "chip"
    parts = [chip]
    import math
    for i in range(12):
        a = 2 * math.pi * i / 12
        bpy.ops.mesh.primitive_cube_add(
            size=1, location=(0.088 * math.cos(a), 0.088 * math.sin(a), 0.01))
        r = bpy.context.active_object
        r.name = f"ridge{i}"
        r.scale = (0.012, 0.02, 0.021)
        r.rotation_euler = (0, 0, a)
        bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)
        parts.append(r)
    # raised mark both faces, scaled into the chip face
    for z, nm in ((0.021, "mark_top"), (-0.001, "mark_bot")):
        before = set(bpy.context.scene.objects)
        bpy.ops.import_curve.svg(filepath=svg)
        fresh = [o for o in bpy.context.scene.objects
                 if o not in before and o.type == "CURVE"]
        m = normalize(to_mesh(fresh, bevel_depth=0.002, extrude=0.004))
        m.scale = (0.32, 0.32, 0.32)
        m.location = (0, 0, z)
        bpy.ops.object.transform_apply(location=True, scale=True)
        m.name = nm
        parts.append(m)
    bpy.ops.object.select_all(action="DESELECT")
    for p in parts:
        p.select_set(True)
    bpy.context.view_layer.objects.active = chip
    bpy.ops.object.join()
    chip = bpy.context.active_object
    chip.name = "poker_chip"
    plastic(chip, rgb=(0.75, 0.16, 0.14, 1))
    export_glb(chip, out / "oddhobb_poker_chip.glb")
    print("chip verts:", len(chip.data.vertices), flush=True)


def main() -> int:
    args = parse_args(sys.argv)
    out = Path(args.out)
    build_mark_set(args.svg, out)
    build_poker_chip(args.svg, out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
