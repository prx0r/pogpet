"""Theory operators — search functions over JokeBlocks.

Each operator takes a block and returns premise candidates: one comic
interpretation per hit. Operators are deliberately dumb template functions,
not LLM personas: the diversity comes from the intellectual operation, not
the voice. An LLM (or human) then executes the candidate into a premise.

Premise generation becomes search: run every operator over every promising
block, rank candidates, execute the best.
"""
from __future__ import annotations


def _tensions(block: dict) -> list[str]:
    return [str(t) for t in block.get("tensions", [])]


def _chars(block: dict) -> list[str]:
    return [str(c) for c in block.get("characters", [])]


def INCONGRUITY(block: dict) -> list[dict]:
    ten = _tensions(block)
    return [{"operator": "incongruity",
             "angle": "What expectation does this violate: "
                      + ("; ".join(ten) if ten else "the obvious reading") + "?",
             "seeds": ten}]


def SCRIPT_OPPOSITION(block: dict) -> list[dict]:
    out = []
    for t in _tensions(block):
        if "/" in t:
            a, b = [s.strip() for s in t.split("/", 1)]
            out.append({"operator": "script_opposition",
                        "angle": f"World where {a} vs world where {b}; stage the collision.",
                        "seeds": [a, b]})
    return out or [{"operator": "script_opposition",
                    "angle": "Find the two opposed world models in this block.",
                    "seeds": []}]


def IDENTITY(block: dict) -> list[dict]:
    chars = _chars(block) or ["central figure"]
    return [{"operator": "identity_contradiction",
             "angle": "Whose identity conflicts with their role: "
                      + ", ".join(chars) + "?",
             "seeds": chars}]


def STATUS(block: dict) -> list[dict]:
    return [{"operator": "status_reversal",
             "angle": "Who thinks they're in control here? Invert it.",
             "seeds": _chars(block)}]


def RIGIDITY(block: dict) -> list[dict]:
    return [{"operator": "rigidity",
             "angle": "Who keeps applying a rule after reality makes it absurd? Follow them one step further.",
             "seeds": []}]


def BISOCIATION(block: dict) -> list[dict]:
    analogues = ((block.get("culture") or {}).get("analogues") or [])
    if not analogues:
        return [{"operator": "bisociation",
                 "angle": "What unrelated frame shares this structure?",
                 "seeds": []}]
    return [{"operator": "bisociation",
             "angle": f"What unrelated frame shares this structure: {a}?",
             "seeds": [a]} for a in analogues]


def BENIGN_VIOLATION(block: dict) -> list[dict]:
    return [{"operator": "benign_violation",
             "angle": "What is uncomfortable here, and what distance (time, place, fiction, cuteness) makes it playable?",
             "seeds": []}]


def LITERALISE(block: dict) -> list[dict]:
    return [{"operator": "literalise",
             "angle": f"Treat the rhetoric as physically true: {block.get('comic_claim', '')}",
             "seeds": []}]


def ESCALATE(block: dict) -> list[dict]:
    return [{"operator": "escalation",
             "angle": "If this pattern continues, what are steps 2, 3 and 10?",
             "seeds": ["step 2", "step 3", "step 10"]}]


def SELF_AWARENESS(block: dict) -> list[dict]:
    chars = _chars(block) or ["they"]
    return [{"operator": "self_awareness",
             "angle": "What changes if the character knows exactly how absurd "
                      "this is: " + ", ".join(chars) + "?",
             "seeds": chars}]


def AUDIENCE_SUPERIORITY(block: dict) -> list[dict]:
    return [{"operator": "audience_alliance",
             "angle": "What can the audience know that the character doesn't? Stage the dramatic irony with no dialogue.",
             "seeds": []}]


def ROLE_REVERSAL(block: dict) -> list[dict]:
    return [{"operator": "role_reversal",
             "angle": "Swap tool/user, expert/novice, institution/customer. Who begs whom now?",
             "seeds": []}]


OPERATORS = (INCONGRUITY, SCRIPT_OPPOSITION, IDENTITY, STATUS, RIGIDITY,
             BISOCIATION, BENIGN_VIOLATION, LITERALISE, ESCALATE,
             SELF_AWARENESS, AUDIENCE_SUPERIORITY, ROLE_REVERSAL)


def run_all(block: dict) -> list[dict]:
    """Every operator over one block -> premise candidate list."""
    out = []
    for op in OPERATORS:
        try:
            out.extend(op(block))
        except Exception:
            continue
    return out


def compose(block: dict, theory_ids: list[str]) -> dict:
    """Apply a theory combo to a block -> premise draft. Theories are
    operations; a combo is a pipeline: each operator contributes its angle,
    and the draft statement scaffolds them into one comic model."""
    by_op = {}
    for c in run_all(block):
        by_op.setdefault(c["operator"], []).append(c)
    alias = {"incongruity_resolution": ["incongruity", "resolution"],
             "literalisation": ["literalise"]}
    ops: list[str] = []
    for t in theory_ids:
        ops.extend(alias.get(t, [t]))
    angles = []
    for op in ops:
        for c in by_op.get(op, []):
            angles.append(f"[{op}] {c['angle']}")
    claim = block.get("comic_claim", "")
    return {"block": block.get("id", ""), "operators": ops,
            "statement": claim or "undeclared comic model",
            "angles": angles,
            "coverage": round(len([o for o in ops if o in by_op]) / max(len(ops), 1), 3)}
