"""Demand radar: what people ask for vs what the catalog covers.

JSONL ledger (gitignored data/demand.jsonl). Sources: site search/ramble
logs, MCP playbook topics, owner notes. gaps() matches request topics
against STUDIO_LINES labels/blurbs; unmatched clusters with count >= 3
become product candidates. No fake demand: only logged observations.
"""
from __future__ import annotations

import json
import os
import re
from collections import Counter
from datetime import datetime, timezone

DATA = os.environ.get("FIGG_DATA", "/home/ubuntu/figgsite/data")
LEDGER = os.path.join(DATA, "demand.jsonl")

STOP = set("the a an and or for with what how when want need get got like just really very".split())


def log_request(text: str, source: str = "note") -> dict:
    row = {"at": datetime.now(timezone.utc).isoformat(), "source": source,
           "text": text[:500]}
    os.makedirs(os.path.dirname(LEDGER), exist_ok=True)
    with open(LEDGER, "a") as f:
        f.write(json.dumps(row) + "\n")
    return row


def _topics(text: str) -> list[str]:
    words = re.findall(r"[a-z]{3,}", text.lower())
    return [w for w in words if w not in STOP]


def top(limit: int = 20) -> list[tuple[str, int]]:
    if not os.path.exists(LEDGER):
        return []
    c: Counter = Counter()
    with open(LEDGER) as f:
        for line in f:
            try:
                c.update(_topics(json.loads(line).get("text", "")))
            except Exception:
                continue
    return c.most_common(limit)


def gaps(catalog_words: list[str], min_count: int = 3) -> list[dict]:
    """Request topics the catalog never mentions, ranked by frequency."""
    cat = {w.lower() for w in catalog_words}
    out = []
    for topic, n in top(200):
        if n >= min_count and topic not in cat:
            out.append({"topic": topic, "requests": n,
                        "action": "add product" if n >= 5 else "custom-make"})
    return out
