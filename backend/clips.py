"""Viral clip planner: cut-list for perform outputs.

Borrowed shape from freaktown's clips/planner (TikTok 63–75s window,
best-20s hook, best-40s social, score-reveal tail) minus the laugh buckets
we don't have — our cuts are time-based and honest about it. ffmpeg does
the cutting; this module only plans.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

TIKTOK_MIN_S = 63.0
TIKTOK_MAX_S = 75.0


def probe_duration(mp4: Path) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(mp4)],
        capture_output=True, text=True, timeout=60)
    try:
        return max(0.0, float((out.stdout or "").strip()))
    except ValueError:
        return 0.0


def plan(duration_s: float) -> dict:
    """Cut-list for one finished clip. All times seconds."""
    cuts = [{"id": "full", "start": 0.0, "end": duration_s,
             "label": "full set"}]
    if duration_s >= 20:
        cuts.append({"id": "best-20s", "start": 0.0,
                     "end": min(20.0, duration_s), "label": "viral hook"})
    if duration_s >= 40:
        cuts.append({"id": "best-40s", "start": 0.0,
                     "end": min(40.0, duration_s), "label": "social cut"})
    if duration_s > 45:
        cuts.append({"id": "score-reveal", "start": max(0.0, duration_s - 12.0),
                     "end": duration_s, "label": "tail reveal"})
    tiktok_ok = TIKTOK_MIN_S <= duration_s <= TIKTOK_MAX_S
    return {"duration_s": round(duration_s, 2), "cuts": cuts,
            "tiktok_window_ok": tiktok_ok,
            "note": "time-based cuts; laugh-density windows arrive with judging"}


def render_cut(src: Path, start: float, end: float, dest: Path) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["ffmpeg", "-y", "-ss", f"{start:.2f}", "-to", f"{end:.2f}",
         "-i", str(src), "-c", "copy", str(dest)],
        capture_output=True, timeout=300, check=True)
    return dest
