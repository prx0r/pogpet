"""Premise library (templates.md): joke content packs by audience.

Formats are structures; premises are the jokes that fill them.
Cross format × audience × occasion = programmable shelf.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2] / "templates" / "premises"


def load_packs(root: Path | None = None) -> dict[str, dict]:
    out: dict[str, dict] = {}
    base = root or ROOT
    if not base.is_dir():
        return out
    for f in sorted(base.glob("*.json")):
        try:
            pack = json.loads(f.read_text())
        except (OSError, ValueError):
            continue
        if pack.get("pack") and isinstance(pack.get("premises"), list):
            out[pack["pack"]] = pack
    return out


def match_premises(interests: list[str], topics: list[str],
                   packs: dict[str, dict] | None = None) -> list[dict]:
    """Premises whose topics overlap the recipient's interests or the
    template's topics. Returns [{pack, id, text}] ranked by overlap."""
    packs = packs if packs is not None else load_packs()
    want = {str(i).lower() for i in interests} | {str(t).lower() for t in topics}
    scored = []
    for pack_id, pack in packs.items():
        for p in pack.get("premises", []):
            pt = {str(t).lower() for t in p.get("topics", [])}
            hit = want & pt
            if hit:
                scored.append({"pack": pack_id, "id": p["id"], "text": p["text"],
                               "overlap": sorted(hit)})
    scored.sort(key=lambda r: (-len(r["overlap"]), r["id"]))
    return scored
