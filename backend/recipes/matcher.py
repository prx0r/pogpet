"""Recipe matcher: eligibility gate, then ranked reasons.

Deterministic: same brief + registry = same order. Scores mirror the
house weights (occasion 30, relationship 10, interest 15, humour 15,
assets 10, novelty 5) so taste rhymes across lanes without sharing code.
"""
from __future__ import annotations

WEIGHTS = {
    "occasion": 30, "relationship": 10, "interest": 15, "humour": 15,
    "assets": 10, "novelty": 5,
}

INTEREST_TOPICS = {
    "golf": ["sports"], "football": ["sports"], "fishing": ["sports"],
    "cricket": ["sports"], "rugby": ["sports"], "tennis": ["sports"],
    "gaming": ["games"], "cooking": ["food"], "music": ["music"],
    "dogs": ["pets"], "cats": ["pets"],
}


def eligible(recipe: dict, brief: dict) -> list[str]:
    """[] = eligible, else the blocking reasons."""
    blocks = []
    elig = recipe.get("eligibility") or {}
    occ = str((brief.get("occasion") or "general")).lower()
    occasions = [str(o).lower() for o in (elig.get("occasion") or [])]
    if occ not in occasions and "general" not in occasions:
        blocks.append(f"no {occ} support")
    kind = str(brief.get("subject_kind") or "person").lower()
    subjects = [str(s).lower() for s in (elig.get("subjects") or [])]
    if kind not in subjects:
        blocks.append(f"needs {elig.get('subjects')}")
    have = int(brief.get("photo_count", 0))
    need = int(elig.get("min_photos", 0))
    if have < need:
        blocks.append(f"needs {need} photos, has {have}")
    return blocks


def score(recipe: dict, brief: dict, *, seen: set[str] | None = None) -> tuple[float, list[str]]:
    """(points, reasons)."""
    rank = recipe.get("ranking") or {}
    rec = brief.get("recipient") or {}
    pts, reasons = 0.0, []
    occ = str((brief.get("occasion") or "general")).lower()
    occasions = [str(o).lower() for o in ((recipe.get("eligibility") or {}).get("occasion") or [])]
    if occ in occasions:
        pts += WEIGHTS["occasion"]
        reasons.append(f"made for {occ}")
    rel = str(rec.get("relationship") or "").lower()
    if rel:
        pts += WEIGHTS["relationship"]
        reasons.append(f"good for {rel}")
    interests = [str(i).lower() for i in (rec.get("interests") or [])]
    rtopics = [str(t).lower() for t in (rank.get("interests") or [])]
    hits = [i for i in interests
            if any(i in t or t in i for t in rtopics)
            or any(m in rtopics for m in INTEREST_TOPICS.get(i, [i]))]
    if hits:
        pts += WEIGHTS["interest"]
        reasons.append(f"into {', '.join(hits[:2])}")
    tones = [str(t).lower() for t in (rank.get("tones") or [])]
    ask = str(brief.get("vibe") or "").lower()
    if ask and any(w in tones for w in ask.replace(",", " ").split()):
        pts += WEIGHTS["humour"]
        reasons.append("matches the vibe")
    if int(brief.get("photo_count", 0)) >= 4:
        pts += WEIGHTS["assets"]
        reasons.append("great photos on file")
    if seen is not None and recipe["id"] not in seen:
        pts += WEIGHTS["novelty"]
        reasons.append("new this week")
    return round(pts, 1), reasons


def match(brief: dict, recipes: dict[str, dict], *,
          seen: set[str] | None = None, limit: int = 5) -> list[dict]:
    """Ranked [{id, version, score, reasons, price_cents}]."""
    ranked = []
    for rid, r in recipes.items():
        if eligible(r, brief):
            continue
        pts, reasons = score(r, brief, seen=seen)
        ranked.append({"id": rid, "version": r.get("version", 1),
                       "score": pts, "reasons": reasons,
                        # fallback = card truth (£2.99): recipes without a price
                        # are cards; priced products must declare price_cents.
                        "price_cents": (r.get("product") or {}).get("price_cents", 299)})
    ranked.sort(key=lambda m: (-m["score"], m["id"]))
    return ranked[:limit]
