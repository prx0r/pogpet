"""Delivery traces — how a premise was performed, beat by beat.

V1 is a scaffold: the trace schema is frozen, analysis backends plug in
later. Sources: Qwen3.8-Omni-Flash (+ Qwen-MM-Plugins omni-memory) for
semantic multimodal interpretation, WhisperX for word alignment, a laughter
detector for onset/duration, pose/face extraction for motion. No network
calls happen here; analyze() refuses without its key, same house rule as
every provider in this repo.
"""
from __future__ import annotations

REQUIRED_BEAT = ("beat", "mechanism", "delivery", "response")
REQUIRED_DELIVERY = ("pre_pause_ms", "words_per_second", "gaze", "body")
REQUIRED_RESPONSE = ("laugh_onset_ms", "duration_ms")


def validate_trace(t: dict) -> list[str]:
    gaps = []
    for k in REQUIRED_BEAT:
        if k not in t:
            gaps.append(f"missing {k}")
    for k in REQUIRED_DELIVERY:
        if k not in (t.get("delivery") or {}):
            gaps.append(f"delivery missing {k}")
    for k in REQUIRED_RESPONSE:
        if k not in (t.get("response") or {}):
            gaps.append(f"response missing {k}")
    return gaps


def analyze(video_ref: str, *, api_key: str = "") -> dict:
    """Full pipeline: Qwen omni (semantic) + WhisperX (alignment) + laugh
    detector (onset) + pose (motion) fused into beat traces. Stub until
    a DASHSCOPE_API_KEY is provided and the harness is built."""
    if not api_key:
        raise RuntimeError("delivery analysis needs DASHSCOPE_API_KEY")
    raise NotImplementedError("Qwen harness not built yet; schema is frozen")
