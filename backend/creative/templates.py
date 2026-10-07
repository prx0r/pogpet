"""Versioned template registry (cardgen.md §3–4).

Templates are data: immutable manifests with taxonomy, requirements, typed
slots and renderer bindings. The manifest says WHAT; layout files (Polotno /
Konva JSON, SVGs, motion, prompts) referenced under files/ say WHERE/HOW and
can be replaced without touching the manifest.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2] / "templates"

REQUIRED_TOP = ("id", "version", "taxonomy", "requirements", "slots", "renderers")
TEXT_SLOT_KEYS = ("max_chars", "default")


def validate_manifest(m: dict) -> list[str]:
    gaps = []
    for k in REQUIRED_TOP:
        if k not in m:
            gaps.append(f"missing {k}")
    if not isinstance(m.get("version"), int):
        gaps.append("version must be int")
    tax = m.get("taxonomy") or {}
    for k in ("occasion", "styles", "topics", "tone"):
        if k in tax and not isinstance(tax[k], list):
            gaps.append(f"taxonomy.{k} must be a list")
    req = m.get("requirements") or {}
    for k in ("subjects", "face_photos_min"):
        if k in req and not isinstance(req[k], int):
            gaps.append(f"requirements.{k} must be int")
    for sid, slot in (m.get("slots") or {}).items():
        if not isinstance(slot, dict) or "type" not in slot:
            gaps.append(f"slot {sid} needs a type")
        elif slot["type"] == "text" and "max_chars" in slot \
                and not isinstance(slot["max_chars"], int):
            gaps.append(f"slot {sid} max_chars must be int")
    return gaps


def load_all(root: Path | None = None) -> dict[str, dict]:
    """id -> latest manifest. Invalid manifests are skipped with _errors."""
    out: dict[str, dict] = {}
    base = root or ROOT
    if not base.is_dir():
        return out
    for manifest in sorted(base.glob("*/*/manifest.json")):
        try:
            m = json.loads(manifest.read_text())
        except (OSError, ValueError):
            continue
        gaps = validate_manifest(m)
        if gaps:
            continue
        cur = out.get(m["id"])
        if cur is None or m["version"] > cur["version"]:
            m["_dir"] = str(manifest.parent)
            out[m["id"]] = m
    return out


def get(template_id: str, root: Path | None = None) -> dict:
    return load_all(root).get(template_id, {})
