"""Meme performance ledger — the timeline as the loss function.

Every strip we post (X, TikTok, Instagram, YouTube) carries its premise_id.
What comes back (views, likes, shares, completion, profile taps) lands here
in an append-only JSONL ledger under gitignored data/. Family scores derived
from the ledger reweight what the engine surfaces next: catalog featured
ordering today, matcher scoring next.

Cost model: posting everywhere costs nothing extra (one strip, N wrappers),
so every platform is a tester, not just X.
"""
from __future__ import annotations

import json
import time
from pathlib import Path

from backend import config

PLATFORMS = ("x", "tiktok", "instagram", "youtube")
POST_FORMATS = ("single_panel", "slideshow", "short_video")

LEDGER_NAME = "meme_performance.jsonl"
WEIGHTS_NAME = "meme_weights.json"


def ledger_path(path: Path | str | None = None) -> Path:
    return Path(path) if path else config.DATA / LEDGER_NAME


def _append(row: dict, path: Path | str | None = None) -> dict:
    p = ledger_path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    row = {"ts": time.time(), **row}
    with p.open("a") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")
    return row


def record_post(*, premise_id: str, family: str, platform: str,
                post_ref: str, format: str = "single_panel",
                block_id: str = "",
                path: Path | str | None = None) -> dict:
    """Log an outgoing post. post_ref is the platform's native ID or URL."""
    if platform not in PLATFORMS:
        raise ValueError(f"unknown platform {platform!r}")
    if format not in POST_FORMATS:
        raise ValueError(f"unknown format {format!r}")
    return _append({"type": "post", "premise_id": premise_id, "family": family,
                    "platform": platform, "post_ref": post_ref, "format": format,
                    "block_id": block_id},
                   path)


def record_metrics(*, post_ref: str, views: int = 0, likes: int = 0,
                   shares: int = 0, completion: float = 0.0,
                   profile_taps: int = 0,
                   path: Path | str | None = None) -> dict:
    """Log observed metrics for a post. completion is 0..1 (video watch-through)."""
    return _append({"type": "metrics", "post_ref": post_ref, "views": int(views),
                    "likes": int(likes), "shares": int(shares),
                    "completion": float(completion),
                    "profile_taps": int(profile_taps)}, path)


def _rows(path: Path | str | None = None, days: int = 30) -> list[dict]:
    p = ledger_path(path)
    if not p.is_file():
        return []
    cutoff = time.time() - days * 86400
    out = []
    for line in p.read_text().splitlines():
        try:
            r = json.loads(line)
        except ValueError:
            continue
        if r.get("ts", 0) >= cutoff:
            out.append(r)
    return out


def engagement(m: dict) -> float:
    """One number per metrics row. Shares and profile taps dominate because
    they mean the joke traveled or converted; completion scales with views."""
    views = m.get("views", 0) or 0
    return (m.get("likes", 0) + 5 * m.get("shares", 0)
            + 3 * m.get("profile_taps", 0) + views * m.get("completion", 0.0))


def family_scores(days: int = 30, path: Path | str | None = None) -> dict:
    """family -> {posts, engagement, rate}. rate = engagement per post."""
    posts: dict[str, dict] = {}
    metrics: dict[str, list[dict]] = {}
    for r in _rows(path, days):
        if r.get("type") == "post":
            posts[r["post_ref"]] = r
        elif r.get("type") == "metrics" and r.get("post_ref") in posts:
            metrics.setdefault(r["post_ref"], []).append(r)
    fams: dict[str, dict] = {}
    for ref, post in posts.items():
        fam = post.get("family", "")
        eng = sum(engagement(m) for m in metrics.get(ref, []))
        d = fams.setdefault(fam, {"posts": 0, "engagement": 0.0})
        d["posts"] += 1
        d["engagement"] += eng
    for fam, d in fams.items():
        d["rate"] = d["engagement"] / max(d["posts"], 1)
    return fams


def block_scores(days: int = 30, path: Path | str | None = None) -> dict:
    """block_id -> {posts, engagement, rate}. Same math as families, so we
    learn which BLOCK works, not just which joke."""
    posts: dict[str, dict] = {}
    metrics: dict[str, list[dict]] = {}
    for r in _rows(path, days):
        if r.get("type") == "post" and r.get("block_id"):
            posts[r["post_ref"]] = r
        elif r.get("type") == "metrics" and r.get("post_ref") in posts:
            metrics.setdefault(r["post_ref"], []).append(r)
    blocks: dict[str, dict] = {}
    for ref, post in posts.items():
        bid = post.get("block_id", "")
        eng = sum(engagement(m) for m in metrics.get(ref, []))
        d = blocks.setdefault(bid, {"posts": 0, "engagement": 0.0})
        d["posts"] += 1
        d["engagement"] += eng
    for bid, d in blocks.items():
        d["rate"] = d["engagement"] / max(d["posts"], 1)
    return blocks


def weights(days: int = 30, path: Path | str | None = None) -> dict[str, float]:
    """family -> multiplier >= 1.0. No signal yet: everything 1.0 (no-op).
    Signal: families above the mean rate earn up to 2x."""
    scores = family_scores(days, path)
    if not scores:
        return {}
    mean = sum(d["rate"] for d in scores.values()) / len(scores)
    if mean <= 0:
        return {fam: 1.0 for fam in scores}
    return {fam: round(min(2.0, 1.0 + max(0.0, d["rate"] - mean) / mean), 3)
            for fam, d in scores.items()}


def apply_ranking(items: list[dict], w: dict[str, float] | None = None,
                  days: int = 30, path: Path | str | None = None) -> list[dict]:
    """Stable sort by family weight (desc). Items without a known family
    keep relative order at weight 1.0."""
    w = w if w is not None else weights(days, path)
    if not w:
        return list(items)

    def fam_of(t: dict) -> str:
        return str(t.get("family") or "")

    return sorted(items, key=lambda t: (-w.get(fam_of(t), 1.0), t.get("id", "")))
