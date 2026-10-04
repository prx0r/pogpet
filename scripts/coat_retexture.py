#!/usr/bin/env python3
"""Coat retexture presets — controlled patterns on the canonical mesh.

    blender --background --python scripts/coat_retexture.py -- \
        --in data/uploads/chibi-figure-hook.glb \
        --out data/marketing/patterns \
        --coat chocolate --pattern spots --size 900

Patterns (shader-only, no new Meshy):
  solid | spots | stripes | fairisle
0 Meshy credits. Production multi-colour = live farm quote.
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
    p.add_argument("--coat", default="chocolate")
    p.add_argument("--pattern", default="spots", choices=("solid", "spots", "stripes", "fairisle"))
    p.add_argument("--size", type=int, default=900)
    p.add_argument("--sat", type=float, default=1.40)
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


def extract_texture(glb_path: Path) -> Path:
    out = glb_path.with_suffix(".texture.jpg")
    if out.exists() and out.stat().st_size > 0:
        return out
    raw = glb_path.read_bytes()
    clen, _ = struct.unpack("<II", raw[12:20])
    js = json.loads(raw[20 : 20 + clen])
    bin_off = 20 + clen
    blen, _ = struct.unpack("<II", raw[bin_off : bin_off + 8])
    blob = raw[bin_off + 8 : bin_off + 8 + blen]
    img = js["images"][0]
    bv = js["bufferViews"][img["bufferView"]]
    off = bv.get("byteOffset", 0)
    out.write_bytes(blob[off : off + bv["byteLength"]])
    return out


def main() -> int:
    args = parse_args(sys.argv)
    import bpy
    from mathutils import Vector

    src = Path(args.src)
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    tex = extract_texture(src)
    coat = COAT_HEX.get(args.coat, COAT_HEX["chocolate"])

    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=str(src))

    img = bpy.data.images.load(str(tex), check_existing=True)
    mat = bpy.data.materials.new("coat_tex")
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

    # base = texture × coat colour
    mult = nt.nodes.new("ShaderNodeMix")
    mult.data_type = "RGBA"
    mult.blend_type = "MULTIPLY"
    mult.inputs["Factor"].default_value = 1.0
    mult.inputs[7].default_value = (*coat, 1.0)
    nt.links.new(hsv.outputs["Color"], mult.inputs[6])
    base_out = mult.outputs[2]

    if args.pattern == "solid":
        nt.links.new(base_out, bsdf.inputs["Base Color"])
    elif args.pattern == "spots":
        vor = nt.nodes.new("ShaderNodeTexVoronoi")
        vor.inputs["Scale"].default_value = 18.0
        ramp = nt.nodes.new("ShaderNodeValToRGB")
        ramp.color_ramp.elements[0].position = 0.25
        ramp.color_ramp.elements[1].position = 0.45
        # dark spots
        dark = (coat[0] * 0.35, coat[1] * 0.3, coat[2] * 0.3, 1.0)
        mix = nt.nodes.new("ShaderNodeMix")
        mix.data_type = "RGBA"
        mix.blend_type = "MIX"
        mix.inputs[7].default_value = dark
        nt.links.new(vor.outputs["Distance"], ramp.inputs["Fac"])
        nt.links.new(ramp.outputs["Color"], mix.inputs["Factor"])
        nt.links.new(base_out, mix.inputs[6])
        nt.links.new(mix.outputs[2], bsdf.inputs["Base Color"])
    elif args.pattern == "stripes":
        wave = nt.nodes.new("ShaderNodeTexWave")
        wave.inputs["Scale"].default_value = 8.0
        wave.wave_type = "BANDS"
        ramp = nt.nodes.new("ShaderNodeValToRGB")
        ramp.color_ramp.elements[0].position = 0.4
        ramp.color_ramp.elements[1].position = 0.6
        stripe = (coat[0] * 0.55, coat[1] * 0.5, coat[2] * 0.45, 1.0)
        mix = nt.nodes.new("ShaderNodeMix")
        mix.data_type = "RGBA"
        mix.blend_type = "MIX"
        mix.inputs[7].default_value = stripe
        nt.links.new(wave.outputs["Fac"], ramp.inputs["Fac"])
        nt.links.new(ramp.outputs["Color"], mix.inputs["Factor"])
        nt.links.new(base_out, mix.inputs[6])
        nt.links.new(mix.outputs[2], bsdf.inputs["Base Color"])
    else:  # fairisle
        chk = nt.nodes.new("ShaderNodeTexChecker")
        chk.inputs["Scale"].default_value = 12.0
        chk.inputs["Color1"].default_value = (*coat, 1.0)
        chk.inputs["Color2"].default_value = (coat[0] * 0.5, coat[1] * 0.45, coat[2] * 0.4, 1.0)
        mix = nt.nodes.new("ShaderNodeMix")
        mix.data_type = "RGBA"
        mix.blend_type = "MULTIPLY"
        mix.inputs["Factor"].default_value = 0.55
        nt.links.new(chk.outputs["Color"], mix.inputs[6])
        nt.links.new(base_out, mix.inputs[7])
        nt.links.new(mix.outputs[2], bsdf.inputs["Base Color"])

    bsdf.inputs["Roughness"].default_value = 0.65
    for ob in list(bpy.context.scene.objects):
        if ob.type == "MESH" and len(ob.data.vertices) > 100:
            ob.data.materials.clear()
            ob.data.materials.append(mat)

    scn = bpy.context.scene
    scn.render.engine = "CYCLES"
    scn.cycles.device = "CPU"
    scn.cycles.samples = 20
    scn.cycles.use_denoising = False  # this Blender build has no OIDN
    scn.render.resolution_x = args.size
    scn.render.resolution_y = args.size
    scn.render.film_transparent = True
    scn.view_settings.view_transform = "Standard"
    scn.world = bpy.data.worlds.new("w")
    scn.world.use_nodes = True
    scn.world.node_tree.nodes["Background"].inputs[0].default_value = (0.9, 0.9, 0.9, 1)

    def light(name, loc, e, s):
        ld = bpy.data.lights.new(name, "AREA")
        ld.energy, ld.size = e, s
        lo = bpy.data.objects.new(name, ld)
        bpy.context.collection.objects.link(lo)
        lo.location = loc
        lo.rotation_euler = (Vector((0, 0, 0.1)) - Vector(loc)).to_track_quat("-Z", "Y").to_euler()
        lo.visible_camera = False

    light("key", (0.35, -0.45, 0.45), 70, 0.55)
    light("fill", (-0.35, -0.25, 0.25), 45, 0.7)

    cam_d = bpy.data.cameras.new("c")
    cam = bpy.data.objects.new("c", cam_d)
    bpy.context.collection.objects.link(cam)
    cam.location = (0.05, -0.7, 0.16)
    cam_d.lens = 55
    cam.rotation_euler = (Vector((0, 0, 0.12)) - cam.location).to_track_quat("-Z", "Y").to_euler()
    scn.camera = cam
    bpy.context.view_layer.update()

    dest = outdir / f"coat-{args.coat}-{args.pattern}-hero.png"
    scn.render.filepath = str(dest)
    bpy.ops.render.render(write_still=True)
    print("wrote", dest, dest.stat().st_size)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
