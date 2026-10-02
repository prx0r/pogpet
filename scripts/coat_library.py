#!/usr/bin/env python3
"""P1 coat library — free Blender grades on the locked dog mesh.

    python3 scripts/coat_library.py

One marketing set per coat at 1200px white bg, printed hardware off
(plain body shots for colour comparison). 0 Meshy credits.
"""
from __future__ import annotations

import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BLENDER = "/home/ubuntu/opt/blender-4.2.9-linux-x64/blender"
COATS = ["cream", "golden", "chocolate", "black", "fawn", "grey"]
LOG = ROOT / "data" / "coats" / "_run.log"


def main() -> int:
    LOG.parent.mkdir(parents=True, exist_ok=True)
    overall = 0
    with LOG.open("a") as log:
        log.write(f"\n=== coat library {time.strftime('%Y-%m-%d %H:%M:%S')} ===\n")
        log.flush()
        for coat in COATS:
            out = ROOT / "data" / "coats" / coat
            out.mkdir(parents=True, exist_ok=True)
            log.write(f"--- {coat} ---\n")
            log.flush()
            cmd = [
                BLENDER, "--background", "--python", "scripts/render_product.py", "--",
                "--in", "data/uploads/chibi-figure-hook.glb",
                "--out", str(out),
                "--size", "1200", "--bg", "white", "--shots", "marketing",
                "--coat", coat, "--sat", "1.45", "--no-hook",
            ]
            print(f"coat {coat} ...", flush=True)
            with open(LOG, "a") as child:
                rc = subprocess.run(
                    cmd, cwd=str(ROOT), stdout=child, stderr=subprocess.STDOUT
                ).returncode
            log.write(f"coat {coat} rc={rc}\n")
            log.flush()
            print(f"coat {coat} rc={rc}", flush=True)
            if rc != 0:
                overall = rc
    print("COATS DONE" if overall == 0 else f"COATS DONE with rc={overall}", flush=True)
    return overall


if __name__ == "__main__":
    raise SystemExit(main())
