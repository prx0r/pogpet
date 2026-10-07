"""Ella judge: deterministic Kill Tony rubric (freaktown heritage).

SET SCORE = +2 words 80–180 · +1 specific opener · +1 punchy closer (≤15w) ·
+1 numbers/details · +1 audience address · +1 escalation room (100+w) ·
+1 pivots (2+ And/But) · +1 persona voice · −1 over 200w · −1 abstract opener.
7–8 = 5/5 · 5–6 = 4/5 · 3–4 = 3/5 · else lower. No LLM, no spend, instant.
"""
from __future__ import annotations

import re

ABSTRACT_OPENERS = ("the ", "this ", "that ", "it ", "there ", "so ")


def score(lines: list[str], *, persona_words: tuple[str, ...] = ()) -> dict:
    text = " ".join(lines)
    words = text.split()
    n = len(words)
    pts, reasons = 0, []
    if 80 <= n <= 180:
        pts += 2
        reasons.append("full minute of material")
    first = (lines[0] if lines else "").strip()
    if first and not first.lower().startswith(ABSTRACT_OPENERS) and len(first.split()) <= 15:
        pts += 1
        reasons.append("specific opener")
    last = (lines[-1] if lines else "").strip()
    if last and len(last.split()) <= 15:
        pts += 1
        reasons.append("punchy closer")
    if re.search(r"\d", text):
        pts += 1
        reasons.append("specific numbers")
    if re.search(r"\byou\b", text, re.I):
        pts += 1
        reasons.append("audience address")
    if n >= 100:
        pts += 1
        reasons.append("room to escalate")
    pivots = len(re.findall(r"\b(and|but)\b", text, re.I))
    if pivots >= 2:
        pts += 1
        reasons.append(f"{pivots} pivots")
    if persona_words and any(w.lower() in text.lower() for w in persona_words):
        pts += 1
        reasons.append("persona voice")
    # through-line: one TOPIC held across the set (Ella rule — never leave it).
    # Name-addressing ("oh Dad") doesn't count; the joke's subject does.
    from collections import Counter
    nouns = re.findall(r"\b(golf|christmas|pie|nap|naps|sleep|snore|putter|turkey|lunch|mum)\b",
                       text, re.I)
    top = Counter(n.lower() for n in nouns).most_common(1)
    if top and top[0][1] >= 2:
        pts += 1
        reasons.append(f"through-line: {top[0][0]}")
    # simile piles are salad, not jokes
    similes = len(re.findall(r"\blike\b|\bas\b", text, re.I))
    if similes > 6:
        pts -= 2
        reasons.append(f"simile pile ({similes})")
    # verse is not stand-up: rhyming line-endings fail the set
    ends = [re.sub(r"[^a-z]", "", ln.split()[-1].lower()) for ln in lines if ln.split()]
    rhymes = sum(1 for a, b in zip(ends, ends[1:])
                 if len(a) > 3 and len(b) > 3 and (a[-3:] == b[-3:] or a[-2:] == b[-2:]))
    if rhymes >= 3:
        pts -= 3
        reasons.append(f"rhyming verse ({rhymes} couplets) — prose only")
    if n > 200:
        pts -= 1
        reasons.append("over 200 words")
    if first.lower().startswith(ABSTRACT_OPENERS):
        pts -= 1
        reasons.append("abstract opener")
    stars = 5 if pts >= 7 else 4 if pts >= 5 else 3 if pts >= 3 else 2
    return {"points": pts, "stars": stars, "reasons": reasons, "words": n}
