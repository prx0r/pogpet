# Provenance: copied from /home/ubuntu/petsy/engine/compose.py (prx0r/bwick).
# Read-only there. The 36-concept template library: concept + identity + names
# -> {design_prompt, shot_list, ar_effect, base_variant}.
#!/usr/bin/env python3
"""compose() — concept + identity + names -> render plan.

Contract (concepts.md "Composition rules"):
    compose(concept_id, photos[], names[]) ->
        { design_prompt, shot_list, ar_effect, base_variant }

Guards enforced here, not by convention:
  * photos[] are immutable identity — the prompt never redraws face/markings
  * <= 3 identity meshes per order (props never count)
  * ip_check must be `pass` before anything may back a listing pack
  * state stays `concept_only` until a print sample is approved

Usage:
  python3 compose.py --concept WZ-S1 --photo front.png --photo body.png \
      --name James --pet Buster [--pet-variant] [--for-listing] [--out plan.json]
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

CATALOG = Path(__file__).resolve().parent / "data" / "catalog.json"

MAX_IDENTITY_MESHES = 3

IDENTITY_MESHES = {"solo": 1, "couple": 2, "solo_pet": 2, "pet": 1}

BASE_VARIANT = {
    "solo": "single",
    "couple": "couple",
    "solo_pet": "single_pet_plinth",
    "pet": "single",
}
# names required per category (pet name counts where a pet is in the order)
HUMAN_NAMES = {"solo": 1, "couple": 2, "solo_pet": 1, "pet": 0}
PET_NAMES = {"solo": 0, "couple": 0, "solo_pet": 1, "pet": 1}

AR_EFFECT = {
    "christmas": "snowfall",
    "mystic": "lumos",
    "wizard": "lumos",
}
AR_BY_CATEGORY = {"couple": "kiss", "solo_pet": "lumos"}


class ComposeError(ValueError):
    """A guard rejected the plan. Message is customer/agent facing."""


def load_catalog(path: Path = CATALOG) -> dict:
    if not path.exists():
        raise ComposeError(
            f"catalog not found at {path} — run `python3 build_catalog.py` first"
        )
    return json.loads(path.read_text())


def get_concept(concept_id: str, catalog: dict | None = None) -> dict:
    catalog = catalog or load_catalog()
    for c in catalog["concepts"]:
        if c["id"].upper() == concept_id.upper():
            return c
    raise ComposeError(
        f"unknown concept {concept_id!r} — valid ids: "
        + ", ".join(c["id"] for c in catalog["concepts"][:6]) + ", …"
    )


def identity_count(category: str, pet_variant: bool = False) -> int:
    """How many identity meshes this order needs. Props never count."""
    if pet_variant:
        if category != "couple":
            raise ComposeError(
                "a pet variant only exists on the couple category "
                "(see PROPS.md — family stays cut)"
            )
        return 3
    return IDENTITY_MESHES[category]


def guard_listing(concept: dict) -> None:
    if concept.get("ip_check") != "pass":
        raise ComposeError(
            f"ip_check is {concept.get('ip_check', 'unset')!r} for {concept['id']} — "
            "scan titles/tags against docs/trademark.md and set it to `pass` "
            "before this concept may back a listing (AGENTS.md rule 4)"
        )


def build_design_prompt(concept: dict, photos: list[str], names: list[str],
                        pet_variant: bool) -> str:
    """The prompt overlay rules: identity comes from photos and is never redrawn."""
    id_note = (
        "IDENTITY SOURCE: customer photographs listed below. Reproduce the exact "
        "face shape, coat colour, eye colour and all markings. Identity is "
        "immutable — the scene, costume, props and backdrop are overlays and must "
        "never alter identity."
    )
    who = ", ".join(names) if names else "the subject"
    lines = [
        f"Concept {concept['id']} — {concept['name']} ({concept['world']} world, "
        f"{concept['category']} category)",
        f"Scene: {concept['scene']}",
        f"Subjects: {who}",
        id_note,
        "Photos: " + ", ".join(photos),
        "Style: collectible figurine, matte paint, warm key light, plain studio "
        "backdrop, centred composition with headroom for caption overlay.",
    ]
    if pet_variant:
        lines.append(
            "Variant: couple base PLUS one animal companion on the shared plinth "
            "(3 identity meshes — allowed; anything more is a family and is cut)."
        )
    if concept.get("tags"):
        lines.append("Notes: " + "; ".join(concept["tags"]))
    lines.append("State: concept_only — no print sample approved yet.")
    return "\n".join(lines)


def build_shot_list(concept: dict) -> list[dict]:
    """Render/photography shots for one concept listing."""
    shots = [
        {"slot": 1, "kind": "hero", "desc": "finished figure, 3/4 front, dark bg, gold accent"},
        {"slot": 2, "kind": "before_after", "desc": "customer photo -> 3D preview morph pair"},
        {"slot": 3, "kind": "lifestyle", "desc": "on a real shelf, human hand for scale"},
        {"slot": 4, "kind": "variant", "desc": "alternate angle / pet variant if offered"},
        {"slot": 5, "kind": "process", "desc": "upload -> preview -> printed, triptych"},
        {"slot": 6, "kind": "detail", "desc": "base close-up: name, date, QR"},
        {"slot": 7, "kind": "packaging", "desc": "gift box, open"},
        {"slot": 8, "kind": "scale", "desc": "next to a coin or ruler"},
        {"slot": 9, "kind": "social_proof", "desc": "review screenshots (from first orders on)"},
        {"slot": 10, "kind": "ar", "desc": "screen recording of the spell/action playing"},
    ]
    return shots


def resolve_props(wanted: list[str] | None, catalog: dict) -> list[dict]:
    """Look props up by name or PRP id. Props are candidates only — resolving
    one never makes it a printable part of an order (concepts.md rule 4)."""
    if not wanted:
        return []
    library = catalog.get("props") or []
    if not library:
        raise ComposeError(
            "the catalog carries no prop library — run `build_catalog.py` "
            "(data/props.json must exist)")
    by_name = {str(p.get("name", "")).lower(): p for p in library}
    by_id = {str(p.get("id")).lower(): p for p in library if p.get("id")}
    out, missing = [], []
    for w in wanted:
        key = str(w).strip().lower()
        hit = by_id.get(key) or by_name.get(key)
        if hit is None:
            missing.append(w)
        elif hit not in out:
            out.append(hit)
    if missing:
        sample = ", ".join(str(p.get("name")) for p in library[:8])
        raise ComposeError(
            f"unknown prop(s): {', '.join(missing)} — library has "
            f"{len(library)} (try: {sample}, …)")
    return out


def compose(concept_id: str, photos: list[str], names: list[str],
            pet_variant: bool = False, for_listing: bool = False,
            catalog: dict | None = None,
            props: list[str] | None = None) -> dict:
    catalog = catalog or load_catalog()
    concept = get_concept(concept_id, catalog)

    # --- guards -----------------------------------------------------------
    if for_listing:
        guard_listing(concept)
    if not photos:
        raise ComposeError("photos[] is required — identity comes from customer photos")

    meshes = identity_count(concept["category"], pet_variant)
    if meshes > MAX_IDENTITY_MESHES:
        raise ComposeError(
            f"{meshes} identity meshes exceeds the {MAX_IDENTITY_MESHES}-mesh ceiling "
            "(PROPS.md). Families are cut."
        )

    need_h, need_p = HUMAN_NAMES[concept["category"]], PET_NAMES[concept["category"]]
    # names are counted loosely: at least the humans the category demands
    if len(names) < need_h:
        raise ComposeError(
            f"{concept['category']} needs {need_h} human name(s), got {len(names)}"
        )
    if concept["category"] in ("solo_pet", "pet") and len(names) < need_h + need_p:
        raise ComposeError(
            f"{concept['category']} needs a pet name as well"
        )

    resolved = resolve_props(props, catalog)

    plan = {
        "concept_id": concept["id"],
        "world": concept["world"],
        "category": concept["category"],
        "identity_meshes": meshes,
        "identity": {
            "source_photos": list(photos),
            "immutable": True,
            "rule": "scene/costume/props/backdrop are overlays; never regenerate identity",
        },
        "names": list(names),
        "base_variant": BASE_VARIANT[concept["category"]],
        "ar_effect": AR_BY_CATEGORY.get(concept["category"]) or AR_EFFECT.get(concept["world"], "lumos"),
        "design_prompt": build_design_prompt(concept, photos, names, pet_variant),
        "shot_list": build_shot_list(concept),
        "cross_links": concept.get("cross_links", []),
        "cross_link_rule": "separate products in one scene pack, promoted as a bundle — never one order",
        "props": resolved,
        "props_candidate_only": True,
        "ip_check": concept.get("ip_check", "pending"),
        "state": "concept_only",
    }
    return plan


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--concept", required=True)
    ap.add_argument("--photo", action="append", default=[], dest="photos")
    ap.add_argument("--name", action="append", default=[], dest="names")
    ap.add_argument("--prop", action="append", default=[], dest="props",
                    help="prop name or PRP id (repeatable)")
    ap.add_argument("--pet-variant", action="store_true")
    ap.add_argument("--for-listing", action="store_true")
    ap.add_argument("--catalog")
    ap.add_argument("--out")
    a = ap.parse_args(argv)

    catalog = load_catalog(Path(a.catalog)) if a.catalog else None
    try:
        plan = compose(a.concept, a.photos, a.names, a.pet_variant,
                       a.for_listing, catalog, props=a.props)
    except ComposeError as e:
        print(f"BLOCKED: {e}", file=sys.stderr)
        return 2

    text = json.dumps(plan, indent=2, ensure_ascii=False) + "\n"
    if a.out:
        Path(a.out).write_text(text)
        print(f"plan {plan['concept_id']} -> {a.out} "
              f"(meshes={plan['identity_meshes']}, ar={plan['ar_effect']}, "
              f"state={plan['state']})")
    else:
        sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
