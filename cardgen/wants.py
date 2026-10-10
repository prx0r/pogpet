"""Photo wants: one spec for what a template needs from the uploaded photos.

Cards (cardgen templates) and products (config.PRODIGI_PRODUCTS[*].requires)
both declare it, and the same labels answer both (docs/photo-labels.md):
L1 shot type, L2 who, L3 face size and quality, L5 expression and framing.

A role in a template:

    "hero": {
      "shot": ["solo", "face"],        # L1: solo | face | couple | group
      "identity": "hero",              # hero | with_hero | anyone
      "people": [1, 1],                # faces in the photo (lo, hi)
      "expression": ["happy"],         # L5 (photo_labels.EXPRESSIONS, or happy/expressive/funny_face)
      "framing": [],                   # L5: close_up | head_shoulders | waist_up | full_body
      "min_face_px": 120,              # L3: the hero's face height in px
      "refs": 3,                       # extra hero reference photos for likeness
      "optional": false
    }
"""
from __future__ import annotations

SHOTS = ("solo", "face", "couple", "group")
DEFAULT = {"shot": ["solo", "face"], "identity": "hero", "people": [1, 6],
           "expression": [], "framing": [], "min_face_px": 90, "refs": 1,
           "optional": False}


def norm(role: dict) -> dict:
    r = {**DEFAULT, **(role or {})}
    r["people"] = [int(r["people"][0]), int(r["people"][1])]
    return r


def shot_of(n_faces: int, face_frac: float) -> set:
    if n_faces >= 3:
        return {"group"}
    if n_faces == 2:
        return {"couple"}
    if n_faces == 1:
        return {"solo", "face"} if face_frac >= 0.04 else {"solo"}
    return set()


def describe(role: dict) -> str:
    """Plain words for a shortfall ('a happy solo photo of them')."""
    r = norm(role)
    bits = []
    if r["expression"]:
        bits.append(" or ".join(r["expression"]))
    bits.append({"group": "group", "couple": "couple"}.get(r["shot"][0], "solo"))
    if r["framing"]:
        bits.append("(" + " or ".join(f.replace("_", " ") for f in r["framing"]) + ")")
    who = {"hero": "of them", "with_hero": "with them in it", "anyone": ""}[r["identity"]]
    words = " ".join(bits)
    art = "an" if words[:1] in "aeiou" else "a"
    return f"{art} {words} photo {who}".strip()


def to_requires(wants: dict) -> dict:
    """Template wants -> subject_assets.select_for_template `requires`."""
    req = {"groups": 0, "couples": 0, "solos": 0, "faces": 0}
    emo, frm = set(), set()
    for role in wants.values():
        r = norm(role)
        if r["optional"]:
            continue
        key = {"group": "groups", "couple": "couples", "face": "faces"}.get(r["shot"][0], "solos")
        req[key] += 1
        emo |= set(r["expression"])
        frm |= set(r["framing"])
    if emo:
        req["emotions"] = sorted(emo)
    if frm:
        req["framing"] = sorted(frm)
    return req
