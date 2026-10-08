"""Recipe registry: published, immutable, versioned product recipes.

Recipes live as JSON under recipes/. Only status=published serves the
storefront and MCP. v1 is never altered — improvements ship as v2.
"""
from __future__ import annotations

import json
from pathlib import Path

from .schemas import validate_recipe

ROOT = Path(__file__).resolve().parents[2] / "recipes"


def load_all(root: Path | None = None) -> dict[str, dict]:
    """id -> latest recipe. Invalid files are skipped, never served."""
    out: dict[str, dict] = {}
    base = root or ROOT
    if not base.is_dir():
        return out
    for f in sorted(base.glob("*.json")):
        try:
            r = json.loads(f.read_text())
        except (OSError, ValueError):
            continue
        if not isinstance(r, dict) or not r.get("id"):
            continue
        if validate_recipe(r):
            continue
        cur = out.get(r["id"])
        if cur is None or int(r.get("version", 1)) > int(cur.get("version", 1)):
            r["_file"] = str(f)
            out[r["id"]] = r
    return out


def published(root: Path | None = None) -> dict[str, dict]:
    """The canonical shelf: what recommend/make may serve."""
    return {rid: r for rid, r in load_all(root).items()
            if r.get("status") == "published"}


def get(recipe_id: str, root: Path | None = None) -> dict:
    return published(root).get(recipe_id, {})
