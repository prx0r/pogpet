"""Meta adapters (STAGED — connector programme).

Muse Image for plates, SAM for cutouts/masks. Reached through Meta's
connector/MCP onboarding with OAuth account linking — same six oddhobb_*
tools Muse sees. No keys held here yet.
Docs: https://dev.meta.ai/products/connectors
"""
from __future__ import annotations

from .base import ProviderNotConfigured
from .router import register
from .base import BaseAdapter


@register
class MuseImageAdapter(BaseAdapter):
    capability = "identity_image"
    name = "meta.muse_image"
    paid = True

    def is_available(self) -> bool:
        return False

    def run(self, payload: dict) -> dict:
        raise ProviderNotConfigured("meta.muse_image: staged, no connector yet")


@register
class SamAdapter(BaseAdapter):
    capability = "image_edit"
    name = "meta.sam"
    paid = True

    def is_available(self) -> bool:
        return False

    def run(self, payload: dict) -> dict:
        raise ProviderNotConfigured("meta.sam: staged, no connector yet")
