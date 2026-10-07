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
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "freaktown_sound", "/home/ubuntu/freaktown/sound_synth.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        out = Path(payload.get("out") or "/tmp/oddhobb-walkout.wav")
        out.write_bytes(mod.generate(payload.get("recipe") or {},
                                     int(payload.get("seed") or 0)))
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
    against the audio envelope (scripts/pose_lipsync.py), CPU-only."""
    capability = "lip_sync"
    name = "local.jaw_bake"

    def run(self, payload: dict) -> dict:
        script = Path(__file__).resolve().parents[3] / "scripts" / "pose_lipsync.py"
        name = str(payload.get("name") or "Buster")
        voice = str(payload.get("voice") or "ryan")
        try:
            proc = subprocess.run(
                ["python3", str(script), "--name", name, "--voice", voice],
                capture_output=True, text=True, timeout=600)
        except subprocess.TimeoutExpired:
            raise ProviderNotConfigured("lip_sync: jaw bake timed out")
        if proc.returncode != 0:
            raise ProviderNotConfigured(f"lip_sync: jaw bake failed: {(proc.stderr or '')[-200:]}")
        return {"ok": True, "mode": "jawOpen bake", "log": (proc.stdout or "")[-300:]}


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
