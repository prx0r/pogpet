"""Regulars — empirically discovered comedic identities.

A regular is NOT a character we decided to promote. It is an identity
repeatedly demonstrated to generate novel comedy:

    fertility × coherence × self-awareness × novelty × response × callbacks

V1 scores what the repo already knows: fertility (premises + derivations
linked to the character across blocks and packs), coherence (character
appears with identity-contradiction material), response (ledger engagement
attributed through block_id -> block characters). Novelty, self-awareness
and callback density need performance history; they arrive as null with a
documented path, not as faked numbers.
"""
from __future__ import annotations


def character_links(blocks: dict, premise_index: dict, comics: dict) -> dict:
    """character -> {blocks, premises, derivations, comics} (id lists)."""
    links: dict[str, dict] = {}

    def hit(name: str, kind: str, _id: str):
        d = links.setdefault(name, {"blocks": [], "premises": [],
                                    "derivations": [], "comics": []})
        if _id not in d[kind]:
            d[kind].append(_id)

    for bid, b in blocks.items():
        for c in b.get("characters") or []:
            hit(c, "blocks", bid)
        for dv in b.get("derivations") or []:
            for c in b.get("characters") or []:
                hit(c, "derivations", f"{bid}:{dv.get('id')}")
    for pid, p in premise_index.items():
        for c in _chars_of(p):
            hit(c, "premises", pid)
    for cid, s in comics.items():
        for c in _chars_of(s):
            hit(c, "comics", cid)
    return links


def _chars_of(p: dict) -> list[str]:
    chars = list(p.get("characters") or [])
    text = ((p.get("statement") or "") + " " + (p.get("text") or "")
            + " " + (p.get("premise") or "")).lower()
    for name in ("claude", "chatgpt", "grok"):
        if name in text and name not in chars:
            chars.append(name)
    return chars


def score_characters(blocks: dict, premise_index: dict, comics: dict,
                     engagement_by_block: dict | None = None) -> dict:
    """character -> {fertility, coherence, response, detail}. Nulls where
    the repo has no signal yet (novelty, self_awareness, callbacks)."""
    links = character_links(blocks, premise_index, comics)
    eng = engagement_by_block or {}
    out = {}
    for name, d in links.items():
        fertility = len(d["premises"]) + len(d["derivations"]) + len(d["comics"])
        coherence = sum(1 for bid in d["blocks"]
                        if any(t.get("id") == "identity_contradiction"
                               for t in blocks[bid].get("theories", [])))
        response = round(sum(eng.get(bid, {}).get("engagement", 0)
                             for bid in d["blocks"]), 1)
        out[name] = {"fertility": fertility, "coherence": coherence,
                     "response": response, "novelty": None,
                     "self_awareness": None, "callbacks": None,
                     "detail": d}
    return out


def regular_candidates(scores: dict, min_fertility: int = 3) -> list[str]:
    """Ranked by fertility then response. Promotion threshold is a human
    decision; this list is the audition shortlist."""
    return sorted(scores, key=lambda n: (-(scores[n]["fertility"] >= min_fertility),
                                         -scores[n]["fertility"],
                                         -scores[n]["response"]))
