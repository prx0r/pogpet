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
    # spotlight pool on the floor
    d.ellipse([w * 0.15, h * 0.55, w * 0.85, h * 0.92], fill=(252, 250, 246))
    # curtain suggestion (soft vertical bands)
    for i in range(8):
        x0 = int(w * i / 8)
        x1 = int(w * (i + 1) / 8)
        shade = 236 if i % 2 == 0 else 240
        d.rectangle([x0, 0, x1, int(h * 0.22)], fill=(shade, shade - 4, shade - 10))
    # soft warm glow behind character
    for r in range(200, 0, -8):
        alpha = max(0, 30 - r // 8)
        col = (min(255, 250 + alpha // 4), min(255, 245 + alpha // 5), min(255, 230 + alpha // 6))
        d.ellipse(
            [w // 2 - r, int(h * 0.38) - r, w // 2 + r, int(h * 0.38) + r],
            fill=col,
        )
    d.rectangle([0, int(h * 0.78), w, h], fill=(230, 224, 212))
    d.line([(0, int(h * 0.78)), (w, int(h * 0.78))], fill=(200, 188, 168), width=4)
    # side vignette (subtle, not black)
    vig = Image.new("L", (w, h), 0)
    vd = ImageDraw.Draw(vig)
    vd.ellipse([-w * 0.2, -h * 0.15, w * 1.2, h * 1.15], fill=40)
    vig = vig.filter(ImageFilter.GaussianBlur(80))
    dark = Image.new("RGB", (w, h), (210, 200, 185))
    im = Image.composite(im, dark, vig.point(lambda p: 255 if p > 20 else 0))
    return im


def draw_mic(draw: ImageDraw.ImageDraw, cx: int, cy: int, scale: float = 1.0) -> None:
    """Stage mic with a bit more polish."""
    s = scale
    draw.line([(cx, cy + int(40 * s)), (cx, cy + int(170 * s))], fill=(50, 50, 56), width=max(3, int(7 * s)))
    draw.line([(cx - int(34 * s), cy + int(170 * s)), (cx + int(34 * s), cy + int(170 * s))],
              fill=(50, 50, 56), width=max(3, int(6 * s)))
    # shock mount ring
    rr = int(36 * s)
    cy0 = cy - int(48 * s)
    draw.ellipse([cx - rr, cy0 - rr, cx + rr, cy0 + rr], outline=(70, 70, 78), width=max(2, int(4 * s)))
    r = int(26 * s)
    draw.ellipse([cx - r, cy0 - r, cx + r, cy0 + r], fill=(35, 35, 40))
    draw.ellipse([cx - r + 5, cy0 - r + 5, cx + r - 5, cy0 + r - 5], fill=(100, 100, 110))
    for i in range(-2, 3):
        draw.line([(cx - r + 7, cy0 + i * int(8 * s)), (cx + r - 7, cy0 + i * int(8 * s))],
                  fill=(55, 55, 62), width=1)
    # red tally light
    draw.ellipse([cx - 4, cy0 - r - 12, cx + 4, cy0 - r - 4], fill=(200, 40, 40))


def draw_mouth(img: Image.Image, openness: float) -> None:
    """Soft muzzle mouth driven by envelope 0..1 — looks like a talking dog."""
    w, h = img.size
    l, t, r, b = FACE
    x0, y0, x1, y1 = int(w * l), int(h * t), int(w * r), int(h * b)
    cx = (x0 + x1) // 2
    cy = y0 + int((y1 - y0) * 0.58)
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(overlay)
    wide = int((x1 - x0) * (0.26 + 0.12 * openness))
    open_px = int((y1 - y0) * (0.10 + 0.48 * openness))
    # muzzle shadow (helps the mouth read on cream fur)
    d.ellipse([cx - int(wide * 1.15), cy - int(open_px * 0.2) - 8,
               cx + int(wide * 1.15), cy + open_px + 14],
              fill=(90, 70, 60, 50))
    if open_px < 6:
        d.arc([cx - wide, cy - 6, cx + wide, cy + 10], 20, 160, fill=(55, 32, 30, 220), width=4)
    else:
        # cavity
        d.ellipse([cx - wide, cy - open_px // 4, cx + wide, cy + open_px],
                  fill=(42, 20, 22, 235))
        # tongue
        if openness > 0.35:
            d.ellipse([cx - wide // 3, cy + open_px // 4, cx + wide // 3, cy + open_px - 2],
                      fill=(170, 70, 75, 200))
        # upper teeth strip
        if openness > 0.5:
            d.rectangle([cx - int(wide * 0.55), cy - open_px // 5,
                         cx + int(wide * 0.55), cy + 2], fill=(245, 238, 228, 190))
        # lower lip
        d.ellipse([cx - int(wide * 0.7), cy + open_px - 6, cx + int(wide * 0.7), cy + open_px + 8],
                  fill=(70, 35, 35, 140))
    overlay = overlay.filter(ImageFilter.GaussianBlur(1.6))
    img.paste(overlay, (0, 0), overlay)


def draw_plate(img: Image.Image, name: str, topic: str) -> None:
    w, h = img.size
    d = ImageDraw.Draw(img)
    f_name = pick_font(int(h * 0.042))
    f_sub = pick_font(int(h * 0.026))
    bar_h = int(h * 0.13)
    # frosted bar
    bar = Image.new("RGBA", img.size, (0, 0, 0, 0))
    bd = ImageDraw.Draw(bar)
    bd.rectangle([0, h - bar_h, w, h], fill=(255, 255, 255, 235))
    bd.rectangle([0, h - bar_h, w, h - bar_h + 8], fill=(196, 137, 26, 255))
    img.paste(bar, (0, 0), bar)
    d = ImageDraw.Draw(img)
    d.text((52, h - bar_h + 28), name.upper(), font=f_name, fill=(18, 18, 18))
    d.text((52, h - bar_h + 28 + int(h * 0.046)), topic, font=f_sub, fill=(100, 100, 100))
    # oddhobb mark
    d.text((w - 180, h - bar_h + 28), "oddhobb", font=pick_font(22), fill=(196, 137, 26))


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
