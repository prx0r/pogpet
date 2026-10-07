"""Creative brief builder (cardgen.md §6).

One temporary structured object per request: occasion + recipient (from the
subject graph, never a mesh) + available assets + ask. Thrown at the
matcher, never directly at a renderer.
"""
from __future__ import annotations


def build(*, occasion: str = "general", occasion_date: str = "",
          subject: dict | None = None, profile: dict | None = None,
          asset_counts: dict | None = None, tone: str = "funny",
          budget_cents: int = 0) -> dict:
    sub = subject or {}
    prof = (profile or {}).get("profile", profile or {})
    return {
        "occasion": {"id": occasion or "general", "date": occasion_date or ""},
        "recipient": {
            "subject_id": sub.get("id", ""),
            "name": sub.get("name", "") or prof.get("name", ""),
            "relationship": prof.get("relationship", ""),
            "interests": prof.get("interests", []),
            "humour": prof.get("humour", {}),
            "memories": prof.get("memories", [])[:5],
            "likes": prof.get("likes", []),
            "dislikes": prof.get("dislikes", []),
        },
        "available_assets": asset_counts or {},
        "request": {"tone": tone, "budget_cents": budget_cents},
    }
