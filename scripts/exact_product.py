#!/usr/bin/env python3
"""P0 exact product photos — canonical mesh only, no props.

    python3 scripts/exact_product.py

Ornament: chibi-figure-hook.glb @ 80mm, white bg, --exact
Keychain: same GLB @ 60mm, white bg, --exact (smaller SKU, still exact mesh)
Outputs -> data/productimg/prod/  (public /img/prod/)
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
DEST = ROOT / "data" / "productimg" / "prod"
LOG = DEST / "_run.log"


def run(label: str, outdir: Path, scale_mm: float, shots: str) -> int:
    outdir.mkdir(parents=True, exist_ok=True)
    cmd = [
        BLENDER, "--background", "--python", "scripts/render_product.py", "--",
        "--in", MESH,
        "--out", str(outdir),
        "--size", "2000",
        "--bg", "white",
        "--shots", shots,
        "--exact",
        "--scale-mm", str(scale_mm),
        "--sat", "1.35",
    ]
    print(f"{label}: scale={scale_mm}mm shots={shots}", flush=True)
    with open(LOG, "a") as log:
        log.write(f"\n=== {label} {time.strftime('%H:%M:%S')} ===\n")
        log.flush()
        rc = subprocess.run(cmd, cwd=str(ROOT), stdout=log, stderr=subprocess.STDOUT).returncode
    print(f"{label} rc={rc}", flush=True)
    return rc


def publish() -> None:
    DEST.mkdir(parents=True, exist_ok=True)
    # canonical GLB for the viewer
    shutil.copy2(ROOT / "data" / "uploads" / "chibi-figure-hook.glb",
                 DEST / "chibi-figure-hook.glb")
    # ornament exact shots -> prod-*.png
    orn_src = ROOT / "data" / "marketing" / "ornament"
    kc_src = ROOT / "data" / "marketing" / "keychain"
    for src_dir, mapping in (
        (orn_src, {
            "prod-hero.png": "prod-hero.png",
            "prod-front.png": "prod-front.png",
            "prod-side.png": "prod-side.png",
            "prod-back.png": "prod-back.png",
            "prod-loop.png": "prod-loop.png",
        }),
        (kc_src, {
            "prod-hero.png": "kc-hero.png",
            "prod-front.png": "kc-front.png",
            "prod-side.png": "kc-side.png",
            "prod-back.png": "kc-back.png",
            "prod-loop.png": "kc-loop.png",
        }),
    ):
        for src_name, dest_name in mapping.items():
            src = src_dir / src_name
            if not src.exists():
                print(f"MISSING {src}")
                continue
            shutil.copy2(src, DEST / dest_name)
            print(f"published {dest_name} {src.stat().st_size//1024}KB")


def main() -> int:
    DEST.mkdir(parents=True, exist_ok=True)
    if LOG.exists():
        LOG.unlink()
    rc1 = run("ornament", ROOT / "data" / "marketing" / "ornament", 80.0, "exact")
    rc2 = run("keychain", ROOT / "data" / "marketing" / "keychain", 60.0, "exact")
    publish()
    print("EXACT DONE", flush=True)
    return rc1 or rc2


if __name__ == "__main__":
    raise SystemExit(main())
