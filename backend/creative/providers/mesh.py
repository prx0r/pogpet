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
