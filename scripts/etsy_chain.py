#!/usr/bin/env python3
"""Chain: wait for ornament 2000px render → run keychain 2000px → etsy_pack.

    python3 scripts/etsy_chain.py
"""
from __future__ import annotations

import os
import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BLENDER = "/home/ubuntu/opt/blender-4.2.9-linux-x64/blender"
MARKETING = ROOT / "data" / "marketing"
LOG = Path("/tmp/opencode/render_chain.log")


def orn_ready() -> bool:
    need = ["mkt-hero.png", "mkt-front.png", "mkt-back.png", "mkt-left.png",
            "mkt-right.png", "mkt-hang.png", "mkt-hang-side.png",
            "mkt-hook-close.png", "mkt-hook-side.png"]
    for name in need:
        p = MARKETING / name
        if not p.exists() or p.stat().st_size < 400_000:
            return False
        # 2000px check via file header is heavy; size heuristic + later PIL
    try:
        from PIL import Image
    except ImportError:
        return True
    for name in need:
        p = MARKETING / name
        if not p.exists():
            return False
        if Image.open(p).size[0] < 1800:
            return False
    return True


def blender_running() -> bool:
    out = subprocess.run(["pgrep", "-f", "render_product.py"], capture_output=True, text=True)
    return bool(out.stdout.strip())


def run(cmd: list[str]) -> int:
    with LOG.open("a") as f:
        f.write(f"\n=== {time.strftime('%H:%M:%S')} {' '.join(cmd)} ===\n")
        f.flush()
        p = subprocess.run(cmd, cwd=str(ROOT), stdout=f, stderr=subprocess.STDOUT)
        return p.returncode


def main() -> int:
    LOG.parent.mkdir(parents=True, exist_ok=True)
    # wait for ornament pass if still going
    deadline = time.time() + 3600
    while time.time() < deadline:
        if blender_running() and not orn_ready():
            print("waiting for ornament 2000px pass...", flush=True)
            time.sleep(20)
            continue
        if orn_ready() or not blender_running():
            break
        time.sleep(10)

    if not orn_ready():
        print("ornament set incomplete — check /tmp/opencode/render_orn_2k.log", flush=True)
        # still try keychain if blender free
    if blender_running():
        print("blender still busy, waiting...", flush=True)
        while blender_running() and time.time() < deadline:
            time.sleep(15)

    print("starting keychain 2000px pass", flush=True)
    rc = run([
        BLENDER, "--background", "--python", "scripts/render_product.py", "--",
        "--in", "data/uploads/chibi-figure-hook.glb",
        "--out", "data/marketing",
        "--size", "2000", "--bg", "white", "--shots", "keychain",
        "--variant", "keychain", "--sat", "1.45",
    ])
    print(f"keychain rc={rc}", flush=True)

    print("running etsy_pack.py", flush=True)
    rc2 = run(["python3", "scripts/etsy_pack.py"])
    print(f"etsy_pack rc={rc2}", flush=True)
    return rc or rc2


if __name__ == "__main__":
    raise SystemExit(main())
