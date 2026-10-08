"""Locked constraints — what agents cannot change, anywhere.

Sources of truth, in order: line design_contracts (locked lists), card
renderer ownership (back/type/grammars have no inputs by construction),
product-wide brand rules. This module only READS them into one view that
MCP serves; enforcement lives in save/manifold/stem checks, order gates,
and the renderers themselves.
"""
from __future__ import annotations

from backend import config

# Product-wide locks no single line may override.
GLOBAL_LOCKS = [
    "card back is renderer-owned (brand mark, tagline, URL) — no inputs exist",
    "card type system is fixed (Fraunces/Caveat/Inter) — no font inputs exist",
    "card grammars are hard constraints (panels, bubbles, lengths)",
    "never metal hardware in product photos or designs",
    "prices are EST until a live Prodigi SKU quote lands",
]


def locks_for(line: str) -> dict:
    """Machine-readable lock list for one product line."""
    spec = config.STUDIO_LINES.get(line)
    if spec is None:
        raise KeyError(line)
    contract = spec.get("design_contract") or {}
    enforced = []
    if contract.get("envelope_mm"):
        enforced.append("envelope_mm (save rejects oversize)")
    import json as _json
    try:
        ad = _json.loads((config.ROOT / "scripts" / "factory" /
                          "adapters" / f"{line}.json").read_text())
    except OSError:
        ad = {}
    if (ad.get("stem") or {}).get("dia_mm"):
        enforced.append(f"stem dia {ad['stem']['dia_mm']}mm (save rejects violations)")
    return {"line": line,
            "locked": list(contract.get("locked") or []),
            "enforced_by_save": enforced,
            "verify_open": list(contract.get("verify") or []),
            "method": (spec.get("personalization") or {}).get("method", ""),
            "global": GLOBAL_LOCKS}


def all_locks() -> dict:
    return {"global": GLOBAL_LOCKS,
            "lines": {lid: locks_for(lid)["locked"]
                      for lid in sorted(config.STUDIO_LINES)}}
