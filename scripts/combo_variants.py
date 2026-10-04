#!/usr/bin/env python3
"""Render coat × santa combo stills + extra pattern heroes — free Blender.

    python3 scripts/combo_variants.py

Uses existing OGA CC0 santa hat + canonical dog mesh. 0 Meshy credits.
Publishes to data/productimg/prod/ as:
  coat-<coat>-santa-{hero,front,side,back,loop}.png
  coat-<coat>-<pattern>-hero.png
"""
from __future__ import annotations

import shutil
import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BLENDER = "/home/ubuntu/opt/blender-4.2.9-linux-x64/blender"
MESH = "data/uploads/chibi-figure-hook.glb"
HAT = "data/assets/hats/oga-santa/santa_hat.fbx"
OUT = ROOT / "data" / "marketing" / "combos"
DEST = ROOT / "data" / "productimg" / "prod"
LOG = OUT / "_run.log"

# P0 combos — coat grade + santa hat on the same dog mesh
COMBOS = [
    ("cream", "santa"),
    ("golden", "santa"),
    ("chocolate", "santa"),
    ("black", "santa"),
]
# Pattern heroes that are missing or thin
PATTERNS = [
    ("cream", "spots"),
    ("cream", "stripes"),
    ("golden", "spots"),
    ("chocolate", "stripes"),
    ("black", "spots"),
]


def run(extra: list[str], outdir: Path) -> int:
    outdir.mkdir(parents=True, exist_ok=True)
    cmd = [
        BLENDER, "--background", "--python", "scripts/render_product.py", "--",
        "--in", MESH, "--out", str(outdir),
        "--size", "1400", "--bg", "white", "--shots", "marketing", "--sat", "1.40",
        *extra,
    ]
    with open(LOG, "a") as log:
        log.write(f"\n=== {time.strftime('%H:%M:%S')} {extra} ===\n")
        log.flush()
        return subprocess.run(cmd, cwd=str(ROOT), stdout=log, stderr=subprocess.STDOUT).returncode


def publish(src: Path, dest_name: str) -> None:
    if not src.exists():
        print(f"  MISSING {src.name}")
        return
    DEST.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, DEST / dest_name)
    print(f"  published {dest_name} {(DEST / dest_name).stat().st_size // 1024}KB")


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    DEST.mkdir(parents=True, exist_ok=True)
    if LOG.exists():
        LOG.unlink()
    rc_all = 0
    shots = ["prod-hero.png", "prod-front.png", "prod-side.png", "prod-back.png", "prod-loop.png"]

    for coat, hat in COMBOS:
        outdir = OUT / f"{coat}-{hat}"
        # --prop santa uses the procedural seat (reliable on this dog mesh).
        # Do NOT pass --hat-asset — OGA FBX floats on the lab skull.
        rc = run(["--no-hook", "--coat", coat, "--prop", hat], outdir)
        rc_all |= rc
        for name in shots:
            publish(outdir / name, f"coat-{coat}-{hat}-{name.replace('prod-', '')}")
        print(f"combo {coat}+{hat} rc={rc}", flush=True)

    for coat, pat in PATTERNS:
        outdir = OUT / f"{coat}-{pat}"
        outdir.mkdir(parents=True, exist_ok=True)
        cmd = [
            BLENDER, "--background", "--python", "scripts/coat_retexture.py", "--",
            "--in", MESH, "--out", str(outdir),
            "--coat", coat, "--pattern", pat, "--size", "1400",
        ]
        with open(LOG, "a") as log:
            log.write(f"\n=== {time.strftime('%H:%M:%S')} pattern {coat}+{pat} ===\n")
            log.flush()
            rc = subprocess.run(cmd, cwd=str(ROOT), stdout=log, stderr=subprocess.STDOUT).returncode
        rc_all |= rc
        # coat_retexture writes coat-<coat>-<pattern>-hero.png directly
        publish(outdir / f"coat-{coat}-{pat}-hero.png", f"coat-{coat}-{pat}-hero.png")
        print(f"pattern {coat}+{pat} rc={rc}", flush=True)

    print("COMBOS DONE" if rc_all == 0 else f"COMBOS DONE rc={rc_all}", flush=True)
    return rc_all


if __name__ == "__main__":
    raise SystemExit(main())
