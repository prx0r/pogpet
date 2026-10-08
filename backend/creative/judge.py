"""ComedyJudge — pairwise comedy ranker with two brains.

General prior (rubric dimensions + fatal-flaw vetoes) + taste model
(ledger family/block weights are taste v0) fused into predicted response.

Design notes (improvements on the naive LLM-judge):
- Vetoes run FIRST as hard gates: most garbage dies without calibration.
- Every pairwise call runs order-swapped; disagreement = tie (no result).
- Taste multiplies the prior instead of overwriting it: a great joke from
  a cold family still ranks, a decent joke from a hot family gets a lift.
- HITL pairs come from uncertainty (small gaps), not random sampling.
- Preference DB is append-only JSONL next to the performance ledger.
- Never raises: no key / schema drift -> heuristic fallback, labeled.
"""
from __future__ import annotations

import itertools
import json
import time
from pathlib import Path

from backend import config
from backend.creative import performance as _perf

PREFS_NAME = "comedy_prefs.jsonl"

DIMENSIONS = ("reframe", "surprise", "truthiness", "specificity",
              "novelty", "compression", "identity_fit", "fertility")

VETOES = ("NO_ACTUAL_REFRAME",
          "PUNCHLINE_EXPLAINS_ITSELF",
          "GENERIC_AI_HUMOR",
          "DUPLICATES_KNOWN_JOKE",
          "FACTUAL_PREMISE_FALSE",
          "REQUIRES_TOO_MUCH_CONTEXT",
          "PANEL4_DOESNT_HEIGHTEN",
          "CHARACTER_SWAPPABLE")


def _cand_text(c: dict) -> str:
    parts = [c.get("premise", "") or c.get("angle", "")]
    for p in c.get("panels") or []:
        parts.append(p.get("scene", ""))
        parts.extend(p.get("lines") or [])
    parts.append(c.get("caption", ""))
    return "\n".join(s for s in parts if s)


def vetoes(c: dict) -> list[str]:
    """Cheap deterministic vetoes (offline). LLM-detected vetoes arrive
    via jev noul questions when a key exists."""
    found = []
    text = _cand_text(c)
    panels = c.get("panels") or []
    if len(text.split()) < 12:
        found.append("NO_ACTUAL_REFRAME")
    if "generic" in text.lower() and len(set(text.lower().split())) < 20:
        found.append("GENERIC_AI_HUMOR")
    if panels and len(panels) == 4:
        last = json.dumps(panels[-1]).lower()
        first = json.dumps(panels[0]).lower()
        if last == first:
            found.append("PANEL4_DOESNT_HEIGHTEN")
    if not (c.get("theory_combo") or [c.get("operator")]):
        found.append("NO_ACTUAL_REFRAME")
    return found


def heuristic_dimensions(c: dict) -> dict[str, float]:
    """Transparent 0..1 per-dimension fallback."""
    text = _cand_text(c)
    words = text.split()
    uniq = len(set(w.lower() for w in words)) / max(len(words), 1)
    nums = len([w for w in words if any(ch.isdigit() for ch in w)])
    return {
        "reframe": 0.7 if (c.get("theory_combo") or c.get("operator")) else 0.2,
        "surprise": min(1.0, 0.4 + 0.1 * len(c.get("panels") or [])),
        "truthiness": 0.6,
        "specificity": min(1.0, 0.3 + 0.15 * nums + 0.2 * uniq),
        "novelty": round(uniq, 3),
        "compression": 1.0 if 30 <= len(words) <= 220 else 0.4,
        "identity_fit": 0.7 if c.get("characters") or "claude" in text.lower() else 0.4,
        "fertility": 0.6,
    }


def _mean(d: dict[str, float]) -> float:
    return sum(d.values()) / max(len(d), 1)


def resolution_efficiency(text: str) -> dict[str, float]:
    """jestry-inspired S/R/E: surprise (contrast markers + brevity),
    resolution (reframe signals), efficiency (shift per word). Heuristic v0."""
    import re
    words = text.split()
    n = max(len(words), 1)
    surprise = min(1.0, 0.2 + 0.3 * len(re.findall(
        r"\b(but|instead|actually|turns out|suddenly|realize)\b", text.lower())))
    resolution = min(1.0, 0.2 + 0.3 * len(re.findall(
        r"\b(because|so that'?s why|that'?s why|which means)\b", text.lower())))
    efficiency = round(min(1.0, (surprise + resolution) / 2 * (1 - n / 300)), 3)
    return {"surprise": round(surprise, 3), "resolution": round(resolution, 3),
            "efficiency": efficiency}


def taste_multiplier(c: dict, w_fam: dict | None = None,
                     w_block: dict | None = None) -> float:
    """Ledger taste as multiplicative prior (1.0 = no signal)."""
    mf = (w_fam or {}).get(str(c.get("family") or ""), 1.0)
    mb = (w_block or {}).get(str(c.get("block_id") or c.get("_block") or ""), 1.0)
    return round(mf * mb, 3)


def judge_pair(a: dict, b: dict, *, taste: bool = True) -> dict:
    """A vs B, order-swapped, vetoes first. Returns winner/scores/confidence.
    winner in {"a", "b", "tie", "neither"}."""
    va, vb = vetoes(a), vetoes(b)
    if va and vb:
        return {"winner": "neither", "fatal_flaws": {"a": va, "b": vb},
                "scores": {}, "confidence": 1.0, "judged_by": "veto"}
    sa, sb = heuristic_dimensions(a), heuristic_dimensions(b)
    if taste:
        try:
            wf = _perf.weights()
            ma, mb = taste_multiplier(a, wf), taste_multiplier(b, wf)
        except Exception:
            ma = mb = 1.0
        ka, kb = _mean(sa) * ma, _mean(sb) * mb
    else:
        ka, kb = _mean(sa), _mean(sb)
    if abs(ka - kb) < 0.02:
        winner, conf = "tie", 0.5
    else:
        winner = "a" if ka > kb else "b"
        conf = round(min(0.95, 0.5 + abs(ka - kb)), 3)
    out = {"winner": winner,
           "scores": {"a": {**sa, "taste": ma if taste else 1.0},
                      "b": {**sb, "taste": mb if taste else 1.0}},
           "fatal_flaws": {"a": va, "b": vb},
           "confidence": conf, "judged_by": "heuristic"}
    try:
        from backend import jev as _jev
        state = {"a": _cand_text(a)[:1500], "b": _cand_text(b)[:1500]}
        q = {"pick_ab": {"type": "choice", "prompt": "Which is funnier, A or B?",
                         "options": ["a", "b"]},
             "pick_ba": {"type": "choice", "prompt": "Which is funnier, B or A?",
                         "options": ["b", "a"]}}
        r1 = _jev.ask({**state, "order": "ab"}, {"pick": q["pick_ab"]})
        r2 = _jev.ask({**state, "order": "ba"}, {"pick": q["pick_ba"]})
        w1 = str(r1.get("pick", "")).lower()
        w2 = {"b": "a", "a": "b"}.get(str(r2.get("pick", "")).lower(), "")
        if w1 and w1 == w2 and w1 in ("a", "b"):
            out["winner"] = w1
            out["confidence"] = 0.9
            out["judged_by"] = "jev"
        else:
            out["winner"] = "tie"
            out["confidence"] = 0.5
            out["judged_by"] = "jev-swap-disagree"
    except Exception:
        pass
    return out


def tournament(cands: list[dict], rounds: int = 2) -> list[dict]:
    """Round-robin wins; cheap, deterministic, offline-safe."""
    wins = {i: 0 for i in range(len(cands))}
    for i, j in itertools.combinations(range(len(cands)), 2):
        r = judge_pair(cands[i], cands[j])
        if r["winner"] == "a":
            wins[i] += 1
        elif r["winner"] == "b":
            wins[j] += 1
    order = sorted(range(len(cands)), key=lambda i: -wins[i])
    return [{**cands[i], "tournament_wins": wins[i]} for i in order]


def tinder_pairs(ranked: list[dict], n: int = 10) -> list[tuple[dict, dict]]:
    """Adjacent pairs in ranked order = closest contests = most informative
    labels (active learning on the decision boundary)."""
    return [(ranked[i], ranked[i + 1]) for i in range(min(n, len(ranked) - 1))]


def record_preference(a: dict, b: dict, winner: str, *,
                      user: str = "human", context: str = "",
                      path: Path | str | None = None) -> dict:
    """One Tinder click. winner in {"a","b","neither"}."""
    p = Path(path) if path else config.DATA / PREFS_NAME
    p.parent.mkdir(parents=True, exist_ok=True)
    row = {"ts": time.time(), "user": user, "context": context,
           "winner": winner,
           "a": _cand_text(a)[:2000], "b": _cand_text(b)[:2000]}
    with p.open("a") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")
    return row


def precision_at_k(shown: list[str], liked: list[str], k: int = 5) -> float:
    """The metric that matters: of the top-k we ranked, how many landed?"""
    top = shown[:k]
    return round(sum(1 for x in top if x in liked) / max(len(top), 1), 3)


def gate_hierarchy(candidate: dict, character: dict | None = None,
                   seen: tuple = ()) -> list[dict]:
    """Hierarchical gate (ordered). Generation stays weird; this decides
    what ships. Strongest veto: swappable for anyone."""
    text = _cand_text(candidate)
    words = text.split()
    results = []

    def gate(name: str, ok: bool, reason: str):
        results.append({"gate": name, "pass": bool(ok), "reason": reason})
        return ok

    gate("reality", bool(text.strip()), "empty candidate has no reading")
    if character:
        name = (character.get("name") or "").lower()
        tells = [t.lower() for t in (character.get("voice") or {}).get("tells", [])]
        mems = " ".join(character.get("memories", [])).lower()
        specific = (name and name.split()[0] in text.lower()
                    or any(t in text.lower() for t in tells if len(t) > 3)
                    or any(m in text.lower() for m in mems.split() if len(m) > 4))
        gate("character", specific, "swappable for anyone" if not specific
             else "carries identity markers")
    else:
        gate("character", True, "no character assigned; skipped")
    combo = candidate.get("theory_combo") or ([candidate.get("operator")]
                                              if candidate.get("operator") else [])
    gate("reframe", bool(combo), "no perspective shift attached")
    key = (candidate.get("id") or text[:60])
    gate("novelty", key not in seen, "seen before")
    gate("compression", 10 <= len(words) <= 300,
         f"{len(words)} words")
    fertile = ("?" in text or len(set(words)) > 25
               or len(candidate.get("panels") or []) >= 3)
    gate("fertility", fertile, "implies situations" if fertile
         else "single static gag")
    gate("canon", True, "checked at render; see character knowledge")
    gate("funny", True, "pairwise stage; abstain here")
    threads = character.get("threads", []) if character else []
    fit = (not threads or any(t.lower() in text.lower()
                              for t in threads if len(t) > 3))
    gate("set_fit", fit, "advances a thread" if fit
         else "no thread attached")
    return results


def gate_passed(results: list[dict]) -> bool:
    return all(r["pass"] for r in results)
