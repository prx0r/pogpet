#!/usr/bin/env python3
"""Shareable standup video — real jawOpen mesh lipsync, CPU-only, finishes fast.

    python3 scripts/pose_lipsync.py --name Buster --voice ryan

1. Render N jaw poses from the morph GLB (Blender, once)
2. Assemble vertical frames from those poses using the audio envelope
3. Mux edge-tts audio → shareable mp4 for the Videos feed / pogtown wedge
"""
from __future__ import annotations

import argparse
import asyncio
import math
import struct
import subprocess
import wave
from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter

ROOT = Path(__file__).resolve().parent.parent
GLB = ROOT / "data" / "uploads" / "chibi-figure-hook-jaw.glb"
BLENDER = "/home/ubuntu/opt/blender-4.2.9-linux-x64/blender"
VW, VH = 1080, 1920
FPS = 15
POSES = 9  # jaw 0..1


def pick_font(size: int):
    for fp in (
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    ):
        if Path(fp).exists():
            try:
                from PIL import ImageFont
                return ImageFont.truetype(fp, size)
            except OSError:
                pass
    from PIL import ImageFont
    return ImageFont.load_default()


async def tts(text: str, voice: str, out_wav: Path) -> None:
    import edge_tts
    vid = {
        "ryan": "en-GB-RyanNeural",
        "andrew": "en-GB-AndrewNeural",
        "jenny": "en-US-JennyNeural",
        "libby": "en-GB-LibbyNeural",
    }.get(voice, voice)
    raw = out_wav.with_suffix(".edge.mp3")
    await edge_tts.Communicate(text, vid).save(str(raw))
    subprocess.run(
        ["ffmpeg", "-y", "-i", str(raw), "-ac", "1", "-ar", "16000",
         "-c:a", "pcm_s16le", str(out_wav)],
        check=True, capture_output=True,
    )


def envelope(path: Path, fps: int = FPS) -> list[float]:
    with wave.open(str(path), "rb") as w:
        n, sw, ch, rate = w.getnframes(), w.getsampwidth(), w.getnchannels(), w.getframerate()
        raw = w.readframes(n)
    samples = struct.unpack("<" + "h" * (len(raw) // 2), raw)
    if ch > 1:
        samples = samples[::ch]
    total = max(1, len(samples))
    nframes = max(1, int(math.ceil(total / rate * fps)))
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


def blender_poses(glb: Path, outdir: Path, n_poses: int, samples: int = 24) -> list[Path]:
    outdir.mkdir(parents=True, exist_ok=True)
    script = outdir / "_poses.py"
    script.write_text(f'''
import bpy, math
from mathutils import Vector
from pathlib import Path
glb = r"{glb}"
outdir = Path(r"{outdir}")
n_poses = {n_poses}
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=glb)
mesh_obj = None
for ob in bpy.context.scene.objects:
    if ob.type == "MESH" and len(ob.data.vertices) > 1000:
        mesh_obj = ob
        break
assert mesh_obj, "no mesh"
if mesh_obj.data.shape_keys is None:
    bpy.context.view_layer.objects.active = mesh_obj
    mesh_obj.select_set(True)
    bpy.ops.object.shape_key_add(from_mix=False)
jaw = None
for k in mesh_obj.data.shape_keys.key_blocks:
    if "jaw" in k.name.lower():
        jaw = k
        break
if jaw is None:
    jaw = mesh_obj.data.shape_keys.key_blocks[0]
    jaw.name = "jawOpen"
print("jaw", jaw.name)

scn = bpy.context.scene
scn.render.engine = "CYCLES"
scn.cycles.device = "CPU"
scn.cycles.samples = {samples}
scn.cycles.use_denoising = True
scn.render.resolution_x = {VW}
scn.render.resolution_y = {VH}
scn.render.film_transparent = True
scn.view_settings.view_transform = "Standard"
scn.world = bpy.data.worlds.new("w")
scn.world.use_nodes = True
scn.world.node_tree.nodes["Background"].inputs[0].default_value = (0.85,0.85,0.85,1)
scn.world.node_tree.nodes["Background"].inputs[1].default_value = 0.6

def light(name, loc, e, s):
    ld = bpy.data.lights.new(name, "AREA"); ld.energy=e; ld.size=s
    lo = bpy.data.objects.new(name, ld); bpy.context.collection.objects.link(lo)
    lo.location = loc
    lo.rotation_euler = (Vector((0,0,0.1))-Vector(loc)).to_track_quat("-Z","Y").to_euler()
    lo.visible_camera = False
light("key",(0.35,-0.45,0.45),70,0.55)
light("fill",(-0.35,-0.25,0.25),45,0.7)
light("rim",(0.05,0.35,0.35),35,0.45)

cam_d=bpy.data.cameras.new("c"); cam=bpy.data.objects.new("c",cam_d)
bpy.context.collection.objects.link(cam)
cam.location=(0.02,-0.72,0.16); cam_d.lens=52
cam.rotation_euler=(Vector((0,0,0.12))-cam.location).to_track_quat("-Z","Y").to_euler()
scn.camera=cam
bpy.context.view_layer.update()

for i in range(n_poses):
    v = i/(n_poses-1) if n_poses>1 else 0.0
    jaw.value = v
    bpy.context.view_layer.update()
    scn.render.filepath = str(outdir/f"pose_{{i:02d}}.png")
    bpy.ops.render.render(write_still=True)
    print("pose", i, "jaw", round(v,2), flush=True)
print("POSES_DONE")
''')
    log = outdir / "_poses.log"
    with log.open("w") as lf:
        subprocess.run([BLENDER, "--background", "--python", str(script)],
                       cwd=str(ROOT), stdout=lf, stderr=subprocess.STDOUT)
    poses = sorted(outdir.glob("pose_*.png"))
    print(f"poses rendered: {len(poses)}")
    if not poses:
        print(log.read_text()[-800:])
        raise SystemExit("pose render failed")
    return poses


def stage_bg(w: int, h: int) -> Image.Image:
    im = Image.new("RGB", (w, h), (244, 241, 234))
    d = ImageDraw.Draw(im)
    d.ellipse([w*0.12, h*0.52, w*0.88, h*0.95], fill=(252, 250, 246))
    d.rectangle([0, int(h*0.78), w, h], fill=(230, 224, 212))
    d.line([(0, int(h*0.78)), (w, int(h*0.78))], fill=(200, 188, 168), width=4)
    return im


def draw_mic(d: ImageDraw.ImageDraw, cx: int, cy: int, s: float = 1.0) -> None:
    d.line([(cx, cy+int(40*s)), (cx, cy+int(170*s))], fill=(50,50,56), width=max(3,int(7*s)))
    d.line([(cx-int(34*s), cy+int(170*s)), (cx+int(34*s), cy+int(170*s))],
           fill=(50,50,56), width=max(3,int(6*s)))
    rr=int(36*s); cy0=cy-int(48*s)
    d.ellipse([cx-rr,cy0-rr,cx+rr,cy0+rr], outline=(70,70,78), width=max(2,int(4*s)))
    r=int(26*s)
    d.ellipse([cx-r,cy0-r,cx+r,cy0+r], fill=(35,35,40))
    d.ellipse([cx-r+5,cy0-r+5,cx+r-5,cy0+r-5], fill=(100,100,110))
    d.ellipse([cx-4,cy0-r-12,cx+4,cy0-r-4], fill=(200,40,40))


def draw_plate(img: Image.Image, name: str) -> None:
    w,h=img.size; d=ImageDraw.Draw(img)
    bar_h=int(h*0.13)
    bar=Image.new("RGBA", img.size, (0,0,0,0))
    bd=ImageDraw.Draw(bar)
    bd.rectangle([0,h-bar_h,w,h], fill=(255,255,255,235))
    bd.rectangle([0,h-bar_h,w,h-bar_h+8], fill=(196,137,26,255))
    img.paste(bar,(0,0),bar)
    d=ImageDraw.Draw(img)
    d.text((52,h-bar_h+28), name.upper(), font=pick_font(int(h*0.042)), fill=(18,18,18))
    d.text((52,h-bar_h+28+int(h*0.046)), "stand-up · mic on", font=pick_font(int(h*0.026)), fill=(100,100,100))
    d.text((w-180,h-bar_h+28), "oddhobb", font=pick_font(22), fill=(196,137,26))


def assemble(poses: list[Path], env: list[float], outdir: Path, name: str) -> list[Path]:
    outdir.mkdir(parents=True, exist_ok=True)
    # load poses as RGBA, paste onto transparent canvas same size as stage
    loaded = []
    for p in poses:
        im = Image.open(p).convert("RGBA")
        # fit into stage content box
        box = int(VW*0.78)
        im = im.resize((box, box), Image.Resampling.LANCZOS)
        loaded.append(im)
    frames = []
    n = len(loaded)
    for i, v in enumerate(env):
        stage = stage_bg(VW, VH)
        t = i / max(1, FPS)
        bob = int(math.sin(t*2.4)*6)
        # map envelope to pose index
        pi = int(round(v * (n-1)))
        pi = max(0, min(n-1, pi))
        dog = loaded[pi]
        # slight breathe
        br = 1.0 + 0.008*math.sin(t*3.1)
        sz = int(dog.size[0]*br)
        dog_i = dog.resize((sz,sz), Image.Resampling.BILINEAR)
        ang = math.sin(t*1.7)*1.0
        dog_i = dog_i.rotate(ang, resample=Image.Resampling.BICUBIC)
        dx=(VW-sz)//2; dy=int(VH*0.28)+bob
        stage.paste(dog_i,(dx,dy),dog_i)
        work=stage.copy()
        draw_mic(ImageDraw.Draw(work), int(VW*0.82), int(VH*0.52), 1.3)
        draw_plate(work, name)
        if v>0.55:
            ImageDraw.Draw(work).text((48,int(VH*0.12)), "ha ha ha", font=pick_font(36), fill=(196,137,26))
        fp=outdir/f"f{i:04d}.png"
        work.save(fp,"PNG")
        frames.append(fp)
        if i%20==0 or i==len(env)-1:
            print(f"frame {i+1}/{len(env)} pose={pi} open={v:.2f}", flush=True)
    return frames


def mux(frames: list[Path], wav: Path, out: Path) -> None:
    pattern=str(frames[0].parent/"f%04d.png")
    cmd=["ffmpeg","-y","-framerate",str(FPS),"-i",pattern,"-i",str(wav),
         "-c:v","libx264","-pix_fmt","yuv420p","-c:a","aac","-b:a","160k",
         "-shortest","-movflags","+faststart",str(out)]
    subprocess.run(cmd, check=True, capture_output=True)
    print("muxed", out, out.stat().st_size)


DEFAULT_SCRIPT = (
    "Evening. I'm the family dog. Yes, that dog. "
    "They said I'd guard the house. I guard the sofa. Different skillset. "
    "Walkies? I thought you said walk-aways. I walked away. For six hours. "
    "They bought me a smart collar. It tracked me to the bin. Twice. "
    "I have four beds. I sleep on the charging cable. You're welcome. "
    "They say I'm a good boy. Correct. That's the whole joke. Good night."
)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--name", default="Buster")
    ap.add_argument("--voice", default="ryan")
    ap.add_argument("--script", default=DEFAULT_SCRIPT)
    ap.add_argument("--glb", default=str(GLB))
    ap.add_argument("--work", default=str(ROOT/"data"/"videos"/"pose_work"))
    ap.add_argument("--out", default=str(ROOT/"data"/"videos"/"p0_standup.mp4"))
    args = ap.parse_args()
    work=Path(args.work); work.mkdir(parents=True, exist_ok=True)
    if not Path(args.glb).exists():
        raise SystemExit(f"missing jaw GLB: {args.glb} (run scripts/add_jaw_morph.py)")
    wav=work/"set.wav"
    print("TTS…", flush=True)
    asyncio.run(tts(args.script, args.voice, wav))
    env=envelope(wav)
    print("envelope", len(env), "peak", round(max(env),2), flush=True)
    pose_dir=work/"poses"
    poses=blender_poses(Path(args.glb), pose_dir, POSES, samples=20)
    frames=assemble(poses, env, work/"frames", args.name)
    out=Path(args.out)
    mux(frames, wav, out)
    for f in frames: f.unlink(missing_ok=True)
    print("OK", out, flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
