"""Parametric CAD adapter (build123d, isolated venv).

Thin layer, not a CAD rewrite: run scripts/parametric_panel.py under the
cad venv, get back verified STL + dims + volume for BOMs and estimates.
Without the venv every call stages honestly (InvenTree/CADAM pattern:
parameters in, verified geometry out — never faked).
"""
from __future__ import annotations

import os
import subprocess

CAD_PYTHON = os.environ.get(
    "CAD_PYTHON", "/home/ubuntu/.venvs/cad/bin/python")


def available() -> bool:
    import pathlib as _p
    return _p.Path(CAD_PYTHON).exists()


def panel(w: float = 100, h: float = 80, t: float = 3,
          hole_r: float = 2, inset: float = 8,
          out: str = "data/cad/tinywall_100x80.stl") -> dict:
    """Wall panel with mounting holes. Staged without the cad venv."""
    if not available():
        return {"ok": False, "staged": True,
                "error": "no cad venv — pip install build123d (≈1GB)"}
    try:
        r = subprocess.run(
            [CAD_PYTHON, "scripts/parametric_panel.py",
             "--w", str(w), "--h", str(h), "--t", str(t),
             "--hole-r", str(hole_r), "--inset", str(inset),
             "--out", out],
            capture_output=True, text=True, timeout=300, cwd=".")
    except Exception as e:
        return {"ok": False, "error": str(e)[:200]}
    if r.returncode != 0:
        return {"ok": False, "error": (r.stderr or "")[-300:]}
    return {"ok": True, "out": out, "log": (r.stdout or "")[-300:]}
