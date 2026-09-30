#!/usr/bin/env python3
"""Product renders for an amended mesh — deterministic, CPU-only.

    blender --background --python scripts/render_product.py -- \\
        --in data/uploads/chibi-figure-hook.glb --out /tmp/renders \\
        [--size 900] [--loop-y -0.0239] [--loop-z 0.1377] [--no-hook] [--sat 1.35]

Why this script exists (see docs/rendering.md for the full spec):
  * Headless EEVEE here is unreliable (EGL_BAD_MATCH) — renders come out
    flat white. Cycles/CPU is deterministic (~60 s for two 900px shots).
  * The glTF material import intermittently arrives as flat white, so the
    4K texture is extracted from the GLB and the material is rebuilt.
  * `Standard` view transform clips cream fur to pure white (~20% blown);
    `AgX` cannot clip but desaturates, so `AgX - Punchy` + a saturation
    node in the material is the combination that passes QC.
  * Cameras need `view_layer.update()` after transform changes, otherwise
    the render uses a stale camera matrix.

QC printed at the end: blown (>250) and crushed (<6) percentages. Targets:
blown < 2%, crushed < 3% for a shippable frame.
"""
from __future__ import annotations

import argparse
import json
import struct
import sys
from pathlib import Path


def parse_args(argv):
    p = argparse.ArgumentParser()
    p.add_argument("--in", dest="src", required=True)
    p.add_argument("--out", dest="outdir", required=True)
    p.add_argument("--size", type=int, default=900, help="square px (use 2000 for listings)")
    p.add_argument("--loop-y", type=float, default=-0.0239,
                   help="loop centre Y (m) — CoM column of the demo dog")
    p.add_argument("--loop-z", type=float, default=0.1377,
                   help="loop ring centre Z (m)")
    p.add_argument("--sat", type=float, default=1.35, help="fur saturation boost")
    p.add_argument("--no-hook", action="store_true", help="skip the S-hook prop")
    argv = argv[argv.index("--") + 1:] if "--" in argv else argv[1:]
    return p.parse_args(argv)


def extract_texture(glb_path: Path) -> Path:
    """Pull the embedded base-color image out of a GLB (reliable > clever)."""
    out = glb_path.with_suffix(".texture.jpg")
    if out.exists() and out.stat().st_size > 0:
        return out
    raw = glb_path.read_bytes()
    clen, _ = struct.unpack("<II", raw[12:20])
    js = json.loads(raw[20:20 + clen])
    bin_off = 20 + clen
    blen, _ = struct.unpack("<II", raw[bin_off:bin_off + 8])
    blob = raw[bin_off + 8: bin_off + 8 + blen]
    img = js["images"][0]
    bv = js["bufferViews"][img["bufferView"]]
    off = bv.get("byteOffset", 0)
    out.write_bytes(blob[off:off + bv["byteLength"]])
    return out


def main() -> int:
    args = parse_args(sys.argv)
    import bpy
    from mathutils import Vector

    src = Path(args.src)
    out_dir = Path(args.outdir)
    out_dir.mkdir(parents=True, exist_ok=True)
    tex = extract_texture(src)

    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=str(src))

    # ---- material: rebuilt from the extracted texture -----------------------
    img = bpy.data.images.load(str(tex), check_existing=True)
    mat = bpy.data.materials.new("product_tex")
    mat.use_nodes = True
    nt = mat.node_tree
    bsdf = nt.nodes["Principled BSDF"]
    texn = nt.nodes.new("ShaderNodeTexImage")
    texn.image = img
    uvn = nt.nodes.new("ShaderNodeUVMap")
    nt.links.new(uvn.outputs["UV"], texn.inputs["Vector"])
    hsv = nt.nodes.new("ShaderNodeHueSaturation")
    hsv.inputs["Saturation"].default_value = args.sat
    nt.links.new(texn.outputs["Color"], hsv.inputs["Color"])
    nt.links.new(hsv.outputs["Color"], bsdf.inputs["Base Color"])
    bsdf.inputs["Roughness"].default_value = 0.65

    for ob in list(bpy.context.scene.objects):
        if ob.type == "MESH" and len(ob.data.vertices) > 10000:
            ob.data.materials.clear()
            ob.data.materials.append(mat)
            if not ob.data.uv_layers:
                raise SystemExit("model has no UV layer")
            bpy.ops.object.select_all(action="DESELECT")
            ob.select_set(True)
            bpy.context.view_layer.objects.active = ob
            bpy.ops.object.mode_set(mode="EDIT")
            bpy.ops.mesh.select_all(action="SELECT")
            bpy.ops.mesh.normals_make_consistent(inside=False)
            bpy.ops.object.mode_set(mode="OBJECT")
            print("material rebuilt on:", ob.name)

    # ---- S-hook prop (hardware prop only — never exported) ------------------
    if not args.no_hook:
        cy, cz = args.loop_y, args.loop_z
        pts = [(-3, 10), (-3, 2), (-1.8, -1.4), (0, -2.0), (1.8, -1.4),
               (3, 2), (3, 12), (2.2, 16.5), (0, 18.5), (-2.6, 16.5)]
        pts = [(x / 1000.0, cy, cz + z / 1000.0) for x, z in pts]
        cu = bpy.data.curves.new("S", "CURVE")
        cu.dimensions = "3D"
        sp = cu.splines.new("BEZIER")
        sp.bezier_points.add(len(pts) - 1)
        for i, (x, y, z) in enumerate(pts):
            bp = sp.bezier_points[i]
            bp.co = (x, y, z)
            bp.handle_left_type = bp.handle_right_type = "AUTO"
        cu.bevel_depth = 0.0005          # 1 mm wire — standard tree hook
        cu.bevel_resolution = 6
        cu.use_fill_caps = True
        hook = bpy.data.objects.new("S_hook", cu)
        bpy.context.collection.objects.link(hook)
        sm = bpy.data.materials.new("steel")
        sm.use_nodes = True
        b = sm.node_tree.nodes["Principled BSDF"]
        b.inputs["Base Color"].default_value = (0.72, 0.73, 0.78, 1)
        b.inputs["Metallic"].default_value = 1.0
        b.inputs["Roughness"].default_value = 0.30
        hook.data.materials.append(sm)

    # ---- scene: the recipe that passes QC -----------------------------------
    scn = bpy.context.scene
    scn.render.engine = "CYCLES"
    scn.cycles.device = "CPU"
    scn.cycles.samples = 48
    scn.cycles.use_denoising = True
    scn.view_settings.view_transform = "AgX"      # cannot clip to pure white
    scn.view_settings.look = "AgX - Punchy"       # counteracts AgX flatness
    scn.render.resolution_x = args.size
    scn.render.resolution_y = args.size
    scn.world = bpy.data.worlds.new("w")
    scn.world.use_nodes = True
    scn.world.node_tree.nodes["Background"].inputs[0].default_value = (
        0.085, 0.09, 0.10, 1)

    def light(name, loc, tgt, e, s):
        ld = bpy.data.lights.new(name, "AREA")
        ld.energy = e
        ld.size = s
        lo = bpy.data.objects.new(name, ld)
        bpy.context.collection.objects.link(lo)
        lo.location = loc
        lo.rotation_euler = (Vector(tgt) - Vector(loc)).to_track_quat(
            "-Z", "Y").to_euler()
        lo.visible_camera = False

    light("key", (0.30, -0.25, 0.35), (0, -0.02, 0.12), 90, 0.5)
    light("fill", (-0.35, -0.15, 0.15), (0, -0.02, 0.10), 65, 0.9)
    light("rim", (-0.10, 0.35, 0.30), (0, 0.02, 0.14), 55, 0.4)
    light("bounce", (0.40, -0.30, 0.02), (0, -0.02, 0.09), 45, 0.8)

    def shot(path, target, offset, lens):
        tgt = Vector(target)
        cam_d = bpy.data.cameras.new("c")
        cam = bpy.data.objects.new("c", cam_d)
        bpy.context.collection.objects.link(cam)
        cam.location = tgt + Vector(offset)
        cam_d.lens = lens
        cam.rotation_euler = (tgt - cam.location).to_track_quat("-Z", "Y").to_euler()
        scn.camera = cam
        bpy.context.view_layer.update()     # stale matrix = wrong framing
        scn.render.filepath = str(path)
        bpy.ops.render.render(write_still=True)
        print("shot:", path)
        bpy.data.objects.remove(cam, do_unlink=True)

    cy, cz = args.loop_y, args.loop_z
    shot(out_dir / "detail.png", (0, cy, cz + 0.004), (0.10, -0.055, 0.025), 85)
    shot(out_dir / "hero.png", (0, -0.005, 0.100), (0.317, -0.384, 0.234), 58)

    # ---- QC on the outputs ---------------------------------------------------
    # Blender's bundled Python has no PIL — run the check with system python3.
    import shutil
    import subprocess
    helper = (
        "import sys;from PIL import Image,ImageStat;"
        "im=Image.open(sys.argv[1]).convert('L');h=im.histogram();t=sum(h);"
        "print(f'{ImageStat.Stat(im).mean[0]:.1f} "
        "{100*sum(h[250:])/t:.2f} {100*sum(h[:6])/t:.1f}')"
    )
    py = shutil.which("python3") or "/usr/bin/python3"
    for f in ("detail.png", "hero.png"):
        run = subprocess.run([py, "-c", helper, str(out_dir / f)],
                             capture_output=True, text=True)
        if run.returncode != 0:
            print(f"QC {f}: skipped ({(run.stderr or 'helper failed').strip().splitlines()[-1]})")
            continue
        mean, blown, black = run.stdout.split()
        print(f"QC {f}: mean={mean} blown={blown}% black={black}% "
              f"{'PASS' if float(blown) < 2 and float(black) < 3 else 'CHECK'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
