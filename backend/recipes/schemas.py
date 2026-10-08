"""Recipe schema: the executable product contract (card actual.md).

A recipe is versioned, immutable once published, and says WHAT a product
is — never provider names, never coordinates. Providers satisfy named
capabilities; renderers own geometry; the compiler binds a person.
"""
from __future__ import annotations

REQUIRED_TOP = ("id", "version", "status", "product", "eligibility",
                "ranking", "inputs", "renderer", "outputs")
VALID_STATUSES = ("draft", "published", "retired")
VALID_SUBJECTS = ("person", "pet", "couple", "family")


def validate_recipe(r: dict) -> list[str]:
    """[] = publishable, else the blocking reasons."""
    gaps = []
    if not isinstance(r, dict):
        return ["recipe must be an object"]
    for k in REQUIRED_TOP:
        if k not in r:
            gaps.append(f"missing {k}")
    if not isinstance(r.get("version"), int):
        gaps.append("version must be int")
    if r.get("status") not in VALID_STATUSES:
        gaps.append(f"status must be one of {VALID_STATUSES}")
    prod = r.get("product") or {}
    if not isinstance(prod.get("price_cents"), int):
        gaps.append("product.price_cents must be int")
    if not prod.get("sku"):
        gaps.append("product.sku required")
    elig = r.get("eligibility") or {}
    if not isinstance(elig.get("occasion"), list) or not elig.get("occasion"):
        gaps.append("eligibility.occasion must be a non-empty list")
    for s in (elig.get("subjects") or []):
        if s not in VALID_SUBJECTS:
            gaps.append(f"eligibility subject {s!r} must be one of {VALID_SUBJECTS}")
    if not isinstance(elig.get("min_photos", 0), int):
        gaps.append("eligibility.min_photos must be int")
    inp = r.get("inputs") or {}
    photos = (inp.get("photos") or {})
    if photos and not isinstance(photos.get("count", 1), int):
        gaps.append("inputs.photos.count must be int")
    rend = r.get("renderer") or {}
    if not rend.get("template"):
        gaps.append("renderer.template required (existing layout it drives)")
    gen = r.get("generation") or {}
    for gname, g in gen.items():
        if not isinstance(g, dict):
            gaps.append(f"generation.{gname} must be an object")
            continue
        if g.get("kind") == "image":
            box = g.get("box")
            if not isinstance(box, list) or len(box) != 4:
                gaps.append(f"generation.{gname}.box must be [x,y,w,h]")
    return gaps
