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
    if (a.get("output_kind") or "") in ("preview", "print_master"):
        content = _content_check(c, a)
        scores["content"] = content["score"]
        reasons += content["reasons"]
        fixes += content["fixes"]
    verdict = "ship" if all(v >= 1.0 for v in scores.values()) and scores else "revise"
    return {"ok": True, "artifact_id": artifact_id, "verdict": verdict,
            "scores": scores, "reasons": reasons, "fixes": fixes,
            "moods": sorted(MOODS),
            "hint": "apply fixes via POST /backend/api/creative/revise (new revision each time)"}


def _content_check(c: sqlite3.Connection, a: dict) -> dict:
    """Pixels + star slot: fail blank artwork and missing subjects.
    Reads only, $0. Never throws — unreadable pixels are a finding, not a 500."""
    from PIL import Image as _Image
    reasons, fixes = [], []
    try:
        from . import projects as _cproj
        rev = _cproj.get_revision(c, a.get("project_id", ""), int(a.get("revision") or 0))
        subjects = (rev.get("scene") or {}).get("subjects") or []
        with_photo = False
        for s in subjects:
            for aid in (s.get("asset_ids") or []):
                row = c.execute("SELECT 1 FROM photos WHERE id=? AND owner=?",
                                (aid, a.get("owner", ""))).fetchone()
                if row:
                    with_photo = True
                    break
            if with_photo:
                break
        if subjects and not with_photo:
            return {"score": 0.0,
                    "reasons": ["star slot has no resolvable photo — subject chose nothing on file"],
                    "fixes": [{"op": "revise", "why": "attach a subject photo that belongs to this owner"}]}
    except Exception:  # noqa: BLE001 — scene problems are findings too
        pass
    try:
        from backend import storage as _storage
        import tempfile as _tf
        from pathlib import Path as _P
        with _tf.NamedTemporaryFile(suffix=".png") as tmp:
            _storage.get(a.get("storage_key") or "", _P(tmp.name))
            img = _Image.open(tmp.name).convert("RGB").resize((120, 120))
        px = list(img.getdata())
        corners = px[:5] + px[-5:]
        bg = tuple(sum(ch) // len(ch) for ch in zip(*corners))
        flat = sum(1 for p in px if all(abs(p[i] - bg[i]) < 12 for i in range(3)))
        if flat / max(1, len(px)) > 0.97:
            return {"score": 0.0,
                    "reasons": ["blank artwork — panels empty, no photo or art rendered"],
                    "fixes": [{"op": "render", "why": "no drawable content reached the canvas"}]}
        return {"score": 1.0, "reasons": ["artwork has rendered content"], "fixes": []}
    except Exception as e:  # noqa: BLE001
        return {"score": 0.0, "reasons": [f"artwork unreadable: {str(e)[:80]}"],
                "fixes": [{"op": "render", "why": "artifact bytes missing"}]}


def apply_mood(copy: dict, mood: str) -> tuple[dict, dict]:
    """Deterministic mood application: returns (new_copy, render_opts).
    Caption text itself stays the agent's words — we only tune rendering."""
    m = MOODS.get((mood or "").lower())
    if not m:
        return copy, {}
    return dict(copy), {"palette": m["palette"], "expression": m["expression"],
                        "caption_hint": m["caption_hint"]}
