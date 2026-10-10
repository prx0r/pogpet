"""transform(): capability + references + instruction + contract.

Callers name a published transform id and hand over reference assets.
The registry supplies the instruction template; the capability router
picks today's adapter. One expensive transformation becomes reusable
inventory: the returned artifact carries its provenance (transform id +
version + adapter) so renderers and credit accounting can cite it.

No network happens here beyond what the resolved adapter does — and paid
adapters raise ProviderNotConfigured without approval + key, never billing
by surprise.
"""
from __future__ import annotations

from . import transforms as _reg
from .providers import router as _router
from .providers.base import ProviderNotConfigured

# Import for side effect: adapters self-register on import. No network.
from .providers import alibaba as _ali  # noqa: F401
from .providers import fal as _fal  # noqa: F401
from .providers import higgsfield as _hf  # noqa: F401
from .providers import local as _local  # noqa: F401
from .providers import mesh as _mesh  # noqa: F401
from .providers import meta as _meta  # noqa: F401


class TransformError(Exception):
    pass


def transform(transform_id: str, references: list | None = None, *,
              owner: str = "anon", policy: str = "free",
              route: str = "", keychain: dict | None = None,
              instruction_override: str = "") -> dict:
    """Run one published transform. Returns ok/artifact/provenance or
    ok False with error. Never raises on bad input (adapter errors from
    paid paths surface as ok False with the reason)."""
    owner = (owner or "anon").strip()[:80] or "anon"
    t = _reg.get(transform_id)
    if not t:
        return {"ok": False, "error": f"unknown or retired transform {transform_id}"}
    refs = list(references or [])
    need = int((t.get("references") or {}).get("min_images", 0))
    if len(refs) < need:
        return {"ok": False,
                "error": f"{transform_id} needs {need} reference image(s), got {len(refs)}"}
    capability = t.get("capability", "")
    instruction = instruction_override.strip() or (
        t.get("instruction") or {}).get("template", "")
    payload = {
        "images": refs,
        "prompt": instruction,
        "preserve": t.get("preserve", []),
        "output": t.get("output", {}),
        "qc": t.get("qc", {}),
        "transform_id": t["id"],
        "transform_version": t.get("version", 1),
    }
    try:
        if policy != "free" or route:
            out = _router.run(capability, payload, policy=policy,
                              route=route, keychain=keychain)
        else:
            out = _router.run_for_owner(capability, owner, payload,
                                        policy=policy, route=route)
    except ProviderNotConfigured as e:
        return {"ok": False, "error": str(e)}
    except Exception as e:  # noqa: BLE001 — adapter failure is data
        return {"ok": False, "error": f"{capability} failed: {e}"}
    out["provenance"] = {
        "transform_id": t["id"],
        "transform_version": t.get("version", 1),
        "capability": capability,
        "references_used": len(refs),
    }
    out.setdefault("ok", True)
    return out


def describe(transform_id: str) -> dict:
    """The transform card: what it needs, what it makes. No execution."""
    t = _reg.get(transform_id)
    if not t:
        return {"ok": False, "error": f"unknown or retired transform {transform_id}"}
    return {"ok": True, "transform": {k: t[k] for k in
            ("id", "version", "capability", "references", "preserve",
             "output", "qc", "prompt_id", "products") if k in t}}
