"""Joke recipes: Kill Tony shapes the scripting engine plans into.

The LLM supplies profile details (who Dad is, what happened); the recipe
supplies structure (where the laugh lives). Recipes from the Ella rubric
(225 sets): specific opener, numbers, address, escalation, pivots, closer.
"""
from __future__ import annotations

RECIPES = {
    "dad_game_winner": {
        "beats": ["specific opener (≤15 words, a scene, not an abstraction)",
                  "escalation (start grounded, get wilder)",
                  "punch (the turn: But/And pivot)",
                  "tag (second laugh on the same premise)",
                  "closer (≤15 words, IS the joke)"],
        "needs": ["one true detail", "one number", "one escalation"],
    },
    "profile_roast": {
        "beats": ["loving address (name them)",
                  "true observation (profile fact)",
                  "absurd escalation (their quirk, weaponized)",
                  "callback closer"],
        "needs": ["profile fact", "interest", "memory"],
    },
    "family_scandal": {
        "beats": ["breaking-news framing", "specific allegation (time/place)",
                  "denial quote", "escalating agenda", "deadpan sign-off"],
        "needs": ["event", "detail", "quote"],
    },
    "tired_parents": {
        "beats": ["shared misery opener", "two concrete examples",
                  "absurd comparison", "tiny victorious closer"],
        "needs": ["relatable pain", "specifics"],
    },
}


def plan(recipe_id: str, facts: dict) -> dict:
    """Beat plan with the profile facts slotted in. Deterministic."""
    r = RECIPES.get(recipe_id, RECIPES["dad_game_winner"])
    return {"recipe": recipe_id if recipe_id in RECIPES else "dad_game_winner",
            "beats": list(r["beats"]), "needs": list(r["needs"]),
            "facts": {k: facts.get(k) for k in ("name", "detail", "number",
                                                "interest", "memory", "quote")}}
