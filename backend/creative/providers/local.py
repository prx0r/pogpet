"""Local (free) provider adapters. $0, in-repo, always available first.

These are the defaults the router resolves before any paid provider:
edge-tts voice, procedural music, PIL composite, Blender jaw-bake lipsync,
Meshy genesis (the one paid exception, still ask-first + free-tier), stub
realtime. Paid adapters live in alibaba.py / fal.py / meta.py (staged).
"""
from __future__ import annotations

import subprocess
from pathlib import Path

from .base import ProviderNotConfigured
from .router import register
from .base import BaseAdapter


class _Local(BaseAdapter):
    paid = False

    def is_available(self) -> bool:
        return True


@register
class EdgeTTSAdapter(_Local):
    capability = "voice_tts"
    name = "local.edge_tts"

    def run(self, payload: dict) -> dict:
        from backend import video as _video
        text = str(payload.get("text") or "")
        if not text.strip():
            raise ProviderNotConfigured("voice_tts: empty text")
        out = Path(payload.get("out") or "/tmp/oddhobb-tts.mp3")
        _video.tts(text[:2000], str(payload.get("voice") or "ryan"), out)
        return {"ok": True, "audio": str(out)}


@register
class ProceduralMusicAdapter(_Local):
    """Free music default from freaktown: stdlib procedural walkouts
    (sound_synth.py) — zero cost, zero creds, sibling repo read-only."""
    capability = "music"
    name = "local.procedural"

    def run(self, payload: dict) -> dict:
        from backend import performance as _perf
        out = Path(payload.get("out") or "/tmp/oddhobb-walkout.wav")
        out.write_bytes(_perf.procedural_music(int(payload.get("seed") or 0),
                                              payload.get("recipe") or {}))
        return {"ok": True, "audio": str(out)}


@register
class CompositeAdapter(_Local):
    capability = "identity_image"
    name = "local.composite"

    def run(self, payload: dict) -> dict:
        # Free tier of identity_image: deterministic composite, no pixels gen.
        return {"ok": True, "mode": "composite2d preview",
                "note": "paid plate via alibaba.qwen_image / fal.flux_edit"}


@register
class JawBakeAdapter(_Local):
    """Free lip-sync default from prx0r/freaktown: jawOpen morph poses baked
    against the audio envelope (scripts/pose_lipsync.py), CPU-only. Takes
    name/voice/script, returns the mp4 path + duration like the server does."""
    capability = "lip_sync"
    name = "local.jaw_bake"

    def run(self, payload: dict) -> dict:
        import time
        script = Path(__file__).resolve().parents[3] / "scripts" / "pose_lipsync.py"
        name = str(payload.get("name") or "Buster")
        voice = str(payload.get("voice") or "ryan")
        script_text = str(payload.get("script") or "")
        out = Path(payload.get("out") or
                   f"/tmp/oddhobb-jaw-{int(time.time())}.mp4")
        cmd = ["python3", str(script), "--name", name, "--voice", voice,
               "--out", str(out)]
        if script_text:
            cmd += ["--script", script_text]
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=900)
        except subprocess.TimeoutExpired:
            raise ProviderNotConfigured("lip_sync: jaw bake timed out")
        if proc.returncode != 0 or not out.is_file():
            raise ProviderNotConfigured(f"lip_sync: jaw bake failed: {(proc.stderr or proc.stdout or '')[-200:]}")
        import json as _json
        dur = 0.0
        try:
            probe = subprocess.run(
                ["ffprobe", "-v", "error", "-show_entries", "format=duration",
                 "-of", "csv=p=0", str(out)],
                capture_output=True, text=True, timeout=30)
            dur = float((probe.stdout or "").strip() or 0)
        except Exception:  # noqa: BLE001
            pass
        return {"ok": True, "mode": "jawOpen bake", "path": str(out),
                "bytes": out.stat().st_size, "duration": round(dur, 2)}


@register
class PoseBakeAdapter(JawBakeAdapter):
    capability = "video_scene"
    name = "local.pose_bake"


@register
class StubRealtimeAdapter(_Local):
    capability = "realtime_voice"
    name = "local.stub"

    def run(self, payload: dict) -> dict:
        return {"ok": True, "mode": "typed turns",
                "note": "live voice needs alibaba.qwen_omni or gemini.live + key"}
