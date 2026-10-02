#!/usr/bin/env python3
"""P0 standup — dog does stand-up on a vertical stage. CPU only.

    python3 scripts/p0_standup.py [--name Max] [--voice ryan] [--out DIR]

Freaktown-shaped chain, oddhobb dog:
  script → edge-tts → envelope → frames (white stage + mouth + mic) → mp4

0 Meshy credits. No GPU. Mouth = audio energy on the muzzle (GLB has no morphs).
"""
from __future__ import annotations

import argparse
import asyncio
import math
import os
import struct
import subprocess
import sys
import wave
from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parent.parent
HERO = ROOT / "data" / "productimg" / "prod" / "prod-hero.png"
OUT_DEFAULT = ROOT / "data" / "videos"
VW, VH = 1080, 1920
FPS = 24

# Chibi face box on prod-hero (relative) — muzzle sits here
FACE = (0.42, 0.34, 0.58, 0.48)  # l, t, r, b

SCRIPT_LINES = [
    "Evening. I'm the family dog. Yes, that dog.",
    "They said I'd guard the house. I guard the sofa. Different skillset.",
    "Walkies? I thought you said walk-aways. I walked away. For six hours.",
    "My human works from home. So do I. From the floor. Under the desk.",
    "They bought me a smart collar. It tracked me to the bin. Twice.",
    "I have four beds. I sleep on the charging cable. You're welcome.",
    "They say I'm a good boy. Correct. That's the whole joke. Good night.",
]


def pick_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for fp in (
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ):
        if Path(fp).exists():
            try:
                return ImageFont.truetype(fp, size)
            except OSError:
                pass
    return ImageFont.load_default()


async def tts(text: str, voice: str, out_wav: Path) -> None:
    import edge_tts
    voice_id = {
        "ryan": "en-GB-RyanNeural",
        "andrew": "en-GB-AndrewNeural",
        "jenny": "en-US-JennyNeural",
        "libby": "en-GB-LibbyNeural",
    }.get(voice, voice)
    raw = out_wav.with_suffix(".edge.mp3")
    comm = edge_tts.Communicate(text, voice_id)
    await comm.save(str(raw))
    # edge-tts writes mp3 — decode to PCM wav for envelope + aac mux
    subprocess.run(
        ["ffmpeg", "-y", "-i", str(raw), "-ac", "1", "-ar", "16000",
         "-c:a", "pcm_s16le", str(out_wav)],
        check=True, capture_output=True,
    )


def envelope_from_wav(path: Path, fps: int = FPS) -> list[float]:
    """Per-frame RMS 0..1, smoothed + lightly gated (freaktown jaw idea)."""
    with wave.open(str(path), "rb") as w:
        n = w.getnframes()
        sw = w.getsampwidth()
        ch = w.getnchannels()
        rate = w.getframerate()
        raw = w.readframes(n)
    if sw == 2:
        samples = struct.unpack("<" + "h" * (len(raw) // 2), raw)
        scale = 32768.0
    elif sw == 1:
        samples = [b - 128 for b in raw]
        scale = 128.0
    else:
        raise SystemExit(f"unsupported sample width {sw}")
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
        rms = math.sqrt(sum(s * s for s in chunk) / len(chunk)) / scale
        env.append(min(1.0, rms * 3.2))
    # smooth
    out = []
    prev = 0.0
    for v in env:
        prev = prev * 0.55 + v * 0.45
        out.append(prev)
    # gate silence
    peak = max(out) or 1.0
    return [0.0 if v < 0.04 else min(1.0, v / peak) for v in out]


def stage_bg(w: int, h: int) -> Image.Image:
    """Warm white club stage — never pure black."""
    im = Image.new("RGB", (w, h), (244, 241, 234))
    d = ImageDraw.Draw(im)
    # soft spotlight
    for r in range(80, 0, -4):
        a = int(18 * (1 - r / 80))
        d.ellipse(
            [w // 2 - r * 6, int(h * 0.22) - r * 4, w // 2 + r * 6, int(h * 0.22) + r * 5],
            fill=(255, 255, 255),
        )
    # floor line
    d.rectangle([0, int(h * 0.78), w, h], fill=(230, 224, 212))
    d.line([(0, int(h * 0.78)), (w, int(h * 0.78))], fill=(210, 200, 180), width=3)
    return im


def draw_mic(draw: ImageDraw.ImageDraw, cx: int, cy: int, scale: float = 1.0) -> None:
    """Simple stage mic prop."""
    s = scale
    # stand
    draw.line([(cx, cy + int(40 * s)), (cx, cy + int(160 * s))], fill=(60, 60, 66), width=max(2, int(6 * s)))
    draw.line([(cx - int(30 * s), cy + int(160 * s)), (cx + int(30 * s), cy + int(160 * s))],
              fill=(60, 60, 66), width=max(2, int(5 * s)))
    # capsule
    r = int(28 * s)
    draw.ellipse([cx - r, cy - int(48 * s) - r, cx + r, cy - int(48 * s) + r], fill=(40, 40, 46))
    draw.ellipse([cx - r + 4, cy - int(48 * s) - r + 4, cx + r - 4, cy - int(48 * s) + r - 4],
                 fill=(90, 90, 100))
    # grill lines
    for i in range(-2, 3):
        draw.line(
            [(cx - r + 6, cy - int(48 * s) + i * int(8 * s)),
             (cx + r - 6, cy - int(48 * s) + i * int(8 * s))],
            fill=(55, 55, 62), width=1,
        )


def draw_mouth(img: Image.Image, openness: float) -> None:
    """Paint a soft muzzle mouth driven by envelope 0..1."""
    w, h = img.size
    l, t, r, b = FACE
    x0, y0, x1, y1 = int(w * l), int(h * t), int(w * r), int(h * b)
    cx = (x0 + x1) // 2
    cy = y0 + int((y1 - y0) * 0.62)
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(overlay)
    open_px = int((y1 - y0) * (0.12 + 0.55 * openness))
    wide = int((x1 - x0) * (0.22 + 0.18 * openness))
    if open_px < 4:
        # closed smile line
        d.line([(cx - wide, cy), (cx + wide, cy)], fill=(50, 30, 28, 200), width=3)
    else:
        # mouth cavity
        d.ellipse([cx - wide, cy - open_px // 3, cx + wide, cy + open_px],
                  fill=(45, 22, 24, 230))
        # teeth hint when wide open
        if openness > 0.45:
            d.ellipse([cx - wide // 2, cy - open_px // 4, cx + wide // 2, cy + open_px // 5],
                      fill=(240, 230, 220, 180))
        # lower lip shade
        d.ellipse([cx - wide // 2, cy + open_px - 4, cx + wide // 2, cy + open_px + 6],
                  fill=(80, 40, 40, 120))
    overlay = overlay.filter(ImageFilter.GaussianBlur(1.2))
    img.paste(overlay, (0, 0), overlay)


def draw_plate(img: Image.Image, name: str, topic: str) -> None:
    w, h = img.size
    d = ImageDraw.Draw(img)
    f_name = pick_font(int(h * 0.045))
    f_sub = pick_font(int(h * 0.028))
    bar_h = int(h * 0.12)
    d.rectangle([0, h - bar_h, w, h], fill=(255, 255, 255))
    d.rectangle([0, h - bar_h, w, h - bar_h + 6], fill=(196, 137, 26))
    d.text((48, h - bar_h + 22), name.upper(), font=f_name, fill=(20, 20, 20))
    d.text((48, h - bar_h + 22 + int(h * 0.048)), topic, font=f_sub, fill=(90, 90, 90))


def render_frames(hero: Path, env: list[float], outdir: Path, name: str) -> list[Path]:
    outdir.mkdir(parents=True, exist_ok=True)
    base = Image.open(hero).convert("RGB")
    # square product shot → letterbox onto stage
    dog_size = int(VW * 0.78)
    dog = base.resize((dog_size, dog_size), Image.Resampling.LANCZOS)
    dog = ImageEnhance.Color(dog).enhance(1.08)
    dog = ImageEnhance.Contrast(dog).enhance(1.04)
    frames = []
    n = len(env)
    font_topic = pick_font(28)
    for i, openv in enumerate(env):
        stage = stage_bg(VW, VH)
        # subtle bob + breathe
        t = i / max(1, FPS)
        bob = int(math.sin(t * 2.4) * 6)
        breathe = 1.0 + 0.01 * math.sin(t * 3.1)
        sz = int(dog_size * breathe)
        dog_i = dog.resize((sz, sz), Image.Resampling.BILINEAR)
        # head micro-tilt
        ang = math.sin(t * 1.7) * 1.2
        dog_i = dog_i.rotate(ang, resample=Image.Resampling.BICUBIC, expand=False)
        dx = (VW - sz) // 2
        dy = int(VH * 0.28) + bob
        stage.paste(dog_i, (dx, dy))
        # mouth on a working copy of the pasted region
        work = stage.copy()
        # draw mouth relative to full stage using FACE of the dog image box
        # temporarily scale FACE onto the dog placement
        global FACE
        saved = FACE
        # map face box into stage coords via dog placement
        l, t0, r, b = saved
        FACE = (
            (dx + sz * l) / VW,
            (dy + sz * t0) / VH,
            (dx + sz * r) / VW,
            (dy + sz * b) / VH,
        )
        draw_mouth(work, openv)
        FACE = saved
        # mic on the right
        draw_mic(ImageDraw.Draw(work), int(VW * 0.82), int(VH * 0.52), scale=1.3)
        draw_plate(work, name, "stand-up · mic on")
        # tiny laugh cue on loud frames
        if openv > 0.55:
            d = ImageDraw.Draw(work)
            d.text((48, int(VH * 0.12)), "ha ha ha", font=pick_font(36), fill=(196, 137, 26))
        p = outdir / f"f{i:04d}.png"
        work.save(p, "PNG")
        frames.append(p)
        if i % 12 == 0 or i == n - 1:
            print(f"  frame {i+1}/{n} open={openv:.2f}", flush=True)
    return frames


def mux(frames: list[Path], wav: Path, out_mp4: Path) -> None:
    out_mp4.parent.mkdir(parents=True, exist_ok=True)
    pattern = str(frames[0].parent / "f%04d.png")
    cmd = [
        "ffmpeg", "-y",
        "-framerate", str(FPS),
        "-i", pattern,
        "-i", str(wav),
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "160k",
        "-shortest",
        "-movflags", "+faststart",
        str(out_mp4),
    ]
    print("ffmpeg…", flush=True)
    subprocess.run(cmd, check=True, capture_output=True)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--name", default="Buster")
    ap.add_argument("--voice", default="ryan")
    ap.add_argument("--out", default=str(OUT_DEFAULT))
    ap.add_argument("--topic", default="does stand-up into a microphone")
    ap.add_argument("--script", default="")
    args = ap.parse_args()

    if not HERO.exists():
        raise SystemExit(f"missing hero still: {HERO}")
    out = Path(args.out)
    work = out / "p0_work"
    work.mkdir(parents=True, exist_ok=True)
    text = args.script or " ".join(SCRIPT_LINES)
    wav = work / "set.wav"
    print(f"TTS ({args.voice})…", flush=True)
    asyncio.run(tts(text, args.voice, wav))
    env = envelope_from_wav(wav)
    print(f"envelope frames={len(env)} peak={max(env):.2f}", flush=True)
    frames = render_frames(HERO, env, work / "frames", args.name)
    mp4 = out / "p0_standup.mp4"
    mux(frames, wav, mp4)
    print(f"OK {mp4} ({mp4.stat().st_size} bytes)", flush=True)
    # cleanup frames to save disk
    for f in frames:
        f.unlink(missing_ok=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
