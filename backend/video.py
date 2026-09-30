"""Free-tier video: comedy set → voice → MP4. No GPU, no vendor, no key.

The whole point is $0 marginal cost:
  1. script   — our LLM (opencode-go key already in .env)
  2. voice    — edge-tts, 324 voices, free, no auth
  3. frame    — PIL composes figg-branded scene + the pet's photo
  4. render   — ffmpeg muxes still frame + audio
  5. watermark— free tier only (paid skips it)

Lip-sync (SadTalker/Wav2Lip) needs a GPU this box doesn't have; that's the
Kaggle kernel or fal. Everything here runs on CPU today.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import os
import re
import subprocess
import urllib.error
import urllib.request
import uuid
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from . import config

OUT_DIR = config.DATA / "videos"
VW, VH = 1080, 1920

FIGG_VIOLET = (139, 61, 255)
FIGG_PAPER = (250, 250, 248)
FIGG_INK = (17, 17, 17)
FIGG_LILAC = (234, 216, 255)


class VideoError(Exception):
    def __init__(self, message: str, code: int = 400):
        super().__init__(message)
        self.code = code


# ── voices ────────────────────────────────────────────────────────────

# Curated shortlist — the full list is 324 and changes; these are stable,
# distinct, and read comedy well.
VOICES = {
    "andrew":   {"label": "Andrew — warm bloke",     "id": "en-GB-AndrewNeural"},
    "ryan":     {"label": "Ryan — dry, deadpan",     "id": "en-GB-RyanNeural"},
    "sonia":    {"label": "Sonia — bright",          "id": "en-GB-SoniaNeural"},
    "aria":     {"label": "Aria — punchy",           "id": "en-US-AriaNeural"},
    "guy":      {"label": "Guy — announcer",         "id": "en-US-GuyNeural"},
    "jenny":    {"label": "Jenny — cheeky",          "id": "en-US-JennyNeural"},
    "libby":    {"label": "Libby — young, silly",    "id": "en-GB-LibbyNeural"},
    "Neill":    {"label": "Neill — Scottish",        "id": "en-GB-NeillNeural"},
}


def voice_id(key: str) -> str:
    return (VOICES.get(key) or VOICES["ryan"])["id"]


# ── script ────────────────────────────────────────────────────────────

# Which voice the generator puts on depends on the talent — the Perform tab
# stages comedy, dance and singing off the same render path.
TALENT_BRIEF = {
    "comedy": "a tight 30-second stand-up routine",
    "dance":  "a spoken intro to a dance number that then counts the beat in",
    "singing": "a short spoken intro that leads into one sung line",
}

SYSTEM = (
    "You write very short stand-up routines for a pet. "
    "Return ONLY a JSON array of 3-5 punchy lines, each under 90 characters. "
    "No stage directions, no quotes, no emoji, no preamble. "
    "Warm, clean, specific to the detail given. The last line is the closer."
)


def write_set(topic: str, pet_name: str = "your pet", persona: str = "",
               talent: str = "comedy") -> list[str]:
    """30-second set from our LLM. Returns the lines."""
    key = os.environ.get("OPENCODE_API_KEY", "")
    if not key:
        raise VideoError("OPENCODE_API_KEY not set — no script model", 500)

    brief = TALENT_BRIEF.get(talent, TALENT_BRIEF["comedy"])
    sys_prompt = (
        f"You write very short performance pieces for a pet: {brief}. "
        "Return ONLY a JSON array of 3-5 punchy lines, each under 90 characters. "
        "No stage directions, no quotes, no emoji, no preamble. "
        "Warm, clean, specific to the detail given. The last line is the closer."
    )
    prompt = f"Pet name: {pet_name}. Funny detail: {topic}. "
    if persona:
        prompt += f"Persona: {persona}. "
    prompt += "Write the set."

    body = json.dumps({
        "model": os.environ.get("PI_MODEL", "mimo-v2.5"),
        "messages": [
            {"role": "system", "content": sys_prompt},
            {"role": "user", "content": prompt},
        ],
        # Reasoning models can burn the whole budget thinking; 400 left us with
        # `content: null` and finish_reason=length now and then.
        "max_tokens": int(os.environ.get("SCRIPT_MAX_TOKENS", "1500")),
        "temperature": 0.9,
    }).encode()

    last_err = ""
    for attempt in range(3):
        req = urllib.request.Request(
            "https://opencode.ai/zen/go/v1/chat/completions",
            data=body,
            headers={
                "Authorization": f"Bearer {key}",
                "Content-Type": "application/json",
                "x-opencode-session": f"figg-{uuid.uuid4()}",
                # Cloudflare 1010s urllib's default UA as a bot.
                "User-Agent": ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                               "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"),
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=90) as r:
                payload = json.loads(r.read().decode())
        except urllib.error.HTTPError as e:
            detail = e.read().decode("utf-8", "replace")[:200]
            last_err = f"HTTP {e.code} {detail}"
            if e.code in (402, 403, 429):
                break                       # won't improve on retry
            continue
        except Exception as e:
            last_err = f"unreachable: {e}"
            continue

        try:
            choice = payload["choices"][0]
            content = choice.get("message", {}).get("content") or ""
        except (KeyError, IndexError, TypeError):
            last_err = f"unexpected shape: {json.dumps(payload)[:200]}"
            continue

        lines = _parse_lines(content)
        if lines:
            return lines
        last_err = (f"empty content (finish_reason="
                    f"{choice.get('finish_reason')}) attempt {attempt + 1}")

    raise VideoError(f"script model failed: {last_err}", 502)


def _parse_lines(content: str) -> list[str]:
    """Tolerant: takes a JSON array if present, else splits into lines."""
    m = re.search(r"\[.*\]", content, re.S)
    if m:
        try:
            arr = json.loads(m.group(0))
            lines = [str(x).strip() for x in arr if str(x).strip()]
            if lines:
                return lines[:6]
        except json.JSONDecodeError:
            pass
    lines = [l.strip(" -*•\t\"'") for l in content.splitlines() if l.strip()]
    return [l for l in lines if len(l) > 3][:6]


# ── audio ─────────────────────────────────────────────────────────────

def tts(text: str, voice_key: str, out_mp3: Path) -> Path:
    import edge_tts
    out_mp3.parent.mkdir(parents=True, exist_ok=True)
    asyncio.run(edge_tts.Communicate(text, voice_id(voice_key)).save(str(out_mp3)))
    if not out_mp3.exists() or out_mp3.stat().st_size < 500:
        raise VideoError("the voice service returned no audio — try again", 502)
    return out_mp3


# ── frame ─────────────────────────────────────────────────────────────

def _font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for cand in (
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ):
        try:
            return ImageFont.truetype(cand, size)
        except OSError:
            continue
    return ImageFont.load_default()


def compose_frame(photo: Path | None, pet_name: str, scene: str,
                  headline: str, watermark: bool) -> Path:
    """PIL builds the full frame so ffmpeg only has to mux."""
    config.ensure_dirs()
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    img = Image.new("RGB", (VW, VH), FIGG_PAPER)

    # Pattern first — it must sit *under* the chrome, otherwise blending it
    # washes the figg-violet header out to lilac.
    pat = config.ROOT / "figg-studio" / "assets" / "patterns" / "figg-repeat.png"
    if pat.is_file():
        try:
            tile = Image.open(pat).convert("RGBA").resize((180, 180))
            for y in range(0, VH, 180):
                for x in range(0, VW, 180):
                    img.paste(tile, (x, y), tile)
            img = Image.blend(img, Image.new("RGB", (VW, VH), FIGG_PAPER), 0.55)
        except Exception:
            pass

    d = ImageDraw.Draw(img, "RGBA")

    # scene chrome — drawn after the blend so the violet stays #8B3DFF
    d.rectangle([0, 0, VW, 260], fill=FIGG_VIOLET)
    d.rectangle([0, VH - 300, VW, VH], fill=FIGG_INK)

    # headline
    d.text((VW // 2, 130), "figg.", font=_font(96), fill=(255, 255, 255), anchor="mm")
    d.text((VW // 2, 330), scene.upper(), font=_font(44), fill=FIGG_VIOLET, anchor="mm")

    # the pet
    cx, cy, r = VW // 2, VH // 2 + 40, 340
    if photo and photo.is_file():
        try:
            src = Image.open(photo).convert("RGB")
            side = min(src.size)
            src = src.crop(((src.width - side) // 2, (src.height - side) // 2,
                            (src.width + side) // 2, (src.height + side) // 2))
            src = src.resize((r * 2, r * 2), Image.LANCZOS)
            mask = Image.new("L", (r * 2, r * 2), 0)
            ImageDraw.Draw(mask).ellipse([0, 0, r * 2, r * 2], fill=255)
            img.paste(src, (cx - r, cy - r), mask)
            d = ImageDraw.Draw(img, "RGBA")
            d.ellipse([cx - r - 8, cy - r - 8, cx + r + 8, cy + r + 8],
                      outline=FIGG_VIOLET, width=10)
        except Exception:
            pass
    else:
        d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=FIGG_LILAC,
                  outline=FIGG_VIOLET, width=10)

    d.text((cx, cy + r + 90), pet_name, font=_font(72), fill=FIGG_INK, anchor="mm")
    d.text((cx, cy + r + 165), headline[:60], font=_font(34), fill=(90, 90, 90), anchor="mm")

    if watermark:
        d.text((VW // 2, VH - 150), "free preview — figg.", font=_font(40),
               fill=(255, 255, 255), anchor="mm")
        d.text((VW // 2, VH - 90), "roast.pet", font=_font(30),
               fill=FIGG_LILAC, anchor="mm")

    out = OUT_DIR / f"frame_{uuid.uuid4().hex[:12]}.png"
    img.save(out, "PNG")
    return out


# ── render ────────────────────────────────────────────────────────────

def mux(frame: Path, audio: Path, out_mp4: Path) -> Path:
    out_mp4.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        "ffmpeg", "-y", "-loop", "1", "-i", str(frame), "-i", str(audio),
        "-c:v", "libx264", "-tune", "stillimage", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "128k", "-shortest", "-movflags", "+faststart",
        str(out_mp4),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    if proc.returncode != 0 or not out_mp4.exists():
        raise VideoError(f"render failed: {(proc.stderr or '')[-300:]}", 500)
    return out_mp4


def duration_of(path: Path) -> float:
    try:
        out = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "csv=p=0", str(path)],
            capture_output=True, text=True, timeout=30,
        ).stdout.strip()
        return float(out or 0)
    except Exception:
        return 0.0


def make(*, topic: str, pet_name: str, scene: str, voice: str,
         photo: Path | None, persona: str = "", watermark: bool | None = None,
         talent: str = "comedy") -> dict:
    """Full free-tier pipeline. Returns record for the DB/API."""
    if watermark is None:
        watermark = config.WATERMARK_FREE
    if scene not in config.SCENES:
        raise VideoError(f"unknown scene — pick one of: {', '.join(config.SCENES)}")

    lines = write_set(topic, pet_name, persona, talent=talent)
    if not lines:
        raise VideoError("the script came back empty — try a different detail", 502)
    script = " ".join(lines)

    token = uuid.uuid4().hex[:12]
    mp3 = OUT_DIR / f"set_{token}.mp3"
    mp4 = OUT_DIR / f"set_{token}.mp4"
    frame = None
    try:
        tts(script, voice, mp3)
        frame = compose_frame(photo, pet_name, config.SCENES[scene], lines[0], watermark)
        mux(frame, mp3, mp4)
    finally:
        for p in (frame,):
            if p and p.exists():
                p.unlink(missing_ok=True)

    return {
        "video_id": f"vid_{token}",
        "lines": lines,
        "script": script,
        "scene": scene,
        "scene_label": config.SCENES[scene],
        "talent": talent,
        "voice": voice,
        "voice_id": voice_id(voice),
        "watermarked": bool(watermark),
        "file": str(mp4),
        "audio": str(mp3),
        "bytes": mp4.stat().st_size if mp4.exists() else 0,
        "duration": duration_of(mp4),
        "cost": 0,
    }
