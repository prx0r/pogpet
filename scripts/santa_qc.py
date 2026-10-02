#!/usr/bin/env python3
"""P1 santa hat QC — free Blender, withhold unless seat looks right.

    python3 scripts/santa_qc.py

Renders a tiny set (hero/front/back) with --prop santa + OGA hat asset at
1000px. Output to data/santa_qc/ for human/tagged-image review. NOT auto-
published. 0 Meshy credits.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BLENDER = "/home/ubuntu/opt/blender-4.2.9-linux-x64/blender"
HAT = "data/assets/hats/oga-santa/santa_hat.fbx"
OUT = ROOT / "data" / "santa_qc"
LOG = OUT / "_run.log"


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    # Only need hero/front/back — run marketing set at 1000 then keep those three
    cmd = [
        BLENDER, "--background", "--python", "scripts/render_product.py", "--",
        "--in", "data/uploads/chibi-figure-hook.glb",
        "--out", str(OUT),
        "--size", "1000", "--bg", "white", "--shots", "marketing",
        "--prop", "santa", "--hat-asset", HAT, "--sat", "1.45",
    ]
    print("santa QC render ...", flush=True)
    with open(LOG, "w") as log:
        rc = subprocess.run(cmd, cwd=str(ROOT), stdout=log, stderr=subprocess.STDOUT).returncode
    print(f"santa QC rc={rc} -> {OUT}", flush=True)
    for p in sorted(OUT.glob("santa-*.png")):
        print(f"  {p.name} {p.stat().st_size//1024}KB")
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
