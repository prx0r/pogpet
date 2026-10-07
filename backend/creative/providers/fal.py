"""fal.ai adapters (STAGED — need key + approval).

Creative model supermarket, not architecture: scene plates, edits, lipsync,
Tripo meshes. Keys: BYO payload api_key wins, else FAL_KEY env. fal bills on
successful outputs only; long jobs go through its queue + our callback, never
a blocked worker. Docs: https://fal.ai/docs (has /llms.txt)
"""
from __future__ import annotations

import json
import os
import time
import urllib.request

from .base import ProviderNotConfigured
from .router import register
from .base import BaseAdapter

API = "https://queue.fal.run"


def _key(payload: dict) -> str:
    return str(payload.get("api_key") or os.environ.get("FAL_KEY") or "")


def _submit(endpoint: str, args: dict, key: str) -> str:
    req = urllib.request.Request(f"{API}/{endpoint}", data=json.dumps(args).encode(),
                                 method="POST")
    req.add_header("Authorization", f"Key {key}")
    req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=120) as r:
        d = json.loads(r.read().decode() or "{}")
    rid = d.get("request_id", "")
    if not rid:
        raise ProviderNotConfigured(f"fal: no request_id: {json.dumps(d)[:200]}")
    return rid


def _result(endpoint: str, rid: str, key: str, timeout_s: int = 600) -> dict:
    url = f"{API}/{endpoint}/requests/{rid}"
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        req = urllib.request.Request(url)
        req.add_header("Authorization", f"Key {key}")
        with urllib.request.urlopen(req, timeout=60) as r:
            d = json.loads(r.read().decode() or "{}")
        if d.get("status") in ("COMPLETED", "FAILED"):
            return d
        time.sleep(5)
    raise ProviderNotConfigured("fal: timed out waiting for result")


class _Fal(BaseAdapter):
    paid = True
    endpoint = ""

    def _k(self, payload: dict) -> str:
        k = _key(payload)
        if not k:
            raise ProviderNotConfigured(f"{self.name}: no FAL_KEY (BYO or env)")
        return k

    def submit(self, payload: dict, args: dict) -> dict:
        rid = _submit(self.endpoint, args, self._k(payload))
        return {"ok": True, "request_id": rid,
                "note": "poll via router job; webhook resumes CloudFlow later"}


@register
class FluxEditAdapter(_Fal):
    capability = "image_edit"
    name = "fal.flux_edit"
    endpoint = "fal-ai/flux-3/edit"

    def run(self, payload: dict) -> dict:
        return self.submit(payload, {"prompt": str(payload.get("prompt") or ""),
                                     "image_urls": payload.get("images") or []})


@register
class WanFalAdapter(_Fal):
    capability = "video_scene"
    name = "fal.wan_3"
    endpoint = "fal-ai/wan/v2.2-a14b/text-to-video"

    def run(self, payload: dict) -> dict:
        return self.submit(payload, {"prompt": str(payload.get("prompt") or "")})


@register
class KlingLipsyncAdapter(_Fal):
    """Decoupled lipsync: finished video + cloned audio in, speaking Dad out.
    If Kling is beaten next month, swap this one adapter."""
    capability = "lip_sync"
    name = "fal.kling_lipsync"
    endpoint = "fal-ai/kling-video/lipsync/audio-to-video"

    def run(self, payload: dict) -> dict:
        if not payload.get("video_url") or not payload.get("audio_url"):
            raise ProviderNotConfigured("lip_sync: needs video_url + audio_url")
        return self.submit(payload, {"video_url": payload["video_url"],
                                     "audio_url": payload["audio_url"]})


@register
class TripoAdapter(_Fal):
    """Mesh fallback next to Meshy genesis."""
    capability = "mesh"
    name = "fal.tripo"
    endpoint = "tripo3d/tripo/v2.5/image-to-3d"

    def run(self, payload: dict) -> dict:
        if not payload.get("image_url"):
            raise ProviderNotConfigured("mesh: needs image_url")
        return self.submit(payload, {"image_url": payload["image_url"]})
