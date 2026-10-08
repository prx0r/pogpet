"""Backwards classifier — transcript in, theory tags out.

Working backwards: take any bit (a Louis CK transcript, one of our comics,
a tweet) and recover which theories are doing the work. Heuristic, offline,
transparent: each detector is a documented textual signal, not a black box.
Scores are 0..1 confidences, not verdicts; pairs of tags are the point
(single-theory bits are rare and usually weak).

Use: ingest -> tag -> store tags on the premise -> learn which combos land.
"""
from __future__ import annotations

import re

PATTERNS: dict[str, list[str]] = {
    "status_reversal": [r"\b(boss|king|ceo|manager|scientist|adult|parent)s?\b.*\b(now|actually|instead)\b",
                        r"\bwho('s| is) (really|actually) in charge\b",
                        r"\brealize[sd]? they'?re\b",
                        r"\bare we\b.{0,40}\bassistants?\b",
                        r"\blab assistants?\b"],
    "identity_contradiction": [r"\bcan'?t\b.{0,40}\b(supposed to|job|role)\b",
                               r"\bafraid of\b", r"\bwithout (a|any) sense of\b"],
    "incongruity": [r"\bbut (then|actually|instead)\b", r"\bturns out\b",
                    r"\bexpected\b.{0,30}\binstead\b"],
    "resolution": [r"\boh\b.{0,20}\b(actually|right|i see)\b", r"\bthat'?s why\b",
                   r"\bsuddenly\b.{0,30}\bmakes sense\b"],
    "benign_violation": [r"\b(died|death|kill|plague|threat|danger|scary)\b",
                         r"\btoo soon\b"],
    "bisociation": [r"\blike a\b.{0,30}\b(but|except)\b", r"\bbasically\b",
                    r"\bit'?s just\b"],
    "rigidity": [r"\b(policy|rule|procedure|protocol|must|required|pending)\b",
                 r"\bdropdown\b"],
    "escalation": [r"\bthen\b.*\bthen\b", r"\bday \d\b", r"\bmore\b.{0,20}\bmore\b",
                 r"\bwithin\b.{0,25}\bminutes?\b"],
    "repetition_variation": [r"(.{8,40}?)\1", r"\bagain\b"],
    "self_awareness": [r"\bi know\b", r"\baware\b", r"\bexactly what\b"],
    "mask_collision": [r"\bmask\b", r"\bpretend", r"\bactually\b.{0,20}\b(exhausted|tired|sad|angry)\b"],
    "audience_alliance": [r"\bwe all know\b", r"\bobviously\b", r"\bof course\b"],
    "specificity": [r"\b\d+(\.\d+)?\s?(g|mm|TB|GB|bars?|houses?|agents?)\b",
                    r"\b[A-Z][a-z]+ (Street|Avenue|Institute|Department)\b"],
    "literalise": [r"\bliterally\b", r"\bphysically\b"],
    "contrast": [r"\bbefore\b.{0,40}\bafter\b", r"\bused to\b.{0,30}\bnow\b",
               r"\bmiracle\b"],
    "literalisation": [r"\bliterally\b"],
}


def _hits(text: str, patterns: list[str]) -> int:
    t = text.lower()
    return sum(1 for p in patterns if re.search(p, t))


def classify(text: str) -> dict[str, float]:
    """text -> {theory: confidence}. Empty text -> {}."""
    if not text or not text.strip():
        return {}
    out: dict[str, float] = {}
    for theory, pats in PATTERNS.items():
        h = _hits(text, pats)
        if h:
            out[theory] = round(min(1.0, 0.4 + 0.3 * h), 3)
    # literalise/literalisation are one theory with two spellings
    if "literalisation" in out:
        out["literalise"] = max(out.get("literalise", 0), out.pop("literalisation"))
    return dict(sorted(out.items(), key=lambda kv: -kv[1]))


def top(text: str, n: int = 3) -> list[str]:
    return list(classify(text))[:n]
