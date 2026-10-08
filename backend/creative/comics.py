"""Autonomous 4-panel pipeline — product v1.

Input: one JokeBlock. Output: 5 premise candidates, each with a theory
combo, each renderable as title + one-line premise + 4-panel script.

Stages (each independently testable, each with an offline path):
  candidates()  operators over block -> premise angles (deterministic)
  select_five() greedy max-coverage of theory combos (deterministic)
  rank()        jev calibrated scores when OPENROUTER_API_KEY exists,
                transparent heuristic fallback otherwise
  validate_script()  schema gate before anything renders
  to_video_inputs()  script + rendered plates -> meme_video.slideshow args
  to_card()     script -> single-image artwork via composite2d (caption over
                panel 4, the punch)

Plates come later (fal, needs key). Words never live in plates.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from backend.creative import blocks as _blocks
from backend.creative import operators as _ops

COMICS_DIR = _blocks.ROOT / "comics"

REQUIRED_SCRIPT = ("id", "title", "premise", "theory_combo", "panels", "caption")


def load_comics() -> dict[str, dict]:
    out: dict[str, dict] = {}
    if not COMICS_DIR.is_dir():
        return out
    for f in sorted(COMICS_DIR.glob("*.json")):
        try:
            d = json.loads(f.read_text())
        except (OSError, ValueError):
            continue
        for p in d.get("premises", []):
            if p.get("id"):
                out[p["id"]] = {**p, "_pack": f.stem,
                                "_block": d.get("joke_block", "")}
    return out


def validate_script(s: dict) -> list[str]:
    gaps = []
    for k in REQUIRED_SCRIPT:
        if k not in s:
            gaps.append(f"missing {k}")
    panels = s.get("panels") or []
    if len(panels) != 4:
        gaps.append("a 4-panel script needs exactly 4 panels")
    for i, p in enumerate(panels):
        if not isinstance(p, dict) or not p.get("scene"):
            gaps.append(f"panel {i} needs a scene")
    theories = _blocks.load_theories()
    combo: list[str] = []
    for t in s.get("theory_combo") or []:
        # shorthand the founder uses: incongruity+resolution as one move
        if t == "incongruity_resolution":
            combo.extend(["incongruity", "resolution"])
        else:
            combo.append(t)
    for t in combo:
        if t not in theories:
            gaps.append(f"unknown theory {t}")
    return gaps


def candidates(block: dict) -> list[dict]:
    """Operator angles for one block (deterministic, offline)."""
    return _ops.run_all(block)


def select_five(cands: list[dict]) -> list[dict]:
    """Greedy max-coverage: each pick maximizes unseen theory combos."""
    picked: list[dict] = []
    seen: set = set()
    pool = list(cands)
    while pool and len(picked) < 5:
        best = max(pool, key=lambda c: (c["operator"] not in seen, len(c.get("seeds") or ())))
        picked.append(best)
        seen.add(best["operator"])
        pool.remove(best)
    return picked


def heuristic_score(c: dict) -> float:
    """Transparent offline fallback: specificity + quotability + shape."""
    angle = c.get("angle", "")
    pts = 0.0
    pts += min(3.0, len(re.findall(r"\d+|[A-Z][a-z]+(?:\s[A-Z][a-z]+)+", angle)) * 0.5)
    pts += 1.0 if '"' in angle or '"' in angle or "'" in angle else 0.0
    pts += 1.0 if 20 <= len(angle) <= 220 else 0.0
    pts += 0.5 if (c.get("seeds") or []) else 0.0
    return round(pts, 2)


def rank(cands: list[dict]) -> list[dict]:
    """Calibrated jev scores when possible, heuristic fallback otherwise.
    Never raises: the pipeline must run fully offline."""
    scored = [{**c, "score": heuristic_score(c), "scored_by": "heuristic"}
              for c in cands]
    try:
        from backend import jev as _jev
        answers = _jev.ask(
            {"candidates": [{"operator": c["operator"], "angle": c["angle"]}
                            for c in cands]},
            {"ranking": {"type": "choice",
                         "prompt": "Rank these premise angles by funniness "
                                   "and novelty; return best-first ids.",
                         "options": [c["operator"] for c in cands]},
             "scores": {"type": "score",
                        "prompt": "Score each premise angle 0-100 for "
                                  "funniness, novelty and clarity."}})
        order = answers.get("ranking") or []
        pos = {op: i for i, op in enumerate(order)}
        for s in scored:
            if s["operator"] in pos:
                s["score"] = round(100 - pos[s["operator"]], 2)
                s["scored_by"] = "jev"
    except Exception:
        pass
    return sorted(scored, key=lambda s: -s["score"])


def to_video_inputs(script: dict, panels_dir: Path | str) -> tuple[list[str], list[str]]:
    """Script + directory of 4 rendered plates -> slideshow args.
    Captions come from panel dialogue (last line lands hardest)."""
    d = Path(panels_dir)
    imgs = [str(d / f"panel_{i}.png") for i in range(4)]
    caps = []
    for p in script.get("panels", []):
        lines = p.get("lines") or []
        caps.append(lines[-1] if lines else p.get("scene", ""))
    caps[-1] = script.get("caption", caps[-1])
    return imgs, caps


def duel_pair(scripts: list[dict] | None = None) -> tuple[dict, dict]:
    """Two distinct scripts for a duel. Adjacent in ranked order = closest
    contest (active learning); falls back to random distinct pair."""
    import random
    pool = scripts if scripts is not None else list(load_comics().values())
    if len(pool) < 2:
        raise ValueError("need at least two comics to duel")
    i = random.randrange(len(pool))
    j = random.randrange(len(pool) - 1)
    j += j >= i
    return pool[i], pool[j]


def to_card(script: dict) -> dict:
    """One strip -> single-image artwork spec: panel 4 (the punch) +
    deterministic caption. Rendered downstream by composite2d."""
    panels = script.get("panels", [])
    punch = panels[-1] if panels else {}
    return {"headline": script.get("title", ""),
            "subheadline": script.get("caption", ""),
            "scene": punch.get("scene", ""),
            "style_id": "original",
            "template_id": script.get("id", "")}
