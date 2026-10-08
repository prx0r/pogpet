"""Pogcast — two characters talking to each other.

Format: participants + block + turns. Each turn takes the speaker's next
preferred-theory angle on the block, voiced in their tells, with callbacks
to their memories where they fit. Scaffold output (structure + beats); an
LLM or human executes the lines. Judged like everything else.
"""
from __future__ import annotations

from backend.creative import operators as _ops


def cast(char_a: dict, char_b: dict, block: dict, turns: int = 8) -> dict:
    """Alternate A/B for N turns over one block."""
    ops = _ops.OPERATORS
    speakers = [char_a, char_b]
    beats = []
    for i in range(max(2, turns)):
        ch = speakers[i % 2]
        op = ops[i % len(ops)]
        try:
            cands = op(block)
        except Exception:
            continue
        angle = cands[0]["angle"] if cands else block.get("comic_claim", "")
        tells = (ch.get("voice") or {}).get("tells", [])
        mems = ch.get("memories", []) or []
        beats.append({
            "n": i + 1,
            "speaker": ch.get("id", "?"),
            "operator": cands[0]["operator"] if cands else "free",
            "beat": angle,
            "voice": tells[:2],
            "callback": mems[i % len(mems)] if mems else "",
        })
    return {"title": f"{char_a.get('name', 'A')} vs {char_b.get('name', 'B')}: "
                     f"{block.get('id', 'untitled')}",
            "participants": [char_a.get("id"), char_b.get("id")],
            "block": block.get("id", ""),
            "turns": beats}
