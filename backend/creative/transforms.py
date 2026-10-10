"""Transformation registry: Higgsfield-preset-style reusable transforms.

A transform is versioned, immutable once published, and says WHAT to make —
never provider names, never model endpoints. Recipes refer to transform_id;
the capability router decides which adapter satisfies the capability today.

transforms/*.json fields: id, version, status (draft/published/retired),
capability, references {subject, min_images, preferred_images},
instruction {template}, preserve [], output {}, qc {}, prompt_id?,
products [].
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2] / "transforms"

REQUIRED = ("id", "version", "status", "capability", "references",
            "instruction", "preserve", "output", "qc")
VALID_STATUSES = ("draft", "published", "retired")


def validate_transform(t: dict) -> list[str]:
    gaps = []
    if not isinstance(t, dict):
        return ["transform must be an object"]
    for k in REQUIRED:
        if k not in t:
            gaps.append(f"missing {k}")
    if not isinstance(t.get("version"), int):
        gaps.append("version must be int")
    if t.get("status") not in VALID_STATUSES:
        gaps.append(f"status must be one of {VALID_STATUSES}")
    refs = t.get("references") or {}
    if not isinstance(refs.get("min_images"), int):
        gaps.append("references.min_images must be int")
    if not isinstance((t.get("instruction") or {}).get("template"), str):
        gaps.append("instruction.template must be a string")
    return gaps


def load_all(root: Path | None = None) -> dict[str, dict]:
    out: dict[str, dict] = {}
    base = root or ROOT
    if not base.is_dir():
        return out
    for f in sorted(base.glob("*.json")):
        try:
            t = json.loads(f.read_text())
        except (OSError, ValueError):
            continue
        if not isinstance(t, dict) or not t.get("id"):
            continue
        if validate_transform(t):
            continue
        cur = out.get(t["id"])
        if cur is None or int(t.get("version", 1)) > int(cur.get("version", 1)):
            t["_file"] = str(f)
            out[t["id"]] = t
    return out


def published(root: Path | None = None) -> dict[str, dict]:
    return {tid: t for tid, t in load_all(root).items()
            if t.get("status") == "published"}


def get(transform_id: str, root: Path | None = None) -> dict:
    return published(root).get(transform_id, {})
