"""Gaussian light-field engine for the Stone optical stack.

Two curved LED tracks, moving-Gaussian law per LED:
    I_i(t) = A(t) * exp(-((s_i - p(t))^2) / (2 * sigma(t)^2))
with gamma correction + temporal smoothing, so peaks live between
diodes and motion never steps. Pure functions: runs on the phone,
on the MCU port, or in tests identically.
"""
from __future__ import annotations

import math

GAMMA = 2.2


def track_positions(n: int, track: int = 0) -> list[float]:
    """s in [0,1] along a curved track. Track 1 is phase-offset so the
    two paths interleave rather than mirror."""
    if n <= 1:
        return [0.5]
    off = 0.5 / n if track == 1 else 0.0
    return [min(1.0, max(0.0, i / (n - 1) + off)) for i in range(n)]


def gamma_encode(x: float) -> int:
    """Perceptual correction to 8-bit PWM. Linear fades look steppy;
    gamma-encoded fades look liquid."""
    x = min(1.0, max(0.0, x))
    return int(round(255 * (x ** (1.0 / GAMMA))))


def field_frame(n: int, p: float, sigma: float, amp: float,
                track: int = 0) -> list[int]:
    """One frame: PWM per LED for a Gaussian centred at p, width sigma."""
    out = []
    for s in track_positions(n, track):
        if sigma <= 0:
            i = amp if abs(s - p) < 1e-9 else 0.0
        else:
            i = amp * math.exp(-((s - p) ** 2) / (2 * sigma ** 2))
        out.append(gamma_encode(i))
    return out


def smooth(prev: list[int], nxt: list[int], alpha: float = 0.35) -> list[int]:
    """Temporal smoothing between frames (alpha=new weight)."""
    return [int(round(a + (b - a) * alpha)) for a, b in zip(prev, nxt)]


def breath_to_field(expansion: float, n: int = 20) -> dict:
    """Breath expansion 0..1 -> full-field swell (both tracks)."""
    amp = 0.15 + 0.85 * min(1.0, max(0.0, expansion))
    return {"track0": field_frame(n, 0.5, 0.9, amp, 0),
            "track1": field_frame(n, 0.5, 0.9, amp, 1)}


def stillness(n: int = 20) -> dict:
    """True zero. Leakage check happens in a dark room, not here."""
    return {"track0": [0] * n, "track1": [0] * n}


def travel(n: int, t01: float, width: float = 0.28,
           intensity: float = 0.42) -> dict:
    """One pulse travelling track0 start->end; track1 holds faint echo."""
    return {"track0": field_frame(n, t01, width, intensity, 0),
            "track1": field_frame(n, t01, width * 1.6, intensity * 0.25, 1)}
