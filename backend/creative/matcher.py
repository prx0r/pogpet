"""Deterministic template matcher (cardgen.md §7).

Hard eligibility filter, then weighted scoring, then a human-readable
reason. The LLM only ever explains or soft-ranks — never decides alone.
"""
from __future__ import annotations

WEIGHTS = {
    "occasion": 30, "relationship": 10, "interest": 15, "humour": 15,
    "assets": 10, "novelty": 5, "engagement": 10, "cost": 5,
}

RELATIONSHIP_TOPICS = {
    "dad": ["family", "dads"], "mum": ["family"], "grandad": ["family"],
    "grandma": ["family"], "partner": ["family"], "friend": ["family"],
    "pet": ["pets"],
}

INTEREST_TOPICS = {
    "golf": ["sports"], "football": ["sports"], "fishing": ["sports"],
    "cricket": ["sports"], "rugby": ["sports"], "tennis": ["sports"],
    "cycling": ["sports"], "running": ["sports"], "gaming": ["games"],
    "cooking": ["food"], "coffee": ["food"], "beer": ["food"],
    "music": ["music"], "films": ["films"], "reading": ["books"],
    "gardening": ["home"], "dogs": ["pets"], "cats": ["pets"],
}


def eligible(template: dict, brief: dict) -> list[str]:
    """[] = eligible, else the blocking reasons."""
    blocks = []
    req = template.get("requirements", {})
    tax = template.get("taxonomy", {})
    rec = brief.get("recipient", {})
    avail = brief.get("available_assets", {})
    occ = (brief.get("occasion") or {}).get("id", "general")
    if occ not in (tax.get("occasion") or []) and "general" not in (tax.get("occasion") or []):
        blocks.append(f"no {occ} support")
    need_subjects = int(req.get("subjects", 1))
    if need_subjects and not rec.get("subject_id"):
        blocks.append("needs a subject")
    have_faces = int(avail.get("confirmed_face_photos", 0) or avail.get("photos", 0))
    if have_faces < int(req.get("face_photos_min", 0)):
        blocks.append(f"needs {req.get('face_photos_min')} face photos, has {have_faces}")
    if req.get("mesh") and not (avail.get("meshes")):
        blocks.append("needs a mesh")
    if req.get("voice") and not avail.get("voice"):
        blocks.append("needs a voice")
    return blocks


def score(template: dict, brief: dict, *, seen: set[str] | None = None,
          engagement: dict | None = None) -> tuple[float, list[str]]:
    """(points, reasons). Deterministic: same brief + registry = same order."""
    tax = template.get("taxonomy", {})
    rec = brief.get("recipient", {})
    occ = (brief.get("occasion") or {}).get("id", "general")
    pts, reasons = 0.0, []
    if occ in (tax.get("occasion") or []):
        pts += WEIGHTS["occasion"]
        reasons.append(f"made for {occ}")
    rel = (rec.get("relationship") or "").lower()
    rel_topics = RELATIONSHIP_TOPICS.get(rel, ["family"] if rel else [])
    if any(t in (tax.get("topics") or []) for t in rel_topics):
        pts += WEIGHTS["relationship"]
        reasons.append(f"good for {rel or 'them'}")
    interests = [str(i).lower() for i in (rec.get("interests") or [])]
    topics = [str(t).lower() for t in (tax.get("topics") or [])]
    mapped = set()
    for i in interests:
        mapped.update(INTEREST_TOPICS.get(i, [i]))
    hits = [i for i in interests
            if any(i in t or t in i or m in topics for t in topics
                   for m in INTEREST_TOPICS.get(i, [i]))]
    if hits:
        pts += WEIGHTS["interest"]
        reasons.append(f"into {', '.join(hits[:2])}")
    try:
        from . import premises as _prem
        pre = _prem.match_premises(interests, topics)
        if pre:
            pts += 5
            reasons.append(f"premise ready: {pre[0]['text'][:60]}")
    except Exception:  # noqa: BLE001 — premises never break matching
        pass
    humour = rec.get("humour") or {}
    tones = [str(t).lower() for t in (tax.get("tone") or [])]
    hscore = 0.0
    if isinstance(humour, dict):
        if humour.get("absurd", 0) >= 0.6 and "ross" in tones:
            hscore = WEIGHTS["humour"]
        elif humour.get("sentimental", 0) >= 0.6 and "sentimental" in tones:
            hscore = WEIGHTS["humour"]
    elif isinstance(humour, list) and any(str(h).lower() in tones for h in humour):
        hscore = WEIGHTS["humour"]
    if hscore:
        pts += hscore
        reasons.append("matches their humour")
    avail = brief.get("available_assets", {})
    if int(avail.get("good_portraits", 0)) >= 2 or int(avail.get("confirmed_face_photos", 0)) >= 3:
        pts += WEIGHTS["assets"]
        reasons.append("great photos on file")
    if seen is not None and template["id"] not in seen:
        pts += WEIGHTS["novelty"]
    eng = (engagement or {}).get(template["id"], 0)
    if eng > 0:
        pts += min(WEIGHTS["engagement"], eng)
        reasons.append("picked before")
    pts += WEIGHTS["cost"] * 0.5  # placeholder: print lanes cost alike
    # buyer's actual words: lexical evidence against id/label/premise/caption
    ask = str((brief.get("request") or {}).get("prompt") or "").lower().split()
    ask = [w.strip(",.!?") for w in ask if len(w) > 3]
    if ask:
        hay = " ".join([str(template.get("id") or ""),
                        str((template.get("presentation") or {}).get("label") or ""),
                        str(template.get("premise") or ""),
                        str((template.get("presentation") or {}).get("example_caption") or "")]).lower()
        hits = sum(1 for w in ask if w in hay)
        if hits:
            pts += min(20, 4 * hits)
            reasons.append(f"matches your words ({hits})")
    return round(pts, 1), reasons


def match(brief: dict, templates: dict[str, dict], *,
          engagement: dict | None = None, seen: set[str] | None = None,
          limit: int = 5) -> list[dict]:
    ranked = []
    for tid, t in templates.items():
        blocks = eligible(t, brief)
        if blocks:
            continue
        pts, reasons = score(t, brief, engagement=engagement, seen=seen)
        ranked.append({"id": tid, "version": t.get("version", 1),
                       "score": pts, "reasons": reasons,
                       "format": t.get("format", tid),
                       "premise": t.get("premise", ""),
                       "tone": t.get("tone", []),
                       "renderers": t.get("renderers", {})})
    ranked.sort(key=lambda r: (-r["score"], r["id"]))
    return ranked[:limit]
