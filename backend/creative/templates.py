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


def _presentation(item: dict) -> dict:
    return {
        "label": item.get("label") or str(item.get("id") or "").replace("_", " ").title(),
        "style": item.get("style") or "generic",
        "audience": item.get("audience") or [],
        "premise": item.get("premise") or "",
        "example_caption": item.get("example_caption") or "",
    }


def load_all(root: Path | None = None) -> dict[str, dict]:
    """id -> latest manifest. Hand-authored manifests win; catalog ideas
    synthesize executable manifests (or enrich presentation only)."""
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
    try:
        cat = json.loads((base / "catalog.json").read_text())
    except (OSError, ValueError):
        cat = {}
    for item in cat.get("templates", []):
        tid = str(item.get("id") or "")
        if not tid:
            continue
        if tid in out:
            out[tid]["presentation"] = _presentation(item)
            continue
        style = str(item.get("style") or "generic")
        req = item.get("requirements") or {}
        slots = item.get("slots") or {
            "star": {"type": "subject", "required": True},
            "headline": {"type": "text", "max_chars": 42},
            "caption": {"type": "text", "max_chars": 90},
        }
        m = {
            "id": tid,
            "version": int(item.get("version") or 1),
            "taxonomy": {
                "occasion": item.get("occasion") or ["general"],
                "styles": [style],
                "topics": item.get("topics") or [],
                "tone": item.get("tone") or ["funny"],
            },
            "requirements": {
                "subjects": int(req.get("subjects", 1)),
                "face_photos_min": int(req.get("face_photos_min", 0)),
                "mesh": bool(req.get("mesh", False)),
                "voice": bool(req.get("voice", False)),
            },
            "slots": slots,
            "renderers": {"preview": "composite2d", "hero": "identity_image_v1",
                          "print": "composite2d", "video": "talking_scene_v1"},
            "format": style,
            "premise": item.get("premise") or "",
            "caption_pattern": "{headline} — {caption}",
            "tone": item.get("tone") or ["funny"],
            "rules": {},
            "presentation": _presentation(item),
            "layout": {"photo": [0.08, 0.05, 0.92, 0.55],
                       "headline": [0.08, 0.60, 0.92, 0.70],
                       "caption": [0.08, 0.71, 0.92, 0.82],
                       "safe_inset_mm": 5},
        }
        if not validate_manifest(m):
            m["_dir"] = "catalog"
            out[tid] = m
    return out


def get(template_id: str, root: Path | None = None) -> dict:
    return load_all(root).get(template_id, {})
