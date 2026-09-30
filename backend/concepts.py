"""The 36-concept template library, wired to our product cards.

Backed by `concepts_src.py` (vendored from petsy/bwick's `engine/compose.py`)
and `data/concepts/catalog.json`:

    3 worlds     wizard · mystic · christmas
    4 categories solo · couple · solo_pet · pet
    3 each  =    36 concepts      WZ-S1 · M-C1 · X-P1 …

`compose()` is strict about how many human/pet names each category demands and
refuses to run without photos — those guards matter for print, but a storefront
card just needs the art direction, so `compose_for()` supplies sensible
defaults and lets the caller pass one subject name.
"""
from __future__ import annotations

from pathlib import Path

from . import config
CATALOG_PATH = config.ROOT / "data" / "concepts" / "catalog.json"

from . import concepts_src as C          # noqa: E402

AR_EFFECT = getattr(C, "AR_EFFECT", {})

C.CATALOG = CATALOG_PATH                 # point vendored loader at our copy

WORLD_TINT = {
    "wizard":   {"glow": (139, 61, 255), "accent": "#8B3DFF", "label": "wizard"},
    "mystic":   {"glow": (124, 255, 107), "accent": "#7CFF6B", "label": "mystic"},
    "christmas": {"glow": (229, 52, 27), "accent": "#E5341B", "label": "christmas"},
}

# compose() wants a specific number of human and pet names per category.
_HUMAN_FALLBACK = ["You", "Your favourite human"]


class ConceptError(Exception):
    pass


def load_catalog() -> dict:
    if not CATALOG_PATH.exists():
        raise ConceptError("catalog missing — data/concepts/catalog.json")
    import json
    return json.loads(CATALOG_PATH.read_text())


def list_concepts() -> list[dict]:
    """Flat list for the storefront picker."""
    cat = load_catalog()
    out = []
    for c in cat.get("concepts", []):
        out.append({
            "id": c["id"], "world": c["world"], "category": c["category"],
            "name": c["name"], "scene": c["scene"],
            "identity_meshes": c.get("identity_meshes", 1),
            "ip_check": c.get("ip_check", ""),
            "accent": WORLD_TINT.get(c["world"], {}).get("accent", "#8B3DFF"),
            "ar_effect": AR_EFFECT.get(c["world"], ""),
        })
    return out


def get(concept_id: str) -> dict:
    for c in list_concepts():
        if c["id"].upper() == concept_id.upper():
            return c
    raise ConceptError(
        f"unknown concept {concept_id!r} — try one of: "
        + ", ".join(c["id"] for c in list_concepts()[:8]) + ", …"
    )


def names_for(category: str, subject: str) -> list[str]:
    try:
        nh = C.HUMAN_NAMES.get(category, 1)
        npet = C.PET_NAMES.get(category, 0)
    except Exception:
        nh, npet = 1, 0
    humans = _HUMAN_FALLBACK[:nh]
    pets = [subject] if npet else []
    return humans + pets


def compose_for(concept_id: str, subject: str = "your pet",
                photo: str = "<mesh>") -> dict:
    """Full compose() plan with storefront-safe defaults.

    Returns {concept, design_prompt, shot_list, ar_effect, world, accent, …}
    """
    concept = C.get_concept(concept_id, load_catalog())
    names = names_for(concept["category"], subject)
    try:
        plan = C.compose(concept["id"], photos=[photo], names=names,
                        catalog=load_catalog())
    except C.ComposeError as e:
        # still hand back the art direction even if a print guard trips
        plan = {
            "concept_id": concept["id"],
            "design_prompt": C.build_design_prompt(concept, [photo], names, False),
            "shot_list": C.build_shot_list(concept),
            "guard": str(e),
        }
    world = concept["world"]
    plan.update({
        "concept": concept,
        "world": world,
        "accent": WORLD_TINT.get(world, {}).get("accent", "#8B3DFF"),
        "ar_effect": AR_EFFECT.get(world, ""),
        "names": names,
        "subject": subject,
    })
    return plan
