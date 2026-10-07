"""Three-variant joke sets: main, darker, personal.

One brief → three model×motif prompts (NO spend — prompts only). The human
picks; the pick lands in the taste ledger as a DPO pair (chosen > rejected)
for the future house model. Volume of picks, not model size, is the moat.
"""
from __future__ import annotations

import json
import time
import uuid
from pathlib import Path

from . import persona

VARIANTS = (
    ("main", "dolphin", "picked motif — the set we think is funniest"),
    ("darker", "dolphin", "LOVING_EXECUTIONER — same facts, sharper teeth"),
    ("personal", "grok", "motif matched to THEIR humour + conversation context"),
)

MODEL_FOR = {
    "dolphin": "cognitivecomputations/dolphin-mistral-24b-venice-edition",
    "grok": "x-ai/grok-4.7",
}


def plan_variants(brief: dict, profile: dict) -> list[dict]:
    """Three prompts, zero spend. Each names model + motif + rules."""
    motif, _ = persona.pick(profile)
    out = []
    for slot, model_key, desc in VARIANTS:
        m = "LOVING_EXECUTIONER" if slot == "darker" else motif
        examples = persona.examples(1, persona.MOTIF_TO_ELLA.get(m, ""))
        out.append({
            "variant_id": f"jv_{uuid.uuid4().hex[:8]}",
            "slot": slot,
            "model": MODEL_FOR[model_key],
            "motif": m,
            "blurb": desc,
            "example_motif": (examples[0]["motif"] if examples else ""),
        })
    return out


def record_pick(owner: str, chosen_id: str, variants: list[dict],
                *, root: Path | None = None) -> dict:
    """Persist the human pick as DPO fuel: chosen > each rejected."""
    base = root or Path("data")
    base.mkdir(parents=True, exist_ok=True)
    chosen = next((v for v in variants if v["variant_id"] == chosen_id), None)
    if not chosen:
        raise ValueError("unknown variant_id")
    pairs = []
    for v in variants:
        if v["variant_id"] == chosen_id:
            continue
        pairs.append({"prompt": v["motif"], "chosen": chosen_id,
                      "rejected": v["variant_id"], "model": v["model"]})
    rec = {"ts": time.time(), "owner": owner, "chosen": chosen,
           "rejected": [v["variant_id"] for v in variants if v["variant_id"] != chosen_id],
           "dpo_pairs": len(pairs)}
    with (base / "joke_picks.jsonl").open("a") as f:
        f.write(json.dumps(rec) + "\n")
    return rec
