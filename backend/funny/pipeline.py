"""Funny pipeline: profile → beats → draft → filter → rewrite → judge.

The LLM supplies profile details; WE own structure, filter and verdict.
Draft → noslop diagnose → guided rewrite (max 2 iters) → Ella score → best.
Costs: writer calls only (pennies), everything else $0 deterministic.
"""
from __future__ import annotations

from . import judge, recipes, slop
from . import writer as _writer
from . import persona as _persona
from .writer import WriterError


def build_prompt(plan: dict, attempt: int = 0, guidance: str = "",
                 profile: dict | None = None) -> str:
    f = plan.get("facts", {})
    beats = "\n".join(f"{i + 1}. {b}" for i, b in enumerate(plan["beats"]))
    motif, mechanics = _persona.pick(profile or {})
    shots = _persona.examples(1, _persona.MOTIF_TO_ELLA.get(motif, ""))
    shot = ""
    if shots:
        shot = (f"\nVoice reference ({shots[0]['motif']} mode — study the mechanics, "
                f"not the topic):\n{shots[0]['response'][:900]}")
    base = (f"You are roasting {f.get('name') or 'Dad'} with love, in {motif} mode: "
            f"{mechanics}\n{_persona.RULES}\n"
            f"True details to use (every joke must attach to one): "
            f"{f.get('detail') or ''} {f.get('number') or ''} {f.get('interest') or ''} "
            f"{f.get('memory') or ''} {f.get('quote') or ''}.\n"
            f"Structure:\n{beats}\n{shot}\n"
            f"Return ONLY the set lines, 80-180 words, no preamble.")
    if attempt and guidance:
        base += f"\nRewrite fixing exactly this: {guidance}"
    return base


def run_set(profile: dict, recipe_id: str = "dad_game_winner", *,
            approved: bool = False, model: str = "") -> dict:
    """Full loop. approved=True spends writer pennies (ledgered)."""
    plan = recipes.plan(recipe_id, {
        "name": profile.get("name", "Dad"),
        "detail": (profile.get("memories") or [""])[0],
        "number": "", "interest": (profile.get("interests") or [""])[0],
        "memory": (profile.get("memories") or ["", ""] + [""])[1]
        if len(profile.get("memories") or []) > 1 else "",
        "quote": ""})
    best, attempts = None, []
    guidance = ""
    for attempt in range(3):
        try:
            draft = _writer.write_set(build_prompt(plan, attempt, guidance, profile),
                                      approved=approved, model=model)
        except WriterError as e:
            return {"ok": False, "error": str(e), "attempts": attempts}
        lines = draft["lines"]
        diag = slop.diagnose("\n".join(lines))
        ver = judge.score(lines)
        attempts.append({"lines": lines, "slop": diag["fails"],
                         "stars": ver["stars"], "points": ver["points"]})
        if best is None or (ver["stars"], ver["points"]) > (best["stars"], best["points"]):
            best = {"lines": lines, "stars": ver["stars"], "points": ver["points"],
                    "reasons": ver["reasons"], "model": draft["model"]}
        if diag["slop_free"] and ver["stars"] >= 4:
            break
        guidance = slop.guidance(diag["fails"]) or "tighter, more specific, shorter closer"
    best["attempts"] = attempts
    best["recipe"] = plan["recipe"]
    return {"ok": True, **best}
