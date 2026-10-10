"""Internal feasibility score: gates agents, never auto-publishes.

Rates a compiled gift/recipe 0–100 across manufacturing cost (40),
availability (20), assembly (15), safety (10) and shipping (15).
≥60 = explorable/publishable candidate; below = rework with reasons.
Pure function — no network, no DB. Docs: docs/oddhobb-model.md.
"""
from __future__ import annotations

GATE = 60


def score_gift(compiled: dict, safety_flags: list | None = None) -> dict:
    """Score a compile_gift() result. Safety flags: e.g. ["kids", "battery",
    "ingestible"] — kids/battery each cost half the safety budget."""
    safety_flags = safety_flags or []
    target = max(1, int(compiled.get("target_cents") or 1))
    lines = compiled.get("lines") or []
    ship = compiled.get("ship_cents")
    reasons = list(compiled.get("reasons") or [])

    # Cost (40): margin left after materials (+ship when quoted).
    known = int(compiled.get("materials_cents") or 0)
    if ship is not None:
        known += int(ship)
    margin = (target - known) / target
    cost = max(0, min(40, round(40 * margin / 0.6)))

    # Availability (20): share of feasible lines.
    avail = round(20 * sum(1 for l in lines if l.get("feasible"))
                 / max(1, len(lines))) if lines else 0

    # Assembly (15): fewer distinct lines = simpler pack. Full marks ≤6.
    assembly = max(0, 15 - max(0, len(lines) - 6) * 3) if lines else 0

    # Safety (10): kids/battery/ingestible halve it cumulatively.
    safety = 10
    for flag in ("kids", "battery", "ingestible"):
        if flag in safety_flags:
            safety //= 2
            reasons.append(f"safety review: {flag}")

    # Shipping (15): quoted and ≤20% of target = full; unquoted = 0.
    if ship is None:
        shipping = 0
        reasons.append("shipping unquoted")
    else:
        ratio = ship / target
        shipping = max(0, round(15 * (0.6 - ratio) / 0.4)) if ratio < 0.6 else 0

    total = cost + avail + assembly + safety + shipping
    purchasable = bool(compiled.get("purchasable", False))
    if not purchasable:
        reasons.append("not purchasable — rights/manufacturing unvalidated")
    return {"score": total, "gate": GATE,
            "publishable": total >= GATE and purchasable,
            "parts": {"cost": cost, "availability": avail,
                      "assembly": assembly, "safety": safety,
                      "shipping": shipping},
            "reasons": reasons}
