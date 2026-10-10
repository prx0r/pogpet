"""Motion recipes: hook + body + end card, validated before any render.

A motion recipe is versioned data, like transforms and pack recipes. The
Blender rig builder (next: native DoF/focus-pull/motion-blur/shake per
vision/pro-camera-hooks.md) consumes validated recipes only. Renders are
cached by (mesh_hash, recipe_hash); preview 240 px, final 1080.

Gate (agent contract): the hook owns the first second, and the product
is on screen within 0.5 s of the start.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2] / "motion" / "hooks.json"

REQUIRED = ("hook", "body", "end", "mood")


def library() -> dict:
    return json.loads((ROOT).read_text())


def validate_recipe(r: dict) -> list[str]:
    gaps = []
    if not isinstance(r, dict):
        return ["recipe must be an object"]
    for k in REQUIRED:
        if k not in r:
            gaps.append(f"missing {k}")
    if gaps:
        return gaps
    try:
        lib = library()
    except (OSError, ValueError):
        return ["hook library unreadable"]
    hooks = {h["id"]: h for h in lib.get("hooks", [])}
    bodies = {b["id"] for b in lib.get("body", [])}
    ends = {e["id"] for e in lib.get("end", [])}
    hook = hooks.get(r["hook"])
    if hook is None:
        gaps.append(f"unknown hook {r['hook']!r}")
    for b in (r.get("body") or []):
        if b not in bodies:
            gaps.append(f"unknown body piece {b!r}")
    if r.get("end") not in ends:
        gaps.append(f"unknown end card {r['end']!r}")
    if r.get("mood") not in (lib.get("moods") or []):
        gaps.append(f"unknown mood {r.get('mood')!r}")
    if hook is not None:
        if float(hook["duration"][0]) < 1.0:
            gaps.append("hook must hold the first second")
        if float(hook.get("product_enter_s", 9)) > 0.5:
            gaps.append("product must be on screen within 0.5 s")
    if not isinstance(r.get("body"), list) or not r["body"]:
        gaps.append("body must be a non-empty list")
    return gaps


def cache_key(mesh_hash: str, recipe: dict) -> str:
    canon = json.dumps(recipe, sort_keys=True, separators=(",", ":"))
    return hashlib.sha1(f"{mesh_hash}:{canon}".encode()).hexdigest()[:16]


def describe(recipe: dict) -> dict:
    bad = validate_recipe(recipe)
    if bad:
        return {"ok": False, "error": "; ".join(bad)}
    lib = library()
    hook = next(h for h in lib["hooks"] if h["id"] == recipe["hook"])
    return {"ok": True, "recipe": recipe, "hook": hook,
            "works_on": hook.get("works_on", ["mesh"])}
