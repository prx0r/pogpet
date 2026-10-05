#!/usr/bin/env python3
"""Factory stills finish: composite RGBA renders onto pure white + QC.

    python3 scripts/factory/stills_finish.py /tmp/stills/line_reader \
        --line line_reader --dest data/productimg/prod

Reads hero/front/side/back.png (transparent film), pastes onto white,
writes <line>-{hero,front,side,back}.png, prints blown/crushed QC per file.
Targets (white tiles): blown < 25%, crushed < 2%.
"""
from __future__ import annotations

import argparse
from pathlib import Path

try:
    from PIL import Image
    import numpy as np
except ImportError:
    raise SystemExit("need PIL + numpy: pip install pillow numpy")


def qc(path: Path) -> dict:
    img = Image.open(path).convert("RGB")
    a = np.asarray(img).astype(float)
    h, w, _ = a.shape
    y0, y1, x0, x1 = int(h * 0.15), int(h * 0.85), int(w * 0.15), int(w * 0.85)
    crop = a[y0:y1, x0:x1].reshape(-1, 3)
    bg = (crop[:, 0] > 242) & (crop[:, 1] > 242) & (crop[:, 2] > 238)
    fg = crop[~bg]
    if len(fg) == 0:
        return {"blown": 0.0, "crushed": 0.0, "empty": True}
    blown = float(((fg[:, 0] > 250) & (fg[:, 1] > 235) & (fg[:, 2] > 210)).mean() * 100)
    crushed = float((fg.mean(axis=1) < 40).mean() * 100)
    return {"blown": round(blown, 1), "crushed": round(crushed, 1), "empty": False}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("srcdir")
    ap.add_argument("--line", required=True)
    ap.add_argument("--dest", required=True)
    a = ap.parse_args()
    src, dest = Path(a.srcdir), Path(a.dest)
    dest.mkdir(parents=True, exist_ok=True)
    white = Image.new("RGB", (1, 1), (255, 255, 255))
    for shot in ("hero", "front", "side", "back"):
        f = src / f"{shot}.png"
        if not f.exists():
            print(f"  MISSING {shot}")
            continue
        rgba = Image.open(f).convert("RGBA")
        bg = Image.new("RGB", rgba.size, (255, 255, 255))
        bg.paste(rgba, mask=rgba.split()[3])
        out = dest / f"{a.line}-{shot}.png"
        # slight punch to match the AgX-Punchy product look
        bg.save(out)
        q = qc(out)
        flag = "OK " if (q["blown"] < 25 and q["crushed"] < 2 and not q["empty"]) else "CHECK"
        print(f"  [{flag}] {out.name} blown={q['blown']}% crushed={q['crushed']}%")
    _ = white
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
