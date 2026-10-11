"""Comedic theory validators: every theory is a hard gate, not a vibe.

templates/theories.json holds 25 theories (classical + Freud techniques +
Attardo LMs), each with binary `conditions`. This module runs what can be
decided deterministically and queues the rest for adjudication (Jev/LLM):
verdicts are PASS / FAIL / NEEDS_JUDGE. A set (night's material) runs
through every theory to produce a theory-hit matrix; analytics later joins
hits to outcomes, which is how dependent relationships (theory X works
only given premise Y) emerge instead of being asserted.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2] / "templates" / "theories.json"

_EXAGGERATION_LEX = (
    "billion", "million", "never", "always", "everyone", "nobody",
    "infinitely", "greatest", "worst", "entirely", "literally everybody",
)


def load_theories(root: Path | None = None) -> dict[str, dict]:
    base = root or ROOT
    try:
        data = json.loads(base.read_text())
    except (OSError, ValueError):
        return {}
    out = {}
    for t in data.get("theories", []):
        if isinstance(t, dict) and t.get("id"):
            out[t["id"]] = t
    return out


def _repeated_phrase(text: str) -> str | None:
    words = re.findall(r"[a-z']+", text.lower())
    for n in (4, 3, 2):
        seen: dict[tuple, int] = {}
        for i in range(len(words) - n + 1):
            g = tuple(words[i:i + n])
            seen[g] = seen.get(g, 0) + 1
            if seen[g] >= 2 and len(" ".join(g)) > 8:
                return " ".join(g)
    return None


def _deterministic(theory_id: str, text: str, feats: dict) -> tuple[str, str]:
    """Try to decide without a judge. Returns (verdict, reason) where
    verdict is PASS/FAIL/NEEDS_JUDGE. Conservative: only repetition and
    exaggeration-lexicon can PASS mechanically; absence never FAILs a
    semantic gate (absence of evidence is not evidence of absence)."""
    low = text.lower()
    if theory_id == "repetition_variation":
        rep = _repeated_phrase(text)
        if rep:
            return "PASS", f"repeated: {rep!r}"
        return "NEEDS_JUDGE", "no exact repeat found; needs ear check"
    if theory_id == "exaggeration":
        hits = [w for w in _EXAGGERATION_LEX if w in low]
        if hits:
            return "PASS", f"scale lexicon: {hits[0]}"
        return "NEEDS_JUDGE", "no scale markers; needs judge"
    if theory_id == "superiority":
        if feats.get("butt"):
            return "NEEDS_JUDGE", f"butt={feats['butt']!r}: needs endorsement check"
        return "NEEDS_JUDGE", "no annotated butt; needs judge"
    return "NEEDS_JUDGE", "semantic gate; queued for adjudication"


def validate_text(text: str, features: dict | None = None,
                  root: Path | None = None) -> dict:
    """Run one joke/bit through every theory. Returns hits + judge queue."""
    feats = features or {}
    theories = load_theories(root)
    hits, queue = [], []
    for tid, t in theories.items():
        verdict, reason = _deterministic(tid, text or "", feats)
        if verdict == "PASS":
            hits.append({"theory": tid, "why": reason})
        elif verdict == "NEEDS_JUDGE":
            for c in (t.get("conditions") or []):
                q = c.get("question", "") if isinstance(c, dict) else str(c)
                if q:
                    queue.append({"theory": tid, "gate": q})
                    break
    return {"ok": True, "hits": hits, "judge_queue": queue,
            "theories_checked": len(theories)}


def validate_set(items: list[dict], root: Path | None = None) -> dict:
    """items: [{id, text, features}]. Returns per-item hits + aggregate
    theory profile + full judge queue. The matrix analytics joins to outcomes."""
    per_item, agg = [], {}
    queue = []
    checked = 0
    for it in items:
        r = validate_text(it.get("text", ""), it.get("features") or {}, root)
        checked = r.get("theories_checked", 0)
        per_item.append({"id": it.get("id"), "hits": [h["theory"] for h in r["hits"]]})
        queue.extend([{**q, "item": it.get("id")} for q in r["judge_queue"]])
        for h in r["hits"]:
            agg[h["theory"]] = agg.get(h["theory"], 0) + 1
    return {"ok": True, "items": per_item, "aggregate": agg,
            "judge_queue": queue, "theories_checked": checked}


# ── comment taxonomy v0 (§22): keyword patterns, no LLM. Specificity first:
# longer, mechanism-naming comments outrank generic laughs. Returns label +
# confidence + extracted references for evidence links.
_COMMENT_PATTERNS: list[tuple[str, str]] = [
    ("RETURN_REQUEST", r"bring .*back|more .*episodes?|need .*season|when.?s the next|encore"),
    ("QUOTE", r"\"[^\"]{4,}\"|stealing|my new motto|gonna (say|use)|that line about"),
    ("JOKE_MECHANISM", r"the way (he|she|they|it) .*|thinking .* finished me|lost it when|the fact .* killed me|doubling down|misunderstand"),
    ("PERFORMANCE", r"\bpause\b|timing|delivery|deadpan|stare|hold that|beat after"),
    ("VISUAL", r"\bhat\b|looks? like|tiny .*|animation|mesh|face|neck"),
    ("VOICE", r"\bvoice\b|sound(s|ing)? like|accent|tone of"),
    ("TOPIC", r"too real|literally me|airport|my job|sled|musher|kibble"),
    ("NEGATIVE_CHARACTER", r"hate (this|him|her|it)|annoying|unfunny guy"),
    ("NEGATIVE_WRITING", r"same joke|repetitive|lazy writing|try-hard"),
    ("CONFUSION", r"don.?t get|what happened|confused|makes no sense"),
    ("AI_ARTIFACT", r"melts?|fingers|glitch|ai (slop|looking)|robotic voice"),
    ("PACKAGING_MISMATCH", r"thumbnail.*nothing|clickbait|not in the video"),
    ("CHARACTER_POSITIVE", r"kill(ing|ed) me|love (him|her|them|this (guy|dog|character))|my favorite|icon|killing it"),
    ("GENERIC_POSITIVE", r"\blol\b|haha|funny|😂|lmao|great|brilliant|hilarious"),
]


def classify_comment(text: str) -> dict:
    """Label one feedback string. Specific labels win over generic ones;
    confidence scales with specificity (length + mechanism words)."""
    t = (text or "").strip()
    low = t.lower()
    words = len(low.split())
    for label, pat in _COMMENT_PATTERNS:
        m = re.search(pat, low)
        if m:
            specific = words >= 6 or label not in ("GENERIC_POSITIVE",)
            conf = round(min(0.95, 0.45 + 0.03 * words + (0.15 if specific else 0)), 2)
            out = {"label": label, "confidence": conf,
                   "specific": specific,
                   "sentiment": "negative" if label.startswith("NEGATIVE_") or label in ("CONFUSION",) else "positive",
                   "character_reference": bool(re.search(r"sled|nolan|dog|husky|sergeant", low)),
                   "quote_reference": label == "QUOTE",
                   "request_more": label == "RETURN_REQUEST",
                   "mechanism_reference": label in ("JOKE_MECHANISM", "PERFORMANCE")}
            return out
    return {"label": "GENERIC_POSITIVE", "confidence": 0.2, "specific": False,
            "sentiment": "neutral" if not t else "positive",
            "character_reference": False, "quote_reference": False,
            "request_more": False, "mechanism_reference": False}
