"""Persona mechanics for roast sets (Ella M method, adapted for loved ones).

Ella's engine: pick ONE motif → hook a specific truth → deconstruct it →
land a dark truth → sign off. One target per set, no simile piles, every
joke anchored to something true. Same mechanics, warmer teeth.
"""
from __future__ import annotations

import json
from pathlib import Path

MOTIFS = {
    "LOVING_EXECUTIONER": ("CS", "brutal about them because you know them. "
                           "The cruelty is the intimacy — only family gets to say this."),
    "PROUD_ROAST": ("SPP", "bragging disguised as complaining. Every insult "
                    "is secretly a compliment about showing up."),
    "MYTHOLOGIST": ("GCP", "turn one true habit into legend. Whisper the gospel "
                    "of Dad according to Dad."),
    "HYPE_SQUAD": ("BIW", "ride for them so hard it becomes funny. "
                   "Their tiny victories are world-historical events."),
    "ACCOUNTANT": ("RHM", "everything they do has a cost-benefit analysis. "
                   "Run the numbers on their nonsense, find them wanting."),
}

RULES = ("One target per set — pick the single funniest true thing, never leave it. "
         "Max 2 similes per set; every other joke must be a specific true detail. "
         "No abstract nouns doing the work (no 'lizard brains', no 'langmuir directions'). "
         "PROSE stand-up only — never rhyme, couplets, verse or ballads. "
         "Modern diction — no thee/thou/thy. "
         "Closer is one short line that IS the joke. ")


def pick(profile: dict) -> tuple[str, str]:
    """Motif from humour profile. Absurd-high goes mythologist, roast-high
    goes executioner, sentimental-high goes hype squad, else proud roast."""
    h = profile.get("humour", {}) if isinstance(profile.get("humour"), dict) else {}
    if isinstance(h, list):
        h = {}
    if float(h.get("absurd", 0)) >= 0.7:
        m = "MYTHOLOGIST"
    elif float(h.get("roasting", 0)) >= 0.7:
        m = "LOVING_EXECUTIONER"
    elif float(h.get("sentimental", 0)) >= 0.6:
        m = "HYPE_SQUAD"
    else:
        m = "PROUD_ROAST"
    return m, MOTIFS[m][1]


def examples(n: int = 2, motif: str = "") -> list[dict]:
    p = Path(__file__).resolve().parent / "ella_examples.json"
    try:
        rows = json.loads(p.read_text())
    except Exception:  # noqa: BLE001
        return []
    if motif:
        rows = [r for r in rows if r.get("motif") == motif] or rows
    shorts = sorted([r for r in rows if (r.get("words") or 999) <= 130],
                    key=lambda r: r.get("words") or 0)
    return shorts[:n]


MOTIF_TO_ELLA = {
    "MYTHOLOGIST": "GCP", "LOVING_EXECUTIONER": "CS", "PROUD_ROAST": "SPP",
    "HYPE_SQUAD": "BIW", "ACCOUNTANT": "RHM",
}
