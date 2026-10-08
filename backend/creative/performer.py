"""Semi-autonomous performers — characters that work sets on their own.

A character graph is JokeBlock-compatible: identity, humour (ruling
obsession, after Jonson's humours and Moliere's monomaniacs), mask
(commedia role), preferred theories, voice tells, callbacks/memory,
block affinities, status. Given any block, the performer produces the
character's angle automatically; a trained-classifier gate (judge scores
today, LoRA later) decides what ships. Characters work constantly; only
passing sets reach humans.
"""
from __future__ import annotations

import json
from pathlib import Path

from backend.creative import blocks as _blocks
from backend.creative import judge as _judge
from backend.creative import operators as _ops

ROOT = _blocks.ROOT / "characters"

REQUIRED_CHARACTER = ("id", "name", "archetype", "humour", "mask",
                      "traits", "preferred_theories", "voice", "status")


def _read(p: Path):
    try:
        return json.loads(p.read_text())
    except (OSError, ValueError):
        return None


def load_characters() -> dict[str, dict]:
    out: dict[str, dict] = {}
    if not ROOT.is_dir():
        return out
    for f in sorted(ROOT.glob("*.json")):
        c = _read(f)
        if isinstance(c, dict) and c.get("id"):
            out[c["id"]] = c
    return out


def validate_character(c: dict) -> list[str]:
    gaps = [f"missing {k}" for k in REQUIRED_CHARACTER if k not in c]
    bank = {t["id"] for t in
            (_blocks._read(_blocks.THEORIES_PATH) or {}).get("theories", [])}
    for t in c.get("preferred_theories") or []:
        if t not in bank:
            gaps.append(f"unknown preferred theory {t}")
    if c.get("status") not in ("candidate", "returning", "regular"):
        gaps.append("status must be candidate/returning/regular")
    return gaps


def angle(character: dict, block: dict) -> dict:
    """The character's automatic angle on a block: run only the operators
    matching their preferred theories, voiced in their tells."""
    ops = [o for o in character.get("preferred_theories", [])]
    cands = []
    for op in _ops.OPERATORS:
        probe = {"operator": "", "angle": ""}
        try:
            got = op(block)
        except Exception:
            continue
        for c in got:
            if c["operator"] in ops or not ops:
                cands.append(c)
    voice = (character.get("voice") or {}).get("tells", [])
    claim = block.get("comic_claim", "")
    name = character.get("name", "")
    angles = []
    for c in cands:
        text = c["angle"].replace("central figure", name)
        if "they?" in text:
            text = text.replace("they?", f"{name}?")
        angles.append(text)
    return {"character": character.get("id", ""),
            "block": block.get("id", ""),
            "angles": angles,
            "voice_notes": voice,
            "draft": f"{name} on {claim}: "
                     f"{' / '.join(angles[:2])[:220]}"}


def work_sets(character: dict, blocks: dict, limit: int = 5) -> list[dict]:
    """One character works every block in affinity order, then the rest."""
    aff = character.get("blocks_affinity", [])
    ordered = sorted(blocks.values(),
                     key=lambda b: (b["id"] not in aff, b["id"]))
    out = []
    for b in ordered[:limit]:
        a = angle(character, b)
        if a["angles"]:
            out.append(a)
    return out


def gate(candidates: list[dict], min_score: float = 1.5) -> list[dict]:
    """Trained-classifier gate, v0: judge tournament + score floor.
    Swap the heuristic for the LoRA ranker when it exists; the interface
    (candidates in, passing sets out) stays identical."""
    if not candidates:
        return []
    flat = [{"premise": c.get("draft", ""), **c} for c in candidates]
    table = _judge.tournament(flat)
    passing = []
    for t in table:
        dims = _judge.heuristic_dimensions(t)
        if t.get("tournament_wins", 0) >= 1 and _judge._mean(dims) >= min_score:
            passing.append(t)
    return passing


def _keywords(*parts: str) -> set[str]:
    import re
    words = set()
    for p in parts:
        words.update(re.findall(r"[a-z]{4,}", (p or "").lower()))
    return words


def relevance(character: dict, block: dict) -> float:
    """Graph distance 0..1: would this character care? Block tags, tensions
    and claims vs the character's wants, fears, traits and notices. Most
    characters should ignore most news — that selectiveness is the point."""
    who = _keywords(
        *((character.get("dramatic_core") or {}).get("want", ""),
          (character.get("dramatic_core") or {}).get("fear", ""),
          *character.get("traits", []),
          *((character.get("perception") or {}).get("notices_first", [])),
          *((character.get("perception") or {}).get("watched", []))))
    what = _keywords(
        *block.get("tags", []),
        *[t for t in block.get("tensions", [])],
        block.get("comic_claim", ""),
        *[f.get("claim", "") if isinstance(f, dict) else str(f)
          for f in block.get("facts", [])])
    if not who or not what:
        return 0.0
    return round(len(who & what) / len(who | what) * 4, 3)


def view(character: dict, block: dict) -> dict:
    """CharacterBlockView: ephemeral working memory of this mind seeing
    this world. Salience weights facts by overlap with what the character
    wants, fears and notices first."""
    dc = character.get("dramatic_core", {})
    pc = character.get("perception", {})
    interests = _keywords(dc.get("want", ""), dc.get("fear", ""),
                          *pc.get("notices_first", []),
                          *character.get("traits", []),
                          *pc.get("watched", []))
    facts = []
    for f in block.get("facts", []) or []:
        claim = f.get("claim", "") if isinstance(f, dict) else str(f)
        overlap = interests & _keywords(claim)
        facts.append({"claim": claim,
                      "status": f.get("status", "") if isinstance(f, dict) else "",
                      "weight": round(len(overlap) / max(len(interests), 1) * 4, 3),
                      "reason": f"matches {sorted(overlap)[:3]}" if overlap else ""})
    facts.sort(key=lambda f: -f["weight"])
    tensions = block.get("tensions", []) or []
    priors = ((character.get("comedy") or {}).get("operator_priors")
              or {t: 1.0 for t in character.get("preferred_theories", [])})
    top = facts[0]["claim"] if facts else ""
    return {"character_id": character.get("id", ""),
            "block_id": block.get("id", ""),
            "accessible_reality": [f["claim"] for f in facts],
            "salience": [{"fact": f["claim"], "weight": f["weight"],
                          "reason": f["reason"]} for f in facts[:5]],
            "emotional_stakes": [dc.get("fear", ""), dc.get("want", "")],
            "status_stakes": tensions[:2],
            "interpretation": {
                "surface": block.get("comic_claim", ""),
                "character_frame": f"{character.get('name', '')} notices first: {top}"},
            "candidate_operators": sorted(priors, key=lambda k: -priors[k]),
            "premise_candidates": []}


def contrast_pairs(character: dict, block: dict) -> dict:
    """Weak-supervision training pair: generic angle vs character-specific
    angle on the same block. The specific one wins by construction —
    this teaches identity necessity, not funniness."""
    generic = {"premise": block.get("comic_claim", ""),
               "character": "anyone"}
    specific = angle(character, block)
    return {"a": generic,
            "b": {"premise": specific["draft"],
                  "character": character.get("id", "")},
            "winner": "b", "source": "auto_weak",
            "reason": "character-specific beats generic"}
