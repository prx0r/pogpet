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
    p.add_argument("--no-hook", action="store_true", help="skip the hardware prop")
    p.add_argument("--variant", choices=("ornament", "keychain"), default="ornament",
                   help="ornament = printed loop + matching plastic tree hook; "
                        "keychain = printed loop + printed plastic ring (no metal)")
    p.add_argument("--hardware", choices=("printed", "steel"), default="printed",
                   help="printed = same plastic as the pet (ships POD-safe); "
                        "steel = marketing prop only")
    p.add_argument("--coat", default="",
                   help="fur tint for previews: cream|golden|chocolate|black|fawn|grey "
                        "|RRGGBB (free Blender grade; production multi-colour is quoted live)")
    p.add_argument("--prop", default="",
                   help="custom-request preview prop: santa | none (free Blender addons; "
                        "new Meshy bodies are gated — ask first)")
    p.add_argument("--hat-asset", default="",
                   help="path to FBX/OBJ/GLB hat under data/assets/hats/ "
                        "(CC0/commercial). Seats on measured skull. Empty = procedural prop")
    p.add_argument("--hat-text", default="",
                   help="optional short text on the hat band (e.g. lucky, MAX)")
    p.add_argument("--scale-mm", type=float, default=0.0,
                   help="uniform scale so the mesh's tallest axis is this many mm "
                        "(0 = keep Meshy scale; production SKUs: pets 80, bricks 75)")
    p.add_argument("--bg", choices=("dark", "white"), default="dark",
                   help="world background: dark studio or pure white marketing")
    p.add_argument("--shots", default="standard",
                    help="standard = detail+hero | marketing = white multi-angle "
                         "ornament set | keychain = white set | exact = product-only "
                         "white set (no props)")
    p.add_argument("--exact", action="store_true",
                   help="canonical mesh only — no S-hook, no keyring, no santa, "
                        "no coat grade. Product photo, not a lifestyle prop shot")
    argv = argv[argv.index("--") + 1:] if "--" in argv else argv[1:]
    return p.parse_args(argv)


COAT_HEX = {
    "cream": (0.93, 0.86, 0.74),
    "golden": (0.90, 0.72, 0.42),
    "chocolate": (0.42, 0.26, 0.16),
    "black": (0.12, 0.11, 0.11),
    "fawn": (0.82, 0.68, 0.52),
    "grey": (0.55, 0.55, 0.56),
}


def coat_rgb(spec: str):
    """Named coat or #RRGGBB → linear-ish RGB tuple for a Multiply node."""
    if not spec:
        return None
    s = spec.strip().lower().lstrip("#")
    if s in COAT_HEX:
        return COAT_HEX[s]
    if len(s) == 6 and all(c in "0123456789abcdef" for c in s):
        r, g, b = (int(s[i:i + 2], 16) / 255.0 for i in (0, 2, 4))
        # rough sRGB→linear so dark coats don't wash out under AgX
        return tuple((c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4)
                     for c in (r, g, b))
    raise SystemExit(f"unknown --coat {spec!r} (use a name or RRGGBB)")


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
    fur_rgb = None
    if args.coat:
        fur_rgb = coat_rgb(args.coat)
        mult = nt.nodes.new("ShaderNodeMix")
        mult.data_type = "RGBA"
        mult.blend_type = "MULTIPLY"
        mult.inputs["Factor"].default_value = 1.0
        mult.inputs[7].default_value = (*fur_rgb, 1.0)   # B = coat colour
        nt.links.new(hsv.outputs["Color"], mult.inputs[6])  # A = textured fur
        nt.links.new(mult.outputs[2], bsdf.inputs["Base Color"])
        print(f"coat tint applied: {args.coat} -> {fur_rgb}")
    else:
        nt.links.new(hsv.outputs["Color"], bsdf.inputs["Base Color"])
    bsdf.inputs["Roughness"].default_value = 0.65

    for ob in list(bpy.context.scene.objects):
        if ob.type == "MESH" and len(ob.data.vertices) > 100:
            ob.data.materials.clear()
            ob.data.materials.append(mat)
            if not ob.data.uv_layers:
                raise SystemExit("model has no UV layer")
            bpy.ops.object.select_all(action="DESELECT")
            ob.select_set(True)
            bpy.context.view_layer.objects.active = ob
            bpy.ops.object.mode_set(mode="EDIT")
            bpy.ops.mesh.select_all(action="SELECT")
            bpy.ops.mesh.remove_doubles(threshold=0.00015)
            bpy.ops.mesh.normals_make_consistent(inside=False)
            bpy.ops.object.mode_set(mode="OBJECT")
            print("material rebuilt on:", ob.name)

    # ---- printed loop: DO NOT recolour --------------------------------------
    # A flat loop material painted a white disc on the back that is not in the
    # GLB. Renders must match the mesh — fur texture stays on the loop.

    # ---- production scale (SKUs are 80 mm pets / 75 mm bricks) --------------
    if args.scale_mm > 0:
        zs = [(ob.matrix_world @ v.co).z
              for ob in bpy.context.scene.objects if ob.type == "MESH"
              for v in ob.data.vertices]
        if zs:
            h = max(zs) - min(zs)
            if h > 1e-6:
                s = (args.scale_mm / 1000.0) / h
                for ob in bpy.context.scene.objects:
                    if ob.type == "MESH":
                        ob.scale = (s, s, s)
                args.loop_y *= s
                args.loop_z *= s
                print(f"scaled mesh {h*1000:.1f}mm -> {args.scale_mm:.1f}mm (s={s:.4f})")

    # ---- hardware prop (never exported as product metal) ---------------------
    # POD rule: we ship plastic only. --exact = NO props at all: the GLB IS
    # the product (printed loop is already in the mesh).
    cy, cz = args.loop_y, args.loop_z
    if fur_rgb:
        hw_rgb = tuple(min(1.0, c * 1.02 + 0.02) for c in fur_rgb)
    else:
        hw_rgb = (0.88, 0.80, 0.68)

    def _plastic_mat(name, rgb, rough=0.55):
        m = bpy.data.materials.new(name)
        m.use_nodes = True
        b = m.node_tree.nodes["Principled BSDF"]
        b.inputs["Base Color"].default_value = (*rgb, 1)
        b.inputs["Roughness"].default_value = rough
        if args.hardware == "steel":
            b.inputs["Metallic"].default_value = 1.0
            b.inputs["Roughness"].default_value = 0.28
            b.inputs["Base Color"].default_value = (0.72, 0.73, 0.78, 1)
        return m

    if args.exact:
        print("exact mode: no hardware props (canonical mesh only)")
    elif args.variant == "keychain":
        # Printed keyring: torus in the SAME plastic as the figure.
        # Customer does not need a metal split ring — this is the hardware.
        bpy.ops.mesh.primitive_torus_add(
            major_radius=0.010, minor_radius=0.0018,
            location=(0.0, cy - 0.003, cz + 0.008),
            rotation=(1.2, 0.15, 0))
        ring = bpy.context.active_object
        ring.name = "printed_keyring"
        ring.data.materials.append(_plastic_mat("ring_print", hw_rgb, 0.50))
        # short printed link bar up from the loop (keychain drop)
        bpy.ops.mesh.primitive_cylinder_add(
            radius=0.0016, depth=0.014,
            location=(0.0, cy - 0.003, cz + 0.002))
        link = bpy.context.active_object
        link.name = "printed_link"
        link.data.materials.append(ring.data.materials[0])
        print(f"printed keyring on (keychain, hardware={args.hardware}, colour={hw_rgb})")
    elif not args.no_hook:
        # Printed tree hook — same plastic family as the pet, not bare steel.
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
        cu.bevel_depth = 0.0012          # 2.4 mm printed wire (matches loop)
        cu.bevel_resolution = 6
        cu.use_fill_caps = True
        hook = bpy.data.objects.new("S_hook", cu)
        bpy.context.collection.objects.link(hook)
        hook.data.materials.append(_plastic_mat("hook_print", hw_rgb, 0.55))
        print(f"printed S-hook on (ornament, hardware={args.hardware}, colour={hw_rgb})")

    # ---- custom-request props: prefer real hat assets, else procedural -------
    if args.prop and args.prop != "none":
        prefix = f"{args.prop}-"
    elif args.hat_asset:
        prefix = "hat-"
    else:
        prefix = ""

    want_hat = ((args.prop == "santa") or bool(args.hat_asset)) and not args.exact
    hat_imported = False
    if want_hat:
        hat_path = Path(args.hat_asset) if args.hat_asset else Path(
            "data/assets/hats/oga-santa/santa_hat.fbx")
        if hat_path.exists() and hat_path.suffix.lower() in {".fbx", ".obj", ".glb", ".gltf"}:
            before = {o.name for o in bpy.context.scene.objects}
            if hat_path.suffix.lower() == ".fbx":
                bpy.ops.import_scene.fbx(filepath=str(hat_path))
            elif hat_path.suffix.lower() == ".obj":
                bpy.ops.wm.obj_import(filepath=str(hat_path))
            else:
                bpy.ops.import_scene.gltf(filepath=str(hat_path))
            new = [o for o in bpy.context.scene.objects if o.name not in before]
            hat_meshes = [o for o in new if o.type == "MESH"]
            if not hat_meshes:
                hat_meshes = [o for o in bpy.context.scene.objects
                              if o.type == "MESH" and "hat" in o.name.lower()]
            # head width from the big pet mesh
            dog = [o for o in bpy.context.scene.objects
                   if o.type == "MESH" and len(o.data.vertices) > 10000]
            head_w = 0.10
            mesh_zmax = 0.20
            if dog:
                cs = [dog[0].matrix_world @ v.co for v in dog[0].data.vertices]
                head_w = max(c.x for c in cs) - min(c.x for c in cs)
                mesh_zmax = max(c.z for c in cs)
            if hat_meshes:
                coords = []
                for o in hat_meshes:
                    coords += [o.matrix_world @ v.co for v in o.data.vertices]
                xs = [c.x for c in coords]; ys = [c.y for c in coords]
                zs = [c.z for c in coords]
                w = max(xs) - min(xs); h = max(zs) - min(zs)
                if w < 1e-6:
                    w = 0.05
                if h < 1e-6:
                    h = 0.05
                s = (head_w * 1.08) / w
                if h * s > head_w * 1.15:
                    s = (head_w * 1.15) / h
                for o in hat_meshes:
                    o.scale = (o.scale[0] * s, o.scale[1] * s, o.scale[2] * s)
                # armatures that came with the FBX
                for o in new:
                    if o.type == "ARMATURE":
                        o.scale = (s, s, s)
                bpy.context.view_layer.update()
                coords = []
                for o in hat_meshes:
                    coords += [o.matrix_world @ v.co for v in o.data.vertices]
                zmin = min(c.z for c in coords)
                ymid = sum(c.y for c in coords) / len(coords)
                dz = (mesh_zmax - 0.004) - zmin
                dy = (-0.095 * (mesh_zmax / 0.20)) - ymid
                for o in new:
                    if o.type in {"MESH", "ARMATURE"}:
                        o.location.z += dz
                        o.location.y += dy
                hat_imported = True
                # Force xmas palette on imported hats (OGA FBX often ignores PNG)
                if args.prop == "santa" or "santa" in hat_path.name.lower():
                    red = bpy.data.materials.new("hat_xmas_red")
                    red.use_nodes = True
                    rb = red.node_tree.nodes["Principled BSDF"]
                    # Dark saturated red — AgX + white-bg lights wash bright red to pink
                    rb.inputs["Base Color"].default_value = (0.38, 0.015, 0.015, 1)
                    rb.inputs["Roughness"].default_value = 0.78
                    for o in hat_meshes:
                        o.data.materials.clear()
                        o.data.materials.append(red)
                    print("hat meshes recoloured xmas red")
                print(f"hat-asset {hat_path.name}: s={s:.3f} "
                      f"dz={dz:.4f} dy={dy:.4f} brim_w={head_w*1.08*1000:.1f}mm")
        else:
            print(f"hat-asset not usable: {hat_path}")

    if want_hat and not hat_imported and args.prop == "santa":
        # procedural fallback (proportions locked to measured skull)
        zs_all = [(ob.matrix_world @ v.co)
                  for ob in bpy.context.scene.objects if ob.type == "MESH"
                  for v in ob.data.vertices]
        zmax = max(c.z for c in zs_all) if zs_all else 0.20
        ymid = -0.095 * (zmax / 0.20)
        brim_z = zmax - 0.004
        brim_r = 0.048 * (zmax / 0.20)
        cone_d = 0.095 * (zmax / 0.20)
        head = Vector((0.0, ymid, brim_z))
        bpy.ops.mesh.primitive_cone_add(
            radius1=brim_r * 0.92, radius2=0.006 * (zmax / 0.20),
            depth=cone_d,
            location=(head.x, head.y + 0.004, head.z + cone_d * 0.48))
        cone = bpy.context.active_object
        cone.name = "santa_cone"
        cone.rotation_euler = (0.22, 0.12, 0)
        red = bpy.data.materials.new("santa_red")
        red.use_nodes = True
        rb = red.node_tree.nodes["Principled BSDF"]
        rb.inputs["Base Color"].default_value = (0.72, 0.04, 0.04, 1)
        rb.inputs["Roughness"].default_value = 0.72
        cone.data.materials.append(red)
        bpy.ops.mesh.primitive_torus_add(
            major_radius=brim_r, minor_radius=0.010 * (zmax / 0.20),
            location=(head.x, head.y, head.z + 0.002))
        brim = bpy.context.active_object
        brim.name = "santa_brim"
        brim.scale = (1.0, 0.85, 1.0)
        white = bpy.data.materials.new("santa_white")
        white.use_nodes = True
        wb = white.node_tree.nodes["Principled BSDF"]
        wb.inputs["Base Color"].default_value = (0.94, 0.93, 0.90, 1)
        wb.inputs["Roughness"].default_value = 0.88
        brim.data.materials.append(white)
        bpy.ops.mesh.primitive_uv_sphere_add(
            radius=0.014 * (zmax / 0.20),
            location=(head.x + 0.012, head.y - 0.01, head.z + cone_d * 0.92))
        pomp = bpy.context.active_object
        pomp.name = "santa_pompom"
        pomp.data.materials.append(white)
        print(f"procedural santa on skull z={brim_z:.3f}")

    if args.hat_text and not args.exact:
        zs_all = [(ob.matrix_world @ v.co)
                  for ob in bpy.context.scene.objects if ob.type == "MESH"
                  for v in ob.data.vertices]
        zmax = max(c.z for c in zs_all) if zs_all else 0.20
        curve = bpy.data.curves.new("hat_text", "FONT")
        curve.body = args.hat_text
        curve.size = 0.018 * (zmax / 0.20)
        curve.extrude = 0.0008
        txt = bpy.data.objects.new("hat_text", curve)
        bpy.context.collection.objects.link(txt)
        txt.location = (0.0, -0.095 * (zmax / 0.20) - 0.035, zmax - 0.008)
        txt.rotation_euler = (1.35, 0, 0)
        gold = bpy.data.materials.new("hat_text_gold")
        gold.use_nodes = True
        gb = gold.node_tree.nodes["Principled BSDF"]
        gb.inputs["Base Color"].default_value = (0.85, 0.70, 0.25, 1)
        gb.inputs["Metallic"].default_value = 0.6
        gb.inputs["Roughness"].default_value = 0.35
        txt.data.materials.append(gold)
        print(f"hat text placed: {args.hat_text!r}")

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
    scn.render.film_transparent = False
    scn.cycles.max_bounces = 8
    scn.cycles.diffuse_bounces = 4
    scn.cycles.glossy_bounces = 4
    scn.world = bpy.data.worlds.new("w")
    scn.world.use_nodes = True
    if args.bg == "white":
        # Transparent film: world lights the model but does NOT show in the
        # frame. Composited onto pure white after render — AgX maps a 0.92
        # grey world to ~174, which is why the first marketing pass looked
        # grey instead of white.
        scn.render.film_transparent = True
        scn.world.node_tree.nodes["Background"].inputs[0].default_value = (
            0.55, 0.55, 0.58, 1)
        scn.world.node_tree.nodes["Background"].inputs[1].default_value = 0.7
    else:
        scn.world.node_tree.nodes["Background"].inputs[0].default_value = (
            0.085, 0.09, 0.10, 1)
        scn.world.node_tree.nodes["Background"].inputs[1].default_value = 1.0

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

    if args.bg == "white":
        # Product-photo lighting: flatter and dimmer than the first white
        # pass. Cream fur blows out under a hot key (56-78% of product px
        # were >250); keep midtones alive so the fur texture reads.
        scn.view_settings.exposure = -0.35
        light("key", (0.28, -0.28, 0.40), (0, -0.02, 0.10), 48, 0.7)
        light("fill", (-0.32, -0.22, 0.18), (0, -0.02, 0.10), 42, 1.1)
        light("rim", (-0.08, 0.38, 0.32), (0, 0.02, 0.14), 28, 0.5)
        light("bounce", (0.35, -0.28, 0.00), (0, -0.02, 0.08), 30, 1.0)
        # Low camera-side fill — lifts the flank that goes pitch-black in
        # hook close-ups (normals/UV-atlas wedge, see docs/rendering.md).
        light("flank", (0.08, -0.40, 0.06), (0, -0.02, 0.10), 36, 0.9)
        light("under", (-0.12, -0.18, -0.08), (0, -0.02, 0.06), 26, 0.8)
        # soft overhead — kills hard wedges on the back without heating fur
        light("top", (0.00, -0.05, 0.55), (0, -0.02, 0.10), 26, 1.3)
    else:
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
    body = (0, -0.005, 0.095)               # figure centre (slightly lower)
    if args.scale_mm > 0:
        # keep framing sensible on a scaled production mesh
        body = (0, -0.005, 0.095 * (args.scale_mm / 200.0))
        hook_close = (0, cy, cz + 0.004)
    else:
        hook_close = (0, cy, cz + 0.004)    # printed loop + hardware prop
    hook_top = (0.0, cy, cz + 0.018)
    hang_tgt = (0.0, cy * 0.5, (cz + 0.018) * 0.45)

    if args.prop and args.prop != "none":
        # custom-request previews must not clobber the SKU marketing set
        prefix = f"{args.prop}-"
    else:
        prefix = ""

    if args.shots == "exact" or (args.exact and args.shots in ("marketing", "keychain", "standard")):
        # Canonical product set — the mesh, nothing else added.
        # Loop lives on the back of the GLB; no S-hook, no keyring, no grade.
        shot(out_dir / "prod-front.png", body, (0.00, -0.46, 0.14), 58)
        shot(out_dir / "prod-back.png", body, (0.00, 0.46, 0.14), 58)
        shot(out_dir / "prod-side.png", body, (-0.46, 0.00, 0.14), 58)
        shot(out_dir / "prod-hero.png", body, (0.30, -0.34, 0.24), 60)
        shot(out_dir / "prod-loop.png", hook_close, (0.16, -0.14, 0.09), 68)
        qc_files = ("prod-front.png", "prod-back.png", "prod-side.png",
                    "prod-hero.png", "prod-loop.png")
    elif args.shots == "keychain":
        # White-bg keychain set — split ring on the back, no tree hook.
        shot(out_dir / f"{prefix}kc-front.png", body, (0.00, -0.46, 0.14), 58)
        shot(out_dir / f"{prefix}kc-back.png", body, (0.00, 0.46, 0.14), 58)        # ring side
        shot(out_dir / f"{prefix}kc-hero.png", body, (0.30, -0.34, 0.24), 60)
        shot(out_dir / f"{prefix}kc-ring-close.png", hook_close, (0.14, -0.12, 0.08), 70)
        shot(out_dir / f"{prefix}kc-ring-side.png", hook_close, (0.16, 0.06, 0.06), 70)
        shot(out_dir / f"{prefix}kc-left.png", body, (-0.46, 0.00, 0.14), 58)
        qc_files = (
            f"{prefix}kc-front.png", f"{prefix}kc-back.png", f"{prefix}kc-hero.png",
            f"{prefix}kc-ring-close.png", f"{prefix}kc-ring-side.png", f"{prefix}kc-left.png",
        )
    elif args.shots == "marketing":
        # White-bg marketing set: every angle that shows the hanging loop.
        # Loop sits on the back (+Y); hook prop threads through from behind.
        shot(out_dir / f"{prefix}mkt-front.png", body, (0.00, -0.46, 0.14), 58)
        shot(out_dir / f"{prefix}mkt-back.png", body, (0.00, 0.46, 0.14), 58)       # loop side
        shot(out_dir / f"{prefix}mkt-left.png", body, (-0.46, 0.00, 0.14), 58)
        shot(out_dir / f"{prefix}mkt-right.png", body, (0.46, 0.00, 0.14), 58)
        shot(out_dir / f"{prefix}mkt-hero.png", body, (0.30, -0.34, 0.24), 60)      # 3/4
        # ornament hang — 3/4 + pure side, product fills frame, air above hook
        shot(out_dir / f"{prefix}mkt-hang.png", body, (0.26, -0.40, 0.20), 58)
        shot(out_dir / f"{prefix}mkt-hang-side.png", (0.0, -0.02, 0.115), (0.42, 0.05, 0.07), 58)
        # close-ups — flank/under/top fills lift the body behind the loop
        shot(out_dir / f"{prefix}mkt-hook-close.png", hook_close, (0.16, -0.14, 0.09), 68)
        shot(out_dir / f"{prefix}mkt-hook-side.png", hook_close, (0.18, 0.06, 0.06), 68)
        qc_files = tuple(
            f"{prefix}{n}" for n in (
                "mkt-front.png", "mkt-back.png", "mkt-left.png", "mkt-right.png",
                "mkt-hero.png", "mkt-hang.png", "mkt-hang-side.png",
                "mkt-hook-close.png", "mkt-hook-side.png",
            ))
    else:
        shot(out_dir / f"{prefix}detail.png", hook_close, (0.10, -0.055, 0.025), 85)
        shot(out_dir / f"{prefix}hero.png", body, (0.317, -0.384, 0.234), 58)
        qc_files = (f"{prefix}detail.png", f"{prefix}hero.png")

    # ---- white-bg composite ---------------------------------------------------
    # Transparent film → paste onto pure 255 white. Also a mild saturation
    # lift on the product pixels so AgX does not leave the fur anemic.
    if args.bg == "white":
        import shutil
        import subprocess
        py = shutil.which("python3") or "/usr/bin/python3"
        comp = (
            "import sys\n"
            "from PIL import Image, ImageEnhance, ImageChops\n"
            "src, dst = sys.argv[1], sys.argv[2]\n"
            "im = Image.open(src)\n"
            "if im.mode != 'RGBA':\n"
            "    im = im.convert('RGBA')\n"
            "bg = Image.new('RGB', im.size, (255, 255, 255))\n"
            "bg.paste(im, mask=im.getchannel('A'))\n"
            "bg = ImageEnhance.Color(bg).enhance(1.12)\n"
            "bg = ImageEnhance.Contrast(bg).enhance(1.04)\n"
            "bg.save(dst)\n"
        )
        for f in qc_files:
            p = out_dir / f
            if not p.exists():
                continue
            tmp = p.with_suffix(".rgba.png")
            p.replace(tmp)
            run = subprocess.run(
                [py, "-c", comp, str(tmp), str(p)],
                capture_output=True, text=True)
            if run.returncode != 0:
                print(f"composite {f}: FAILED {(run.stderr or '').strip()[-200:]}")
                tmp.replace(p)
            else:
                tmp.unlink(missing_ok=True)
                print(f"composite {f}: white + sat/contrast")

    # ---- QC on the outputs ---------------------------------------------------
    # Blender's bundled Python has no PIL — run the check with system python3.
    import shutil
    import subprocess
    helper = (
        "import sys;from PIL import Image,ImageStat;"
        "im=Image.open(sys.argv[1]);"
        # white-bg QC: sample centre, drop near-white bg pixels so the pure
        # composite does not drown the product in false 'blown' pixels
        "w,h=im.size;"
        "im=im.crop((int(w*0.15),int(h*0.15),int(w*0.85),int(h*0.85))).convert('RGB');"
        "px=list(im.getdata());"
        "prod=[(r,g,b) for r,g,b in px if not (r>242 and g>242 and b>238)];"
        "prod=prod or px;"
        "blown=100*sum(1 for r,g,b in prod if r>250 and g>235 and b>210)/len(prod);"
        "black=100*sum(1 for r,g,b in prod if (r+g+b)/3<40)/len(prod);"
        "mean=sum((r+g+b)/3 for r,g,b in prod)/len(prod);"
        "print(f'{mean:.1f} {blown:.2f} {black:.1f}')"
    )
    py = shutil.which("python3") or "/usr/bin/python3"
    for f in qc_files:
        run = subprocess.run([py, "-c", helper, str(out_dir / f)],
                             capture_output=True, text=True)
        if run.returncode != 0:
            print(f"QC {f}: skipped ({(run.stderr or 'helper failed').strip().splitlines()[-1]})")
            continue
        mean, blown, black = run.stdout.split()
        if args.bg == "white":
            # product pixels only: want detail (low blown) and no black wedge
            verdict = (
                "PASS" if (float(blown) < 25 and float(black) < 2)
                else "CHECK"
            )
        else:
            verdict = (
                "PASS" if (float(blown) < 2 and float(black) < 3)
                else "CHECK"
            )
        print(f"QC {f}: mean={mean} blown={blown}% black={black}% {verdict}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
