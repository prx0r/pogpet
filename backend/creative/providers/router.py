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
    "mesh":            ["local.meshy", "trellis.selfhost", "fal.tripo"],
    "music":           ["local.procedural"],
    "scene_plate":     ["fal.flux_plate"],
    "identity_plate":  ["local.composite", "fal.phota"],
    "upscale":         ["fal.upscale"],
    # transformation library (vision/multimedia.md): providers change,
    # capabilities don't. Soul ID wins when a persistent identity exists;
    # direct Alibaba is the cheap high-volume default; fal hosts the exotic.
    "subject_cutout":      ["fal.birefnet"],
    "identity_transform":  ["local.composite", "higgsfield.soul",
                            "alibaba.qwen_image", "fal.flux_edit"],
    "multi_reference_edit": ["alibaba.qwen_image", "fal.flux_edit"],
    "brand_style":         ["local.composite", "alibaba.qwen_image"],
    "text_heavy_art":      ["alibaba.qwen_image", "fal.flux_edit"],
    "consistent_image_set": ["alibaba.wan_3", "fal.wan_3"],
    "local_edit":          ["fal.flux_edit", "alibaba.qwen_image"],
    "product_packshot":    ["local.composite", "higgsfield.marketing"],
    "marketplace_image":   ["higgsfield.marketing", "local.composite"],
}

_ADAPTERS: dict[str, BaseAdapter] = {}


def register(adapter: BaseAdapter) -> BaseAdapter:
    _ADAPTERS[adapter.name] = adapter()
    return adapter


def _has_key(ad: BaseAdapter, keychain: dict | None) -> bool:
    import os
    if keychain and keychain.get("key"):
        return True
    return any(os.environ.get(e) for e in (ad.key_envs or ()))


def resolve(capability: str, *, allow_paid: bool = False,
            keychain: dict | None = None) -> BaseAdapter:
    """First available adapter on the route. Free policy only resolves
    adapters free TO THE USER (subsidized Meshy genesis counts: daily caps +
    refunds, $0 to them). Paid adapters need allow_paid AND a reachable key
    (BYO keychain or server env) — otherwise they are skipped, not errored."""
    last_error: Exception | None = None
    for name in ROUTES.get(capability, []):
        ad = _ADAPTERS.get(name)
        if ad is None:
            continue
        if ad.paid and not allow_paid:
            last_error = ProviderNotConfigured(f"{name}: paid, needs approval")
            continue
        if ad.paid and not _has_key(ad, keychain):
            last_error = ProviderNotConfigured(f"{name}: paid, no key connected")
            continue
        if ad.cost_to_user_cents > 0 and not allow_paid:
            last_error = ProviderNotConfigured(f"{name}: costs the user, needs approval")
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
        if ad.paid and not _has_key(ad, keychain):
            raise ProviderNotConfigured(f"{route}: needs a connected provider key")
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
    args = dict(payload or {})
    if keychain and keychain.get("key") and ad.paid:
        args.setdefault("api_key", keychain["key"])
    out = ad.run(args)
    out.setdefault("adapter", ad.name)
    out.setdefault("paid", ad.paid)
    out.setdefault("policy", policy)
    return out


# adapter name prefix -> vault provider id, for BYO key injection
ADAPTER_PROVIDERS = {
    "fal": "fal", "alibaba": "alibaba", "higgsfield": "higgsfield",
    "openrouter": "openrouter", "meta": "meta",
}


def run_for_owner(capability: str, owner: str, payload: dict | None = None,
                  *, policy: str = "free", route: str = "") -> dict:
    """Owner-scoped run: pulls the owner's vault key for the resolved paid
    adapter (BYO first, server env fallback inside adapters). Free policy
    never touches the vault."""
    from backend import db, vault as _vault
    keychain = None
    if policy in ("use-mine", "best", "specific"):
        name = route or (ROUTES.get(capability, [None])[0] or "")
        prov = ADAPTER_PROVIDERS.get(name.split(".")[0], "")
        if prov:
            with db.connect() as c:
                _vault.ensure_tables(c)
                try:
                    secret = _vault.use(c, owner, prov)
                    keychain = {"key": secret, "provider": prov}
                except KeyError:
                    keychain = None
    return run(capability, payload, allow_paid=(policy != "free"),
               keychain=keychain, policy=policy, route=route)


def route_table() -> dict[str, list[str]]:
    return {k: list(v) for k, v in ROUTES.items()}
