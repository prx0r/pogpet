"""Agent review loop (quality verdicts + concrete fix ops).

The agent looks at a render (artifact, card revision, video) and gets back a
structured verdict: scores, reasons, and fixes it can apply itself through
the revise endpoint. Heuristic checks run free; vision-model aesthetic review
stays a staged BYOC lane. The agent's brain interprets "make them happier" —
we provide the eyes and the hands.
"""
from __future__ import annotations

import sqlite3

# mood -> deterministic render adjustments (palette + expression intent).
# No pixels guessed: palettes are fixed, expressions are template vocab.
MOODS = {
    "happier": {"palette": "bright", "expression": "grin",
                "caption_hint": "shorter, punchier, exclamation welcome"},
    "funnier": {"palette": "bold", "expression": "deadpan",
                "caption_hint": "one beat shorter, land the noun last"},
    "warmer": {"palette": "warm", "expression": "happy",
               "caption_hint": "softer words, keep names"},
    "classier": {"palette": "ink", "expression": "neutral",
                 "caption_hint": "fewer words, larger type"},
}

PALETTES = {
    "bright": {"bg": "#fff6e8", "ink": "#141414", "accent": "#e34536"},
    "bold": {"bg": "#122433", "ink": "#ffffff", "accent": "#e34536"},
    "warm": {"bg": "#f8f1e6", "ink": "#22221d", "accent": "#a64332"},
    "ink": {"bg": "#ffffff", "ink": "#111111", "accent": "#8a6a2f"},
}


def review_artifact(c: sqlite3.Connection, artifact_id: str) -> dict:
    """Verdict + fix ops for one artifact. Reads only, $0."""
    from . import artifacts as _art
    row = c.execute("SELECT * FROM render_artifacts WHERE id=?", (artifact_id,)).fetchone()
    if row is None:
        return {"ok": False, "error": "no such artifact"}
    a = dict(row)
    scores, reasons, fixes = {}, [], []
    if a.get("qc_status") == "passed":
        scores["qc"] = 1.0
    else:
        scores["qc"] = 0.0
        reasons.append(f"qc={a.get('qc_status')}: re-render before judging")
        fixes.append({"op": "render", "why": "no passed artifact yet"})
    if (a.get("output_kind") or "") in ("preview", "print_master"):
        if not a.get("width") or not a.get("height"):
            reasons.append("zero dimensions")
            fixes.append({"op": "render", "why": "empty image"})
        else:
            scores["dimensions"] = 1.0
            reasons.append(f"{a['width']}x{a['height']} {a.get('dpi', 0)}dpi")
    if a.get("output_kind") == "print_master" and not a.get("dpi"):
        scores["print"] = 0.0
        reasons.append("print master without DPI")
        fixes.append({"op": "render", "contract": "card_5x7_folded_v1",
                      "why": "re-render with a print contract"})
    else:
        scores.setdefault("print", 1.0)
    if a.get("output_kind") in ("motion", "video", "mp4"):
        if not a.get("duration"):
            reasons.append("zero duration")
            fixes.append({"op": "render", "why": "empty video"})
        else:
            scores["duration"] = 1.0
    verdict = "ship" if all(v >= 1.0 for v in scores.values()) and scores else "revise"
    return {"ok": True, "artifact_id": artifact_id, "verdict": verdict,
            "scores": scores, "reasons": reasons, "fixes": fixes,
            "moods": sorted(MOODS),
            "hint": "apply fixes via POST /api/creative/revise (new revision each time)"}


def apply_mood(copy: dict, mood: str) -> tuple[dict, dict]:
    """Deterministic mood application: returns (new_copy, render_opts).
    Caption text itself stays the agent's words — we only tune rendering."""
    m = MOODS.get((mood or "").lower())
    if not m:
        return copy, {}
    return dict(copy), {"palette": m["palette"], "expression": m["expression"],
                        "caption_hint": m["caption_hint"]}
