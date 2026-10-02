#!/usr/bin/env python3
"""P0 Etsy pack — copy 2000px listing stills into public /img/etsy/.

    python3 scripts/etsy_pack.py

Reads data/marketing/ mkt-*.png + kc-*.png (must be 2000px).
Writes:
  data/productimg/etsy/   local mirror
  site/img/etsy/          public files the bridge serves at /img/etsy/
Optionally stamps a light scale caption on hero shots.
Zero Meshy credits.
"""
from __future__ import annotations

import shutil
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "data" / "marketing"
LOCAL = ROOT / "data" / "productimg" / "etsy"
# /img/* is served from data/productimg by the bridge — public path /img/etsy/…
PUBLIC = ROOT / "data" / "productimg" / "etsy"

# Etsy-friendly names → source file
PACK = {
    "etsy-orn-hero.png": "mkt-hero.png",
    "etsy-orn-front.png": "mkt-front.png",
    "etsy-orn-side.png": "mkt-left.png",
    "etsy-orn-back.png": "mkt-back.png",
    "etsy-orn-hang.png": "mkt-hang.png",
    "etsy-orn-hook-detail.png": "mkt-hook-close.png",
    "etsy-kc-hero.png": "kc-hero.png",
    "etsy-kc-front.png": "kc-front.png",
    "etsy-kc-back.png": "kc-back.png",
    "etsy-kc-side.png": "kc-left.png",
    "etsy-kc-ring-detail.png": "kc-ring-close.png",
    "etsy-kc-ring-side.png": "kc-ring-side.png",
}

# light caption on heroes only
CAPTIONS = {
    "etsy-orn-hero.png": "ornament · ~80 mm",
    "etsy-kc-hero.png": "keychain · ~80 mm · printed ring",
}


def stamp_caption(path: Path, text: str) -> None:
    im = path.open("rb") and Image.open(path)
    im = im.convert("RGB")
    draw = ImageDraw.Draw(im)
    w, h = im.size
    # bottom bar
    bar_h = max(36, h // 28)
    draw.rectangle([0, h - bar_h, w, h], fill=(20, 20, 22))
    font = None
    for fp in (
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    ):
        if Path(fp).exists():
            try:
                font = ImageFont.truetype(fp, max(16, bar_h // 2))
                break
            except OSError:
                font = None
    # text anchor
    if font:
        bbox = draw.textbbox((0, 0), text, font=font)
        tw = bbox[2] - bbox[0]
        th = bbox[3] - bbox[1]
        x = (w - tw) // 2
        y = h - bar_h + (bar_h - th) // 2
        draw.text((x, y), text, fill=(244, 241, 234), font=font)
    else:
        draw.text((w // 2 - 40, h - bar_h + 8), text, fill=(244, 241, 234))
    # re-save as PNG RGB
    im.save(path, "PNG", optimize=True)


def main() -> int:
    LOCAL.mkdir(parents=True, exist_ok=True)
    PUBLIC.mkdir(parents=True, exist_ok=True)
    missing = []
    copied = []
    for dest_name, src_name in PACK.items():
        src = SRC / src_name
        if not src.exists():
            missing.append(src_name)
            continue
        im = Image.open(src)
        if im.size[0] < 1800:
            print(f"SKIP {src_name}: only {im.size} (need ~2000px)")
            missing.append(f"{src_name} ({im.size})")
            continue
        for dest_dir in (LOCAL, PUBLIC):
            dest_dir.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dest_dir / dest_name)
        if dest_name in CAPTIONS:
            # stamp public copy only (local mirror keeps the clean render)
            stamp_caption(PUBLIC / dest_name, CAPTIONS[dest_name])
        copied.append((dest_name, im.size, (PUBLIC / dest_name).stat().st_size))
        print(f"OK {dest_name:28} {im.size[0]}px  {(PUBLIC / dest_name).stat().st_size // 1024}KB")

    if missing:
        print("MISSING / too small:", ", ".join(missing))
    print(f"\npack: {len(copied)} files -> {PUBLIC}")
    print("local mirror:", LOCAL)
    return 0 if not missing else 1


if __name__ == "__main__":
    raise SystemExit(main())
