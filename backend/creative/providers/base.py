"""Provider adapters: capability in, artifact out. No caller outside this
package names a model endpoint (no fal.subscribe / DashScope calls anywhere
else). Free-first: every capability resolves $0 by default; paid adapters
run only with explicit approval + whoever's key (server or BYO).
"""
from __future__ import annotations


class ProviderError(Exception):
    pass


class ProviderNotConfigured(ProviderError):
    """Right adapter, no key/approval. Never a surprise bill."""


class BaseAdapter:
    #: capability this adapter serves, e.g. "lip_sync"
    capability = ""
    #: stable name, e.g. "local.jaw_bake"
    name = ""
    #: True when this run costs provider money
    paid = False
    #: cost to the END USER in cents (0 = free to them, even if subsidized)
    cost_to_user_cents = 0
    #: True when OddHobb subsidizes the provider cost (free-tier Meshy)
    subsidized = False
    #: env vars holding this adapter's key (BYO payload api_key checked first)
    key_envs: tuple = ()

    def is_available(self) -> bool:
        return True

    def run(self, payload: dict) -> dict:
        """payload in (scene fragment), {"ok": True, ...artifact refs} out."""
        raise NotImplementedError
