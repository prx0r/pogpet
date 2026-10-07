"""Human + agent-facing viral-format catalog.

One source of truth powers storefront browsing and ChatGPT/Muse discovery.
"""
from __future__ import annotations
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2] / "templates"
PATH = ROOT / "catalog.json"

def load() -> dict:
    try:
        return json.loads(PATH.read_text())
    except (OSError, ValueError):
        return {"version": 1, "styles": [], "templates": [], "facets": {}}

def by_id() -> dict[str, dict]:
    return {t["id"]: t for t in load().get("templates", []) if t.get("id")}

def query(*, style: str = "", occasion: str = "", audience: str = "",
          tone: str = "", q: str = "") -> dict:
    cat = load()
    items = list(cat.get("templates") or [])
    ql = q.strip().lower()

    def keep(t: dict) -> bool:
        if style and t.get("style") != style:
            return False
        if occasion and occasion not in (t.get("occasion") or []):
            return False
        if audience and audience not in (t.get("audience") or []):
            return False
        if tone and tone not in (t.get("tone") or []):
            return False
        if ql:
            hay = " ".join([
                str(t.get("label") or ""), str(t.get("premise") or ""),
                str(t.get("example_caption") or ""), str(t.get("style") or ""),
                " ".join(t.get("topics") or []), " ".join(t.get("tone") or []),
                " ".join(t.get("audience") or []), " ".join(t.get("occasion") or [])
            ]).lower()
            if ql not in hay:
                return False
        return True

    items = [t for t in items if keep(t)]
    return {
        "ok": True,
        "version": cat.get("version", 1),
        "thesis": cat.get("thesis", ""),
        "styles": cat.get("styles", []),
        "facets": cat.get("facets", {}),
        "count": len(items),
        "templates": items,
    }
