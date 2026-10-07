"""No-slop filter, comedy-calibrated (prx0r/noslop as reference).

Upstream engine is imported, never vendored (no license on file):
backend/resources/repos/noslop/miner/src/{detector,knowledge}.py.
Comedy calibration: rule-of-three lists are a FEATURE in jokes (3LIST
never fails a set); essay tics (NARR/NEG/CLICHE/FLAT) fail. Short-form
(zero-tolerance) regime for sets, captions and cards.
"""
from __future__ import annotations

import importlib.util
import os
from pathlib import Path

NOSLOP_DIR = Path(os.environ.get(
    "NOSLOP_DIR",
    Path(__file__).resolve().parents[2] / "backend" / "resources" / "repos" / "noslop"))

_FAIL_TAGS = ("NARR", "NEG", "CLICHE", "FLAT")
# 3LIST is joke structure (rule of three) — counted, never failed.


def _load(mod: str):
    path = NOSLOP_DIR / "miner" / "src" / f"{mod}.py"
    if not path.exists():
        raise ImportError(f"noslop checkout missing: {path}")
    spec = importlib.util.spec_from_file_location(f"noslop_{mod}", path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def diagnose(text: str) -> dict:
    """Pattern hits per tag + comedy verdict. $0, offline, deterministic."""
    det = _load("detector")
    fns = {"NARR": det.detect_narr, "NEG": det.detect_neg,
           "3LIST": det.detect_three_list, "CLICHE": det.detect_cliche,
           "FLAT": det.detect_flat}
    hits: dict[str, list] = {}
    for tag, fn in fns.items():
        try:
            ms = fn(text)
        except Exception:  # noqa: BLE001 — a probe must never 500 the pipeline
            continue
        hits[tag] = [(getattr(m, "matched_text", ""), getattr(m, "line", 0)) for m in ms]
    fails = {t: v for t, v in hits.items() if t in _FAIL_TAGS and v}
    return {"ok": True, "hits": {t: len(v) for t, v in hits.items()},
            "three_lists": len(hits.get("3LIST", [])),
            "fails": fails, "slop_free": not fails,
            "hint": "rewrite to remove " + ", ".join(sorted(fails)) if fails else "clean"}


def guidance(fails: dict) -> str:
    """One-line repair steer per failing tag (knowledge base when present)."""
    try:
        kb = _load("knowledge")
        glossary = getattr(kb, "PATTERN_KNOWLEDGE", {})
    except Exception:  # noqa: BLE001
        glossary = {}
    lines = []
    for tag in sorted(fails):
        why = ""
        try:
            why = glossary.get(tag, {}).get("why_slop", "")
        except Exception:  # noqa: BLE001
            pass
        lines.append(f"{tag}: {why or 'cut it, say it straight'}".strip())
    return "\n".join(lines)
