"""Benchmark harness skeleton (devplan-2026-10-07): router picks from data.

Records provider attempts per OddHobb task (the 50 below) with scores for
identity/pose/adherence/hands/photorealism/latency/cost. No spend here —
entries are written when real runs happen elsewhere, and the router reads
the aggregates. A Data Garden for model choice.
"""
from __future__ import annotations

import json
import time
from pathlib import Path

TASKS = [
    "dad:sports-interview", "dad:news-desk", "dad:santa-press",
    "mum:award-ceremony", "pet:investigation-board", "two-people:tv-interview",
]

DIMENSIONS = ["identity", "pose", "adherence", "hands", "photorealism",
              "latency", "cost"]


def log_path(root: Path | None = None) -> Path:
    base = root or Path(__file__).resolve().parents[2] / "data"
    base.mkdir(parents=True, exist_ok=True)
    return base / "benchmark_runs.jsonl"


def record(*, task: str, adapter: str, scores: dict,
           root: Path | None = None) -> dict:
    rec = {"ts": time.time(), "task": task, "adapter": adapter,
           "scores": {d: float(scores.get(d, 0)) for d in DIMENSIONS}}
    with log_path(root).open("a") as f:
        f.write(json.dumps(rec) + "\n")
    return rec


def leaderboard(root: Path | None = None) -> dict[str, dict]:
    agg: dict[str, dict] = {}
    p = log_path(root)
    if not p.exists():
        return agg
    for line in p.read_text().splitlines():
        try:
            r = json.loads(line)
        except ValueError:
            continue
        a = agg.setdefault(r.get("adapter", "?"), {"n": 0, "mean": 0.0})
        s = sum(r.get("scores", {}).values()) / max(1, len(DIMENSIONS))
        a["mean"] = (a["mean"] * a["n"] + s) / (a["n"] + 1)
        a["n"] += 1
    return agg
