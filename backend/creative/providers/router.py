"""Capability router (devplan-2026-10-07): models change, capabilities don't.

Resolution per capability: free default first, then BYO-key paid adapters
(owner's key preferred, server key fallback), each gated on explicit
approval. Callers say run(capability=..., ...); the router decides whether
that means Blender, edge-tts, Wan 3.0, Kling, or next month's model.
"""
from __future__ import annotations

from .base import BaseAdapter, ProviderNotConfigured

# capability -> ordered adapter names. "local.*" are $0 in-repo paths.
ROUTES: dict[str, list[str]] = {
    "identity_image":  ["local.composite", "alibaba.qwen_image", "fal.flux_edit"],
    "image_edit":      ["fal.flux_edit", "alibaba.qwen_image"],
    "video_scene":     ["local.pose_bake", "alibaba.wan_3", "fal.wan_3"],
    "lip_sync":        ["local.jaw_bake", "fal.kling_lipsync"],
    "voice_tts":       ["local.edge_tts", "alibaba.qwen_tts", "openrouter.tts"],
    "voice_clone":     ["alibaba.qwen_enroll"],
    "cloned_tts":      ["alibaba.qwen_tts_vc"],
    "realtime_voice":  ["local.stub", "alibaba.qwen_omni", "gemini.live"],
    "mesh":            ["local.meshy", "fal.tripo"],
    "music":           ["local.procedural"],
}

_ADAPTERS: dict[str, BaseAdapter] = {}


def register(adapter: BaseAdapter) -> BaseAdapter:
    _ADAPTERS[adapter.name] = adapter()
    return adapter


def resolve(capability: str, *, allow_paid: bool = False,
            keychain: dict | None = None) -> BaseAdapter:
    """First available adapter on the route. Paid adapters need allow_paid
    AND a key (BYO owner key wins, server key fallback)."""
    last_error: Exception | None = None
    for name in ROUTES.get(capability, []):
        ad = _ADAPTERS.get(name)
        if ad is None:
            continue
        if ad.paid and not allow_paid:
            last_error = ProviderNotConfigured(f"{name}: paid, needs approval")
            continue
        try:
            if ad.is_available():
                return ad
        except Exception as e:  # noqa: BLE001 — probe, don't crash
            last_error = e
    raise ProviderNotConfigured(
        f"no adapter for {capability}" + (f" ({last_error})" if last_error else ""))


# ── compute policies: users/agents pick intent, never providers ────────
# free      → only OddHobb/open/deterministic stack
# use-mine  → connected (vault) providers allowed
# best      → best connected model for the task
# specific  → advanced: exact provider.adapter (payload: route="fal.kling_lipsync")

POLICIES = ("free", "use-mine", "best", "specific")


def resolve_policy(capability: str, policy: str = "free", *,
                   route: str = "", keychain: dict | None = None) -> BaseAdapter:
    """Intent-based resolution. Specific pins an adapter (still needs its key);
    use-mine/best allow paid with vault/server keys; free never spends."""
    if policy not in POLICIES:
        raise ProviderNotConfigured(f"unknown policy — {', '.join(POLICIES)}")
    if policy == "specific":
        ad = _ADAPTERS.get(route)
        if ad is None:
            raise ProviderNotConfigured(f"unknown route {route}")
        if ad.paid and not keychain and not _server_key_for(ad):
            raise ProviderNotConfigured(f"{route}: needs a connected provider")
        return ad
    return resolve(capability, allow_paid=(policy in ("use-mine", "best")),
                   keychain=keychain)


def _server_key_for(ad: BaseAdapter) -> bool:
    import os
    envs = {"alibaba": "DASHSCOPE_API_KEY", "fal": "FAL_KEY",
            "openrouter": "OPENROUTER_API_KEY"}
    prov = ad.name.split(".")[0]
    return bool(os.environ.get(envs.get(prov, ""), ""))


def run(capability: str, payload: dict | None = None, *,
        allow_paid: bool = False, keychain: dict | None = None,
        policy: str = "free", route: str = "") -> dict:
    if policy != "free" or route:
        ad = resolve_policy(capability, policy, route=route, keychain=keychain)
    else:
        ad = resolve(capability, allow_paid=allow_paid, keychain=keychain)
    out = ad.run({**(payload or {}), **({"api_key": keychain["key"]} if keychain and keychain.get("key") else {})})
    out.setdefault("adapter", ad.name)
    out.setdefault("paid", ad.paid)
    out.setdefault("policy", policy)
    return out


def route_table() -> dict[str, list[str]]:
    return {k: list(v) for k, v in ROUTES.items()}
