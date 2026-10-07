"""Alibaba Model Studio adapters (STAGED — need key + approval).

Singaporeregion workspace domains. Keys: BYO payload api_key wins, else
DASHSCOPE_API_KEY env. Nothing here runs without router allow_paid.
Docs: https://docs.modelstudio.console.alibabacloud.com (has /llms.txt)
"""
from __future__ import annotations

import json
import os
import urllib.request

from .base import ProviderNotConfigured
from .router import register
from .base import BaseAdapter

API = "https://dashscope-intl.aliyuncs.com/api/v1"


def _key(payload: dict) -> str:
    return str(payload.get("api_key") or os.environ.get("DASHSCOPE_API_KEY") or "")


def _post(path: str, body: dict, key: str, timeout: int = 120) -> dict:
    req = urllib.request.Request(API + path, data=json.dumps(body).encode(),
                                 method="POST")
    req.add_header("Authorization", f"Bearer {key}")
    req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode() or "{}")


class _Ali(BaseAdapter):
    paid = True

    def _k(self, payload: dict) -> str:
        k = _key(payload)
        if not k:
            raise ProviderNotConfigured(f"{self.name}: no DashScope key (BYO or env)")
        return k


@register
class QwenImageAdapter(_Ali):
    capability = "identity_image"
    name = "alibaba.qwen_image"

    def run(self, payload: dict) -> dict:
        d = _post("/services/aigc/text2image/image-synthesis", {
            "model": "qwen-image-3.0-pro",
            "input": {"prompt": str(payload.get("prompt") or "")},
        }, self._k(payload), timeout=300)
        return {"ok": True, "task": d}


@register
class WanVideoAdapter(_Ali):
    capability = "video_scene"
    name = "alibaba.wan_3"

    def run(self, payload: dict) -> dict:
        d = _post("/services/aigc/video-generation/video-synthesis", {
            "model": "wan-3.0",
            "input": {"prompt": str(payload.get("prompt") or ""),
                      "images": payload.get("images") or [],
                      "duration_s": int(payload.get("duration_s") or 8)},
        }, self._k(payload), timeout=600)
        return {"ok": True, "task": d}


@register
class VoiceEnrollAdapter(_Ali):
    """10–20s reference → persistent voice identity. CONSENT REQUIRED upstream
    (voice_consents table) before this ever runs."""
    capability = "voice_clone"
    name = "alibaba.qwen_enroll"

    def run(self, payload: dict) -> dict:
        if not payload.get("consent_id"):
            raise ProviderNotConfigured("voice_clone: consent_id required")
        d = _post("/services/voice/qwen-voice-enrollment", {
            "reference_audio_url": payload.get("audio_url"),
            "target_model": "qwen3.8-omni-flash-realtime",
        }, self._k(payload))
        return {"ok": True, "enrollment": d}


@register
class ClonedTTSAdapter(_Ali):
    """Deterministic cloned line read (dad-line.wav), not a conversation."""
    capability = "cloned_tts"
    name = "alibaba.qwen_tts_vc"

    def run(self, payload: dict) -> dict:
        if not payload.get("consent_id"):
            raise ProviderNotConfigured("cloned_tts: consent_id required")
        d = _post("/services/audio/qwen3-tts-vc", {
            "text": str(payload.get("text") or ""),
            "provider_voice_id": payload.get("provider_voice_id"),
        }, self._k(payload), timeout=300)
        return {"ok": True, "task": d}


@register
class QwenOmniAdapter(_Ali):
    """Live character voice. Returns session params; the BROWSER connects
    direct (WebRTC/WS) — server never proxies media."""
    capability = "realtime_voice"
    name = "alibaba.qwen_omni"

    def run(self, payload: dict) -> dict:
        self._k(payload)
        return {"ok": True, "model": "qwen3.8-omni-flash-realtime",
                "transport": ["webrtc", "websocket", "aoq"],
                "tools": "OddHobb MCP (same tools as Muse)"}
