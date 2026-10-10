"""Mesh adapters: genesis only (freaktown rule, same here).

Meshy creates from real photos (single or 3-angle multi-image) inside the
existing free-tier + refund discipline. Tripo via fal is the fallback.
Nothing here synthesizes views, repairs, or animates — local Blender does.
"""
from __future__ import annotations

from .base import ProviderNotConfigured
from .router import register
from .base import BaseAdapter


@register
class MeshyAdapter(BaseAdapter):
    capability = "mesh"
    name = "local.meshy"
    paid = False  # free-tier accounted, ask-first; spend itself is BYO/user-approved
    subsidized = True  # OddHobb pays Meshy; $0 to the user under daily caps

    def is_available(self) -> bool:
        return True

    def run(self, payload: dict) -> dict:
        from backend import pipeline
        photo_id = str(payload.get("photo_id") or "")
        if not photo_id:
            raise ProviderNotConfigured("mesh: needs photo_id")
        return pipeline.start_mesh(photo_id, single=bool(payload.get("single")))


@register
class BlenderAdapter(BaseAdapter):
    """Local Blender manufacturing: emboss, repair, retarget. CPU, $0."""
    capability = "mesh"
    name = "local.blender"
    paid = False

    def is_available(self) -> bool:
        from pathlib import Path
        return Path("/home/ubuntu/blender/blender").exists()

    def run(self, payload: dict) -> dict:
        return {"ok": True, "mode": "local blender op",
                "note": "emboss via /api/design/make; repair via factory validate"}


@register
class TrellisAdapter(BaseAdapter):
    """Self-hosted TRELLIS.2 (MIT): PNG -> GLB on our own 24 GB GPU.
    $0 marginal per mesh once running — the Meshy exit: generate once in
    Meshy, then render per person for free. STAGED until TRELLIS_ENDPOINT
    is set (no GPU on this box). Same photo->mesh contract as Meshy."""
    capability = "mesh"
    name = "trellis.selfhost"
    paid = False
    key_envs = ("TRELLIS_ENDPOINT",)

    def is_available(self) -> bool:
        import os
        return bool(os.environ.get("TRELLIS_ENDPOINT", "").strip())

    def run(self, payload: dict) -> dict:
        import os
        import json as _json
        import urllib.request as _url
        ep = os.environ.get("TRELLIS_ENDPOINT", "").strip().rstrip("/")
        if not ep:
            raise ProviderNotConfigured(
                "trellis.selfhost: staged — set TRELLIS_ENDPOINT to a "
                "host with a 24 GB GPU running TRELLIS.2")
        photo_url = str(payload.get("photo_url") or "")
        if not photo_url:
            raise ProviderNotConfigured("mesh: needs photo_url")
        body = {"image_url": photo_url,
                "single": bool(payload.get("single", True))}
        req = _url.Request(ep + "/generate", data=_json.dumps(body).encode(),
                           method="POST",
                           headers={"Content-Type": "application/json"})
        with _url.urlopen(req, timeout=600) as r:
            return {"ok": True, "mode": "trellis",
                    "result": _json.loads(r.read().decode() or "{}")}
