"""Free performance kernel (devplan free-core-byoc): freaktown's timeline
thinking, adapted — never copied. Sibling repo stays read-only; we import
its pure functions (sound) and reimplement the small math (jaw smoothing,
viseme levels) against our own artifacts.

Levels: 0 amplitude→jaw · 1 word timings→envelope · 2 phonemes→visemes.
Paid neural lipsync stays a BYOC adapter, not a dependency.
"""
from __future__ import annotations

import math

# AA / OH / EE / FV / MBP viseme groups for GLB morph targets (level 2).
VISEME_GROUPS = {
    "AA": set("aàáâä"),
    "OH": set("oòóôö"),
    "EE": set("ei"),
    "FV": set("fv"),
    "MBP": set("mbp"),
    "REST": set(" "),
}

EXPRESSIONS = ("neutral", "deadpan", "grin", "annoyed", "surprised",
               "sad", "happy", "sleepy")
GESTURES = ("hold", "shrug", "wave", "point", "lean", "nod")
CAMERAS = ("wide", "medium", "close", "side")


def jaw_from_energy(energy: float, prev: float, smoothing: float = 0.35) -> float:
    """targetJaw = speechEnergy(frame); jaw += (target - jaw) * smoothing."""
    target = max(0.0, min(1.0, energy))
    return prev + (target - prev) * smoothing


def envelope_from_words(words: list[dict], t: float) -> float:
    """Level 1: TTS word timings → speech envelope at time t."""
    for w in words:
        if float(w.get("start", 0)) <= t <= float(w.get("end", 0)):
            return 1.0
    return 0.0


def viseme_for_char(ch: str) -> str:
    c = ch.lower()
    for name, chars in VISEME_GROUPS.items():
        if c in chars:
            return name
    return "REST"


def viseme_track(text: str, wps: float = 2.5) -> list[dict]:
    """Level 2: text → viseme sequence at ~words-per-second pacing."""
    track, t = [], 0.0
    for ch in text:
        if ch.strip():
            track.append({"t": round(t, 2), "viseme": viseme_for_char(ch)})
        t += 1.0 / (wps * 5)
    return track


def compile_beats(beats: list[dict]) -> list[dict]:
    """delivery.v1 beats → timed performance cues (freaktown shape)."""
    out, t = [], 0.0
    for b in beats:
        dur = float(b.get("duration_s") or 2.0)
        out.append({"start": round(t, 2), "end": round(t + dur, 2),
                    "expression": b.get("expression", "neutral"),
                    "gesture": b.get("gesture", "hold"),
                    "camera": b.get("camera", "medium"),
                    "text": b.get("text", "")})
        t += dur + float(b.get("pause_after_ms", 0)) / 1000.0
    return out


def procedural_music(seed: int = 0, recipe: dict | None = None) -> bytes:
    """Free walkout music via freaktown's stdlib synth (import, not copy)."""
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "freaktown_sound", "/home/ubuntu/freaktown/sound_synth.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.generate(recipe or {}, seed)
