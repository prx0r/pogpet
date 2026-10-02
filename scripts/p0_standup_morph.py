#!/usr/bin/env python3
"""P0 standup with REAL mesh lipsync — jawOpen shape key driven by audio envelope.

    blender --background --python scripts/p0_standup_morph.py -- \
        --in data/uploads/chibi-figure-hook-jaw.glb \
        --wav data/videos/p0_work/set.wav \
        --out data/videos/p0_standup_morph.mp4 \
        --name Buster

Freaktown doctrine: mouth listens to audible voice energy. Here the energy
bakes into the GLB's jawOpen morph (injected by scripts/add_jaw_morph.py)
so the dog's muzzle actually moves. CPU only. 0 Meshy credits.
"""
from __future__ import annotations

import argparse
import math
import struct
import subprocess
import sys
import wave
from pathlib import Path


def parse_args(argv):
    p = argparse.ArgumentParser()
    p.add_argument("--in", dest="src", required=True)
    p.add_argument("--wav", dest="wav", required=True)
    p.add_argument("--out", dest="out", required=True)
    p.add_argument("--name", default="Buster")
    p.add_argument("--size", type=int, default=720, help="width; height = size*16/9")
    p.add_argument("--fps", type=int, default=16, help="lower = faster CPU bake")
    p.add_argument("--samples", type=int, default=16)
    argv = argv[argv.index("--") + 1:] if "--" in argv else argv[1:]
    return p.parse_args(argv)


def envelope(path: Path, fps: int):
    with wave.open(str(path), "rb") as w:
        n, sw, ch, rate = w.getnframes(), w.getsampwidth(), w.getnchannels(), w.getframerate()
        raw = w.readframes(n)
    if sw != 2:
        raise SystemExit(f"need 16-bit wav, got width {sw}")
    samples = struct.unpack("<" + "h" * (len(raw) // 2), raw)
    if ch > 1:
        samples = samples[::ch]
    total = max(1, len(samples))
    dur = total / float(rate)
    nframes = max(1, int(math.ceil(dur * fps)))
    env = []
    for i in range(nframes):
        a = int(i * rate / fps)
        b = int(min(total, (i + 1) * rate / fps))
        if b <= a:
            env.append(0.0)
            continue
        chunk = samples[a:b]
        rms = math.sqrt(sum(s * s for s in chunk) / len(chunk)) / 32768.0
        env.append(min(1.0, rms * 3.0))
    out, prev = [], 0.0
    for v in env:
        prev = prev * 0.55 + v * 0.45
        out.append(prev)
    peak = max(out) or 1.0
    return [0.0 if v < 0.04 else min(1.0, v / peak) for v in out]


def main() -> int:
    args = parse_args(sys.argv)
    import bpy

    src = Path(args.src)
    wav = Path(args.wav)
    out_mp4 = Path(args.out)
    w, h = args.size, int(args.size * 16 / 9)
    env = envelope(wav, args.fps)
    print(f"envelope frames={len(env)} size={w}x{h}", flush=True)

    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=str(src))

    # find mesh + shape keys (glTF morph targets import as shape keys)
    mesh_obj = None
    for ob in bpy.context.scene.objects:
        if ob.type == "MESH" and len(ob.data.vertices) > 1000:
            mesh_obj = ob
            break
    if mesh_obj is None:
        raise SystemExit("no mesh in GLB")
    print("mesh", mesh_obj.name, "verts", len(mesh_obj.data.vertices), flush=True)

    # ensure jawOpen shape key exists
    if mesh_obj.data.shape_keys is None:
        bpy.context.view_layer.objects.active = mesh_obj
        mesh_obj.select_set(True)
        bpy.ops.object.shape_key_add(from_mix=False)
    kb = mesh_obj.data.shape_keys
    jaw = None
    for k in kb.key_blocks:
        if "jaw" in k.name.lower():
            jaw = k
            break
    if jaw is None:
        # build jaw from morph target if importer named it differently
        jaw = kb.key_blocks[0]
        jaw.name = "jawOpen"
    print("shape key", jaw.name, flush=True)

    # stage: warm white world + simple floor
    scn = bpy.context.scene
    scn.render.engine = "CYCLES"
    scn.cycles.device = "CPU"
    scn.cycles.samples = args.samples
    scn.cycles.use_denoising = True
    scn.render.resolution_x = w
    scn.render.resolution_y = h
    scn.render.fps = args.fps
    scn.view_settings.view_transform = "Standard"
    scn.world = bpy.data.worlds.new("w")
    scn.world.use_nodes = True
    bg = scn.world.node_tree.nodes["Background"]
    bg.inputs[0].default_value = (0.95, 0.93, 0.88, 1)
    bg.inputs[1].default_value = 0.8

    # lights
    from mathutils import Vector

    def light(name, loc, energy, size):
        ld = bpy.data.lights.new(name, "AREA")
        ld.energy = energy
        ld.size = size
        lo = bpy.data.objects.new(name, ld)
        bpy.context.collection.objects.link(lo)
        lo.location = loc
        lo.rotation_euler = (Vector((0, 0, 0.1)) - Vector(loc)).to_track_quat("-Z", "Y").to_euler()
        lo.visible_camera = False

    light("key", (0.4, -0.5, 0.5), 80, 0.6)
    light("fill", (-0.4, -0.3, 0.3), 50, 0.8)
    light("rim", (0.1, 0.4, 0.4), 40, 0.5)

    # mic prop (simple capsule)
    bpy.ops.mesh.primitive_cylinder_add(radius=0.02, depth=0.08, location=(0.22, -0.05, 0.12))
    mic = bpy.context.active_object
    mic.name = "mic"
    mm = bpy.data.materials.new("mic")
    mm.use_nodes = True
    mm.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.05, 0.05, 0.06, 1)
    mic.data.materials.append(mm)
    bpy.ops.mesh.primitive_cylinder_add(radius=0.004, depth=0.22, location=(0.22, -0.05, 0.0))
    stand = bpy.context.active_object
    stand.data.materials.append(mm)

    # camera vertical
    cam_d = bpy.data.cameras.new("c")
    cam = bpy.data.objects.new("c", cam_d)
    bpy.context.collection.objects.link(cam)
    cam.location = (0.05, -0.75, 0.18)
    cam_d.lens = 55
    cam.rotation_euler = (Vector((0, 0, 0.12)) - cam.location).to_track_quat("-Z", "Y").to_euler()
    scn.camera = cam
    bpy.context.view_layer.update()

    frames_dir = out_mp4.parent / (out_mp4.stem + "_frames")
    frames_dir.mkdir(parents=True, exist_ok=True)
    for i, v in enumerate(env):
        jaw.value = v
        # subtle head bob via object z
        mesh_obj.location.z = 0.01 * math.sin(i / max(1, args.fps) * 2.4)
        bpy.context.view_layer.update()
        scn.render.filepath = str(frames_dir / f"f{i:04d}.png")
        bpy.ops.render.render(write_still=True)
        if i % 8 == 0 or i == len(env) - 1:
            print(f"frame {i+1}/{len(env)} jaw={v:.2f}", flush=True)

    pattern = str(frames_dir / "f%04d.png")
    cmd = [
        "ffmpeg", "-y", "-framerate", str(args.fps), "-i", pattern,
        "-i", str(wav), "-c:v", "libx264", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "160k", "-shortest", "-movflags", "+faststart",
        str(out_mp4),
    ]
    print("ffmpeg…", flush=True)
    subprocess.run(cmd, check=True, capture_output=True)
    print("OK", out_mp4, out_mp4.stat().st_size, flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
