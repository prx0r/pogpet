#!/usr/bin/env python3
"""P1 — publish coat library hero/front stills to public /img/coats/.

    python3 scripts/coat_gallery.py

Picks mkt-hero.png + mkt-front.png per coat from data/coats/<coat>/.
0 Meshy credits.
"""
from __future__ import annotations

import shutil
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "data" / "coats"
DEST = ROOT / "data" / "productimg" / "coats"
COATS = ["cream", "golden", "chocolate", "black", "fawn", "grey"]
WANT = ["mkt-hero.png", "mkt-front.png"]


def main() -> int:
    DEST.mkdir(parents=True, exist_ok=True)
    missing = []
    for coat in COATS:
        src_dir = SRC / coat
        for name in WANT:
            src = src_dir / name
            if not src.exists():
                missing.append(f"{coat}/{name}")
                continue
            im = Image.open(src)
            if im.size[0] < 1000:
                missing.append(f"{coat}/{name} ({im.size})")
                continue
            dest = DEST / f"coat-{coat}-{name.replace('mkt-', '').replace('.png', '')}.png"
            shutil.copy2(src, dest)
            print(f"OK {dest.name:32} {im.size[0]}px {dest.stat().st_size//1024}KB")
    if missing:
        print("MISSING:", ", ".join(missing))
        return 1
    print(f"coats gallery -> {DEST}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
