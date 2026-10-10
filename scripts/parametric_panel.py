#!/usr/bin/env python3
"""Parametric CAD under the isolated CAD venv (build123d, no system deps).

Run with: /home/ubuntu/.venvs/cad/bin/python scripts/parametric_panel.py ...

Subcommands produce exact manufacturing geometry (STL) with volume
assertions — the influenced-by-CADAM pattern: parameters in, verified
geometry + BOM quantities out. Blender stays for organic meshes.
"""
from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path

try:
    from build123d import Box, Cylinder, Pos, export_stl
    HAVE_CAD = True
except ImportError:
    HAVE_CAD = False


def panel(w: float, h: float, t: float, holes: list, hole_r: float,
          out: Path) -> dict:
    """Wall panel w×h×t mm with through-holes. Returns dims + volume."""
    if not HAVE_CAD:
        raise RuntimeError("build123d missing — use the cad venv")
    part = Box(w, h, t)
    for x, y in holes:
        part -= Pos(x, y, 0) * Cylinder(hole_r, t)
    expected = w * h * t - len(holes) * math.pi * hole_r ** 2 * t
    if abs(part.volume - expected) > max(1.0, expected * 1e-6):
        raise ValueError(f"hole mismatch: {part.volume} vs {expected}")
    export_stl(part, str(out))
    return {"w": w, "h": h, "t": t, "holes": len(holes),
            "volume_mm3": round(part.volume, 1),
            "stl_bytes": out.stat().st_size}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--w", type=float, default=100)
    ap.add_argument("--h", type=float, default=80)
    ap.add_argument("--t", type=float, default=3)
    ap.add_argument("--hole-r", type=float, default=2)
    ap.add_argument("--inset", type=float, default=8)
    ap.add_argument("--out", default="data/cad/tinywall_100x80.stl")
    args = ap.parse_args()
    if not HAVE_CAD:
        print("staged: no build123d (cad venv) on this interpreter")
        return 0
    holes = [(-args.w / 2 + args.inset, -args.h / 2 + args.inset),
             (args.w / 2 - args.inset, -args.h / 2 + args.inset),
             (-args.w / 2 + args.inset, args.h / 2 - args.inset),
             (args.w / 2 - args.inset, args.h / 2 - args.inset)]
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    print(panel(args.w, args.h, args.t, holes, args.hole_r, out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
