"""Strip-to-video — one premise, every vertical feed.

A comic strip becomes: TikTok/Instagram slideshow panels for free, and a
1080x1920 MP4 (slow zoom per panel + deadpan voiceover + burned caption)
for Reels / Shorts / TikTok video. The joke text stays OUT of the plates —
captions are burned deterministically here, same rule as the card pipeline.

Splat rooms (backend/marble.py) can replace the plain backdrop once
MARBLE_API_KEY lands; the assembly below doesn't care what the plates are.
"""
from __future__ import annotations

import subprocess
import uuid
from pathlib import Path

from PIL import Image, ImageDraw

from backend import config, video as _video

VW, VH = 1080, 1920
FPS = 30


def plan(captions: list[str], *, min_secs: float = 2.0,
         max_secs: float = 6.0, chars_per_sec: float = 15.0) -> list[float]:
    """Per-panel screen time from caption length. Pure math, offline safe."""
    out = []
    for c in captions:
        out.append(round(min(max_secs, max(min_secs, len(c) / chars_per_sec)), 2))
    return out


def _fit_panel(src: Path) -> Image.Image:
    """Panel plate -> full-bleed 1080x1920 (cover crop, center)."""
    img = Image.open(src).convert("RGB")
    scale = max(VW / img.width, VH / img.height)
    img = img.resize((round(img.width * scale) + 1, round(img.height * scale) + 1),
                     Image.LANCZOS)
    x = (img.width - VW) // 2
    y = (img.height - VH) // 2
    return img.crop((x, y, x + VW, y + VH))


def caption_card(caption: str, size: tuple[int, int] = (VW, VH)) -> Image.Image:
    """Deterministic caption plate (used for the end card / CTA frame)."""
    img = Image.new("RGB", size, (17, 17, 17))
    d = ImageDraw.Draw(img)
    fnt = _video._font(64)
    d.text((size[0] // 2, size[1] // 2), caption, font=fnt,
           fill=(250, 250, 248), anchor="mm")
    return img


def slideshow(panels: list[Path | str], captions: list[str], *,
              voice: str = "ryan", out_mp4: Path | str | None = None,
              workdir: Path | str | None = None) -> Path:
    """Render panels + spoken captions to a vertical MP4. Needs ffmpeg +
    the voice service (edge-tts fallback, same as video.tts)."""
    if len(panels) != len(captions) or not panels:
        raise ValueError("panels and captions must be non-empty and aligned")
    config.ensure_dirs()
    work = Path(workdir) if workdir else config.DATA / "meme_video" / uuid.uuid4().hex[:12]
    work.mkdir(parents=True, exist_ok=True)
    durs = plan(captions)
    segs: list[Path] = []
    auds: list[Path] = []
    for i, (p, cap) in enumerate(zip(panels, captions)):
        plate = _fit_panel(Path(p))
        still = work / f"panel_{i}.png"
        plate.save(still, "PNG")
        audio = work / f"cap_{i}.mp3"
        _video.tts(cap, voice, audio)
        spoken = _video.duration_of(audio)
        dur = round(max(durs[i], spoken + 0.4), 2)
        seg = work / f"seg_{i}.mp4"
        # Slow push-in per panel; freeze the last frame instead of looping audio.
        cmd = ["ffmpeg", "-y", "-loop", "1", "-i", str(still),
               "-vf", f"scale=2160:-1,zoompan=z='1+0.06*on/{FPS * dur:.0f}':"
                      f"d={FPS * dur:.0f}:s={VW}x{VH}:fps={FPS}",
               "-t", str(dur), "-c:v", "libx264", "-preset", "veryfast",
               "-pix_fmt", "yuv420p", str(seg)]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        if proc.returncode != 0 or not seg.exists():
            raise _video.VideoError(f"panel render failed: {(proc.stderr or '')[-300:]}")
        segs.append(seg)
        auds.append(audio)
    # Stitch video, stitch audio, mux.
    vlist, alist = work / "v.txt", work / "a.txt"
    vlist.write_text("".join(f"file '{s}'\n" for s in segs))
    alist.write_text("".join(f"file '{a}'\n" for a in auds))
    vcat, acat = work / "v.mp4", work / "a.mp3"
    for lst, out, args in (
            (vlist, vcat, ["-f", "concat", "-safe", "0", "-i", str(vlist),
                            "-c", "copy", str(vcat)]),
            (alist, acat, ["-f", "concat", "-safe", "0", "-i", str(alist),
                            "-c", "copy", str(acat)])):
        proc = subprocess.run(["ffmpeg", "-y", *args],
                              capture_output=True, text=True, timeout=300)
        if proc.returncode != 0 or not out.exists():
            raise _video.VideoError(f"concat failed: {(proc.stderr or '')[-300:]}")
    dest = Path(out_mp4) if out_mp4 else work / "meme.mp4"
    dest.parent.mkdir(parents=True, exist_ok=True)
    proc = subprocess.run(
        ["ffmpeg", "-y", "-i", str(vcat), "-i", str(acat), "-c:v", "copy",
         "-c:a", "aac", "-b:a", "128k", "-shortest", "-movflags", "+faststart",
         str(dest)], capture_output=True, text=True, timeout=300)
    if proc.returncode != 0 or not dest.exists():
        raise _video.VideoError(f"mux failed: {(proc.stderr or '')[-300:]}")
    return dest
