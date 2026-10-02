#!/usr/bin/env python3
"""P1 — coats + santa on white backdrop, canonical mesh, free Blender.

    python3 scripts/p1_variants.py

Coats: material grade only (cream/golden/chocolate/black/fawn/grey) on the
exact mesh — white bg, --exact (no props).
Santa: --prop santa + OGA CC0 hat asset seated on measured skull — white bg.
Output: data/marketing/variants/<coat|santa>/
Publish: data/productimg/prod/ as coat-*.png / santa-*.png
0 Meshy credits.
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
VARIANTS = ROOT / "data" / "marketing" / "variants"
DEST = ROOT / "data" / "productimg" / "prod"
LOG = VARIANTS / "_run.log"
COATS = ["cream", "golden", "chocolate", "black", "fawn", "grey"]


def run_blender(outdir: Path, extra: list[str]) -> int:
    outdir.mkdir(parents=True, exist_ok=True)
    cmd = [
        BLENDER, "--background", "--python", "scripts/render_product.py", "--",
        "--in", MESH,
        "--out", str(outdir),
        "--size", "1400",
        "--bg", "white",
        "--shots", "marketing",
        "--sat", "1.40",
        *extra,
    ]
    with open(LOG, "a") as log:
        log.write(f"\n=== {outdir.name} {time.strftime('%H:%M:%S')} {extra} ===\n")
        log.flush()
        rc = subprocess.run(cmd, cwd=str(ROOT), stdout=log, stderr=subprocess.STDOUT).returncode
    print(f"{outdir.name} rc={rc} {extra}", flush=True)
    return rc


def publish(src_dir: Path, dest_prefix: str, names: list[str]) -> None:
    DEST.mkdir(parents=True, exist_ok=True)
    for name in names:
        src = src_dir / name
        if not src.exists():
            print(f"  MISSING {src.name}")
            continue
        dest = DEST / f"{dest_prefix}-{name.replace('mkt-', '').replace('prod-', '')}"
        shutil.copy2(src, dest)
        print(f"  published {dest.name} {dest.stat().st_size//1024}KB")


def main() -> int:
    VARIANTS.mkdir(parents=True, exist_ok=True)
    DEST.mkdir(parents=True, exist_ok=True)
    if LOG.exists():
        LOG.unlink()
    overall = 0

    # ── coats: exact mesh + material grade only, white bg ──────────────
    # --exact + --shots marketing writes prod-*.png (see render_product.py)
    src_names = ["prod-hero.png", "prod-front.png", "prod-side.png",
                 "prod-back.png", "prod-loop.png"]
    for coat in COATS:
        out = VARIANTS / coat
        rc = run_blender(out, ["--exact", "--no-hook", "--coat", coat])
        overall |= rc
        publish(out, f"coat-{coat}", src_names)

    # ── santa: hat seated on skull, no coat grade ──────────────────────
    santa_out = VARIANTS / "santa"
    rc = run_blender(santa_out, ["--prop", "santa", "--hat-asset", HAT])
    overall |= rc
    publish(santa_out, "santa", src_names)

    print("P1 VARIANTS DONE" if overall == 0 else f"P1 VARIANTS DONE rc={overall}", flush=True)
    return overall


if __name__ == "__main__":
    raise SystemExit(main())
