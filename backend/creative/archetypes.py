"""Archetype extraction — why a character is funny, as theory.

Operation: take a character (SpongeBob, Claude, the Fool), decompose into
traits, fire each trait against the theory bank, keep the theories that
bite. The result is an archetype: the comic engine without the copyrighted
expression. The engine then regenerates Pogtown-native instances.

Rule encoded here: borrow the cultural fact only when recognition is
essential; otherwise extract mechanics and regenerate.
"""
from __future__ import annotations

import json
from pathlib import Path

from backend.creative import blocks as _blocks

ROOT = _blocks.ROOT
PATH = ROOT / "archetypes.json"

# trait keywords -> theories they activate
TRAIT_THEORY = {
    "pride": ["status_reversal"],
    "simple work": ["status_reversal", "identity_contradiction"],
    "secret": ["audience_alliance"],
    "low status": ["status_reversal"],
    "earnest": ["rigidity"],
    "naive": ["audience_alliance", "self_awareness"],
    "optimis": ["rigidity"],
    "polite": ["mask_collision"],
    "strain": ["mask_collision"],
    "fool": ["status_reversal", "audience_alliance"],
    "literal": ["literalise"],
    "dignity": ["status_reversal"],
    "ritual": ["rigidity", "repetition_variation"],
    "craft": ["identity_contradiction"],
}


def load() -> dict[str, dict]:
    try:
        d = json.loads(PATH.read_text())
    except (OSError, ValueError):
        return {}
    return {a["id"]: a for a in d.get("archetypes", []) if a.get("id")}


def analyze_character(name: str, traits: list[str]) -> dict:
    """Character + trait list -> fired theories + engine sketch."""
    fired: dict[str, int] = {}
    for trait in traits:
        t = trait.lower()
        for kw, theories in TRAIT_THEORY.items():
            if kw in t:
                for th in theories:
                    fired[th] = fired.get(th, 0) + 1
    ranked = sorted(fired, key=lambda k: -fired[k])
    return {"character": name, "traits": traits,
            "theories_fired": ranked,
            "engine": ("; ".join(
                f"{th} x{fired[th]}" for th in ranked) or "no theories fired")}


def extract(source: str, traits: list[str], native_name: str,
            native_concept: str) -> dict:
    """Source character -> Pogtown-native archetype instance (validated)."""
    analysis = analyze_character(source, traits)
    bank = {t["id"] for t in
            (_blocks._read(_blocks.THEORIES_PATH) or {}).get("theories", [])}
    theories = [t for t in analysis["theories_fired"] if t in bank]
    if not theories:
        raise ValueError(f"no bank theories fired for {source}")
    return {"id": native_name.lower().replace(" ", "_"),
            "label": f"{native_name} (after {source})",
            "source_example": source, "traits": traits,
            "theories_fired": theories,
            "comic_engine": analysis["engine"],
            "pogtown_native": {"name": native_name,
                               "concept": native_concept}}
