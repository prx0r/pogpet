"""World operators — comedy as state transformation.

Level 1 of the system: operators manipulate a world-model (relations,
beliefs, status, identities, rules). Level 2 (performance) decides how to
reveal the resulting funny world. Every function is pure: state in, new
state + description out. Tags become functions:

    invert_status(A, B)  -- not tag = status_reversal
"""
from __future__ import annotations

import copy


def blank() -> dict:
    return {"relations": [], "beliefs": {}, "status": {}, "identities": {},
            "rules": [], "frames": {}, "contradictions": [], "beats": [],
            "materialized": [], "revealed": {}, "blind": {}, "log": []}


def _out(state: dict, op: str, description: str) -> dict:
    state["log"].append(op)
    return {"state": state, "operator": op, "description": description}


def status_invert(state: dict, a: str, b: str) -> dict:
    """A controls B -> B effectively controls A."""
    s = copy.deepcopy(state)
    sa, sb = s["status"].get(a, 0), s["status"].get(b, 0)
    s["status"][a], s["status"][b] = sb, sa
    for r in s["relations"]:
        if {r.get("subject"), r.get("object")} == {a, b}:
            r["subject"], r["object"] = r["object"], r["subject"]
    return _out(s, "status_invert", f"{b} now directs {a}")


def double_interpret(state: dict, event: str, frame_a: str, frame_b: str) -> dict:
    """One event, two independent frames; audience suddenly sees both."""
    s = copy.deepcopy(state)
    s["frames"][event] = [frame_a, frame_b]
    return _out(s, "double_interpret", f"{event}: {frame_a} / {frame_b}")


def rigidify(state: dict, rule: str) -> dict:
    """Apply the rule after circumstances made it inappropriate; count grows."""
    s = copy.deepcopy(state)
    n = sum(1 for r in s["rules"] if r.get("rule") == rule) + 1
    s["rules"].append({"rule": rule, "applications": n})
    return _out(s, "rigidify", f"rule applied {n}x despite reality: {rule}")


def split_knowledge(state: dict, audience_knows: str, character: str,
                    character_believes: str) -> dict:
    """Dramatic irony: audience and character hold different models."""
    s = copy.deepcopy(state)
    s["beliefs"].setdefault("audience", []).append(audience_knows)
    s["beliefs"][character] = [character_believes]
    return _out(s, "split_knowledge",
                f"audience knows [{audience_knows}]; {character} acts on [{character_believes}]")


def mistake_identity(state: dict, x: str, mistaken_as: str, cost: int = 1) -> dict:
    """X taken for Y; correcting grows costlier each beat."""
    s = copy.deepcopy(state)
    m = next((m for m in s["beats"] if m.get("kind") == "mistake"), None)
    if m is None:
        m = {"kind": "mistake", "x": x, "as": mistaken_as, "cost": 0}
        s["beats"].append(m)
    m["cost"] += cost
    s["identities"][x] = mistaken_as
    return _out(s, "mistake_identity",
                f"{x} treated as {mistaken_as}; correction cost now {m['cost']}")


def repeat_variation(state: dict, pattern: str, mutation: str) -> dict:
    """Establish, repeat with mutation; final beat breaks expectation."""
    s = copy.deepcopy(state)
    step = sum(1 for b in s["beats"] if b.get("kind") == "repeat") + 1
    s["beats"].append({"kind": "repeat", "step": step,
                       "pattern": pattern, "mutation": mutation})
    return _out(s, "repeat_variation", f"step {step}: {pattern} + {mutation}")


def identity_contradict(state: dict, character: str, identity: str,
                        prop: str) -> dict:
    """I and P cannot comfortably coexist; flag the collision."""
    s = copy.deepcopy(state)
    s["contradictions"].append({"character": character, "identity": identity,
                                "property": prop})
    return _out(s, "identity_contradict", f"{character}: {identity} x {prop}")


def unmask(state: dict, character: str, presented: str, actual: str) -> dict:
    """Presented identity X peels; actual Y becomes undeniable."""
    s = copy.deepcopy(state)
    s["identities"][character] = actual
    s["revealed"][character] = {"was": presented, "is": actual}
    return _out(s, "unmask", f"{character}: {presented} -> {actual}")


def literalize(state: dict, abstraction: str, material: str) -> dict:
    """Make the metaphor materially true."""
    s = copy.deepcopy(state)
    s["materialized"].append({"abstraction": abstraction, "material": material})
    return _out(s, "literalize", f"{abstraction} is now {material}")


def bisociate(state: dict, frame_a: str, frame_b: str, shared: str) -> dict:
    """Two unrelated frames, one shared relational structure."""
    s = copy.deepcopy(state)
    s["frames"][f"{frame_a} x {frame_b}"] = [shared]
    return _out(s, "bisociate", f"{frame_a} x {frame_b} via {shared}")


def expose_self_blindness(state: dict, character: str, trait: str) -> dict:
    """Character has T, cannot see T; audience can."""
    s = copy.deepcopy(state)
    s["blind"].setdefault(character, []).append(trait)
    s["beliefs"].setdefault("audience", []).append(f"{character} is {trait}")
    return _out(s, "expose_self_blindness",
                f"{character} cannot see they are {trait}; audience can")


def character_violation(state: dict, character: str, rule: str) -> dict:
    """Break an established rule once; requires the rule to exist."""
    s = copy.deepcopy(state)
    known = [r.get("rule") for r in s["rules"]]
    if rule not in known:
        return _out(s, "character_violation",
                    f"no rule to break: {rule} was never established")
    s["rules"].append({"rule": rule, "applications": "BROKEN"})
    return _out(s, "character_violation",
                f"{character} breaks {rule} once; information maximal")


OPS = {"status_invert": status_invert, "double_interpret": double_interpret,
       "rigidify": rigidify, "split_knowledge": split_knowledge,
       "mistake_identity": mistake_identity,
       "repeat_variation": repeat_variation,
       "identity_contradict": identity_contradict, "unmask": unmask,
       "literalize": literalize, "bisociate": bisociate,
       "expose_self_blindness": expose_self_blindness,
       "character_violation": character_violation}
