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
    key_envs = ("FAL_KEY",)
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
    endpoint = "blackforestlabs/flux-3/edit-image"

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


# ── card scene plates (docs/card-audit.md gap 1) ────────────────────
# cardp0 §10: AI generates scene (people, place, light), NEVER typography.
# Every plate prompt carries the no-text guard; headlines stay renderer-owned.
NO_TEXT_GUARD = ("no text, no words, no letters, no captions, no speech bubbles, "
                 "no watermark, no logo")


def plate_prompt(scene: str, *, style: str = "") -> str:
    """Scene description → fal prompt with the no-typography guard baked in."""
    base = str(scene or "").strip()
    if style:
        base = f"{base}, {style} style"
    return f"{base}. {NO_TEXT_GUARD}." if base else NO_TEXT_GUARD


def log_spend(*, owner: str, adapter: str, endpoint: str,
              est_cost_usd: float, request_id: str) -> None:
    """Append-only fal.ai ledger (data/fal_credits.jsonl). Ask-first lives in
    the router (paid adapters need explicit approval); this is the receipt."""
    from pathlib import Path as _P
    import time as _t
    root = _P(__file__).resolve().parent.parent.parent.parent
    ledger = root / "data" / "fal_credits.jsonl"
    try:
        ledger.parent.mkdir(parents=True, exist_ok=True)
        with open(ledger, "a") as f:
            f.write(json.dumps({"ts": _t.time(), "owner": owner,
                                "adapter": adapter, "endpoint": endpoint,
                                "est_cost_usd": est_cost_usd,
                                "request_id": request_id}) + "\n")
    except OSError:
        pass


@register
class FluxPlateAdapter(_Fal):
    """Text-free scene plates for the five card grammars (FLUX.1 dev,
    ~$0.025/MP, commercial use). Renderer composites real typography after."""
    capability = "scene_plate"
    name = "fal.flux_plate"
    endpoint = "fal-ai/flux/dev"

    def run(self, payload: dict) -> dict:
        scene = str(payload.get("scene") or "")
        if not scene:
            raise ProviderNotConfigured("scene_plate: needs scene description")
        owner = str(payload.get("owner") or "anon")
        out = self.submit(payload, {
            "prompt": plate_prompt(scene, style=str(payload.get("style") or "")),
            "image_size": payload.get("image_size") or "portrait_4_3",
            "num_images": 1, "enable_safety_checker": True})
        log_spend(owner=owner, adapter=self.name, endpoint=self.endpoint,
                  est_cost_usd=0.025, request_id=out.get("request_id", ""))
        return {**out, "cost_note": "~$0.025/MP, bills on success only"}


@register
class PhotaAdapter(_Fal):
    """Identity-locked hero plates (Phota by PhotaLabs): Dad genuinely in the
    scene, face/geometry preserved. $0.09/image 1K, $0.18 4K; training
    (30-50 photos → Subject Token) is a separate $2.90 step via action=train.
    Without a profile_id it still generates — profile only tightens identity."""
    capability = "identity_plate"
    name = "fal.phota"
    endpoint = "fal-ai/phota"

    def run(self, payload: dict) -> dict:
        action = str(payload.get("action") or "generate")
        owner = str(payload.get("owner") or "anon")
        if action == "train":
            photos = payload.get("photos") or []
            if len(photos) < 5:
                raise ProviderNotConfigured("phota train: needs ≥5 photo URLs "
                                            "(30-50 recommended)")
            out = self.submit(payload, {"images": photos})
            log_spend(owner=owner, adapter=self.name,
                      endpoint="fal-ai/phota/create-profile",
                      est_cost_usd=2.90, request_id=out.get("request_id", ""))
            return {**out, "cost_note": "$2.90/training run"}
        scene = str(payload.get("scene") or "")
        if not scene:
            raise ProviderNotConfigured("identity_plate: needs scene description")
        args: dict = {"prompt": plate_prompt(scene, style=str(payload.get("style") or ""))}
        if payload.get("profile_id"):
            args["profile_id"] = payload["profile_id"]
        if payload.get("image_urls"):
            args["image_urls"] = payload["image_urls"]
            endpoint = "fal-ai/phota/edit"
        else:
            endpoint = self.endpoint
        rid = _submit(endpoint, args, self._k(payload))
        out = {"ok": True, "request_id": rid,
               "note": "poll via router job; webhook resumes CloudFlow later"}
        log_spend(owner=owner, adapter=self.name, endpoint=endpoint,
                  est_cost_usd=0.09, request_id=rid)
        return {**out, "cost_note": "$0.09/image 1K ($0.18 4K)"}


@register
class UpscaleAdapter(_Fal):
    """Sub-200dpi rescue before print (Clarity crystal-upscaler, portrait-tuned,
    ~$0.016/MP). Called when save warns 'may print soft' — never silent."""
    capability = "upscale"
    name = "fal.upscale"
    endpoint = "clarityai/crystal-upscaler"

    def run(self, payload: dict) -> dict:
        if not payload.get("image_url"):
            raise ProviderNotConfigured("upscale: needs image_url")
        owner = str(payload.get("owner") or "anon")
        out = self.submit(payload, {"image_url": payload["image_url"]})
        log_spend(owner=owner, adapter=self.name, endpoint=self.endpoint,
                  est_cost_usd=0.016, request_id=out.get("request_id", ""))
        return {**out, "cost_note": "~$0.016/MP, face-detail tuned"}
