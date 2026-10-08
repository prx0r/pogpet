"""Listing fixtures + demo recipes — one source for factory and API.

Fixtures live in gitignored data/fixtures/<name>/photos (real people need
real permission; never commit photos). Recipes bind a product line to a
fixture using only the line's real personalization method.
"""
from __future__ import annotations

from pathlib import Path

from backend import config

FIX = config.DATA / "fixtures"
OUT = config.DATA / "listings"
PROD = config.DATA / "productimg" / "prod"

# line -> demo recipe. method MUST equal the line's personalization.method.
RECIPES = {
    "brick": {"fixture": "demo", "hero": "brick-hero.png",
              "angles": ["brick-hero.png"],
              "story": "Photo -> little person -> 75 mm desk figure",
              "text": "", "method": "face_swap"},
    "brick_keychain": {"fixture": "demo", "hero": "brick_keychain-hero.png",
                       "angles": ["brick_keychain-front.png", "brick_keychain-side.png"],
                       "story": "Photo -> little person -> keychain",
                       "text": "", "method": "face_swap"},
    "ornament": {"fixture": "demo", "hero": "prod-hero.png",
                 "angles": ["prod-hero.png"],
                 "story": "Photo -> Christmas ornament with printed loop",
                 "text": "", "method": "face_swap"},
    "golf_marker": {"fixture": "dad", "hero": "golf_marker-hero.png",
                    "angles": ["golf_marker-front.png", "golf_marker-side.png"],
                    "story": "Dad loves golf -> personalised marker",
                    "text": "DAD", "method": "relief"},
    "book_holder": {"fixture": "mum", "hero": "book_holder-hero.png",
                    "angles": ["book_holder-front.png", "book_holder-side.png"],
                    "story": "Personalised reading gift for Mum",
                    "text": "MUM", "method": "emboss"},
    "xmas_card": {"fixture": "demo", "hero": "card-merry_xmas-5x7.png",
                  "angles": ["card-merry_xmas-5x7.png"],
                  "story": "Your photo, our joke, posted to their door",
                  "text": "", "method": "print"},
}


def fixture_photos(name: str) -> list[Path]:
    d = FIX / name / "photos"
    if not d.is_dir():
        return []
    return sorted(p for p in d.iterdir()
                  if p.suffix.lower() in (".jpg", ".jpeg", ".png"))


def recipe_for(line: str) -> dict:
    if line not in RECIPES:
        raise KeyError(line)
    return RECIPES[line]


def rank_for(interests: list[str], notes: str = "") -> list[dict]:
    """Rank product lines for someone we know. Prints the reasoning so an
    agent can explain the pick, not just take it."""
    notes = (notes or "").lower()
    ranked = []
    for lid, spec in config.STUDIO_LINES.items():
        hay = " ".join(str(spec.get(k) or "") for k in
                       ("label", "blurb", "theme", "occasion", "fits")).lower()
        hits = sorted({w for w in interests if w and w in hay})
        note_hits = sorted({w for w in notes.split() if len(w) > 3 and w in hay})
        score = 2 * len(hits) + len(note_hits) + (1 if spec.get("status") == "live" else 0)
        reasons = [f"matches interest: {w}" for w in hits]
        reasons += [f"note mentions: {w}" for w in note_hits]
        if spec.get("status") == "live":
            reasons.append("orderable now")
        ranked.append({"line": lid, "label": spec.get("label", lid),
                       "score": score, "reasons": reasons or ["general gift line"],
                       "price_cents": spec.get("price_cents", 0),
                       "status": spec.get("status")})
    ranked.sort(key=lambda r: (-r["score"], r["line"]))
    return ranked
