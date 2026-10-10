"""Cloudflare Workers AI adapter (STAGED — needs CF credentials + approval).

Model supermarket on our own Cloudflare account: klein-4b/9b face edits,
flux-1-schnell plates, llama copy. Same run() API as every provider:
text in, artifact out. Paid per call (cents) — router treats as paid,
FAIL-closed without CF_API_TOKEN + CF_ACCOUNT_ID. Bills to our account,
so human approval per the money rules.
Docs: https://developers.cloudflare.com/workers-ai/
"""
from __future__ import annotations

import base64
import json
import os
import urllib.request

from .base import ProviderNotConfigured
from .router import register
from .base import BaseAdapter


def _creds(payload: dict) -> tuple[str, str]:
    tok = str(payload.get("cf_token") or os.environ.get("CF_API_TOKEN") or "")
    acct = str(payload.get("cf_account") or os.environ.get("CF_ACCOUNT_ID") or "")
    return tok, acct


def _run(model: str, body: dict, payload: dict, timeout: int = 300) -> dict:
    tok, acct = _creds(payload)
    if not tok or not acct:
        raise ProviderNotConfigured(
            "cfworker: needs CF_API_TOKEN + CF_ACCOUNT_ID (env or payload)")
    req = urllib.request.Request(
        f"https://api.cloudflare.com/client/v4/accounts/{acct}/ai/run/{model}",
        data=json.dumps(body).encode(), method="POST",
        headers={"Authorization": f"Bearer {tok}",
                 "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode() or "{}")


def _image_bytes(res: dict) -> bytes | None:
    """Workers AI returns base64 image (or a list) — normalize to bytes."""
    try:
        result = res.get("result") or {}
        img = result.get("image") or result.get("image_url") or result
        if isinstance(img, list):
            img = img[0] if img else None
        if isinstance(img, dict):
            img = img.get("image") or img.get("data")
        if isinstance(img, str):
            if img.startswith("data:"):
                img = img.split(",", 1)[1]
            return base64.b64decode(img)
    except Exception:  # noqa: BLE001
        pass
    return None


class _CF(BaseAdapter):
    paid = True
    key_envs = ("CF_API_TOKEN",)

    def is_available(self) -> bool:
        return bool(os.environ.get("CF_API_TOKEN", "").strip())

    def _save(self, blob: bytes, owner: str, name: str) -> str:
        from pathlib import Path as _P
        from backend import config as _cfg
        d = _P(_cfg.DATA) / "cfgen" / owner
        d.mkdir(parents=True, exist_ok=True)
        p = d / name
        p.write_bytes(blob)
        return str(p)


@register
class CFPlateAdapter(_CF):
    """Text-free scene/backdrop plates (flux-1-schnell). ~cents per plate,
    generated once per template and reused forever."""
    capability = "scene_plate"
    name = "cfworker.flux_plate"
    endpoint = "@cf/black-forest-labs/flux-1-schnell"

    def run(self, payload: dict) -> dict:
        scene = str(payload.get("scene") or payload.get("prompt") or "")
        if not scene:
            raise ProviderNotConfigured("scene_plate: needs scene description")
        owner = str(payload.get("owner") or "anon")
        res = _run(self.endpoint, {"prompt": scene + ", no text, no letters, no watermark"}, payload)
        blob = _image_bytes(res)
        if not blob:
            raise ProviderNotConfigured(f"cfworker: no image back: {str(res)[:200]}")
        import time as _t
        return {"ok": True, "artifact": {"key": self._save(
            blob, owner, f"plate-{int(_t.time())}.png")},
            "cost_note": "Workers AI flux-schnell, cents"}


@register
class CFEditAdapter(_CF):
    """Face-crop edits (flux-2-klein-4b default, 9b retry). Reference image
    + instruction in, transformed image out. The MVP face-swap tier."""
    capability = "identity_transform"
    name = "cfworker.klein_edit"
    endpoint = "@cf/black-forest-labs/flux-2-klein-4b"

    def run(self, payload: dict) -> dict:
        import time as _t
        imgs = payload.get("images") or []
        if payload.get("image_url"):
            imgs = [payload["image_url"]] + imgs
        if not imgs:
            raise ProviderNotConfigured("identity_transform: needs a reference image")
        prompt = str(payload.get("prompt") or "")
        if not prompt:
            raise ProviderNotConfigured("identity_transform: needs an instruction")
        model = self.endpoint if "9b" not in str(payload.get("model") or "") else \
            "@cf/black-forest-labs/flux-2-klein-9b"
        owner = str(payload.get("owner") or "anon")
        res = _run(model, {"prompt": prompt, "image": imgs[0]}, payload)
        blob = _image_bytes(res)
        if not blob:
            raise ProviderNotConfigured(f"cfworker: no image back: {str(res)[:200]}")
        return {"ok": True, "artifact": {"key": self._save(
            blob, owner, f"klein-{int(_t.time())}.png")},
            "cost_note": "Workers AI klein, ~$0.0015/face-crop"}
