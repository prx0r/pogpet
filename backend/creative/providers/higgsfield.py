"""Higgsfield adapter (STAGED — user BYOC only, never server key).

One REST interface over multiple image/video families; Wan 3.0
reference-to-video is the premium identity-video path. Docs:
https://open.higgsfield.ai (balance is API-specific, not the web sub).
"""
from __future__ import annotations

import json
import urllib.request

from .base import ProviderNotConfigured
from .router import register
from .base import BaseAdapter

API = "https://api.higgsfield.ai/v1"


def _key(payload: dict) -> str:
    import os
    return str(payload.get("api_key") or os.environ.get("HIGGSFIELD_API_KEY") or "")


@register
class HiggsfieldWanAdapter(BaseAdapter):
    capability = "video_scene"
    name = "higgsfield.wan_3"
    paid = True

    def is_available(self) -> bool:
        return False  # staged until first connected credential exists

    def run(self, payload: dict) -> dict:
        k = _key(payload)
        if not k:
            raise ProviderNotConfigured("higgsfield.wan_3: connect Higgsfield first")
        body = {"model": "alibaba/wan-3.0/reference-to-video",
                "prompt": str(payload.get("prompt") or ""),
                "reference_images": payload.get("images") or []}
        req = urllib.request.Request(f"{API}/generate", data=json.dumps(body).encode(),
                                     method="POST")
        req.add_header("Authorization", f"Bearer {k}")
        req.add_header("Content-Type", "application/json")
        with urllib.request.urlopen(req, timeout=600) as r:
            return {"ok": True, "task": json.loads(r.read().decode() or "{}")}
