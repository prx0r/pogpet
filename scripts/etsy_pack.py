#!/usr/bin/env python3
"""P0 Etsy pack — copy 2000px listing stills into public /img/etsy/.

    python3 scripts/etsy_pack.py

Sources (after 2000px Blender passes):
  data/marketing/mkt-*.png          ornament marketing set
  data/marketing/kc-*.png           keychain set
  data/marketing/brick/prod-*.png   brick exact set

Writes:
  data/productimg/etsy/   local mirror + public /img/etsy/ via bridge
Optionally stamps a light scale caption on hero shots.
Zero Meshy credits.
"""
from __future__ import annotations

import shutil
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
MARKETING = ROOT / "data" / "marketing"
LOCAL = ROOT / "data" / "productimg" / "etsy"
PUBLIC = ROOT / "data" / "productimg" / "etsy"

# dest name -> list of acceptable sources (first existing wins)
PACK: dict[str, list[str]] = {
    # ornament — marketing set (printed tree hook prop allowed on hang shots)
    "etsy-orn-hero.png": ["mkt-hero.png", "ornament/prod-hero.png", "prod-hero.png"],
    "etsy-orn-front.png": ["mkt-front.png", "ornament/prod-front.png", "prod-front.png"],
    "etsy-orn-side.png": ["mkt-left.png", "ornament/prod-side.png", "prod-side.png"],
    "etsy-orn-back.png": ["mkt-back.png", "ornament/prod-back.png", "prod-back.png"],
    "etsy-orn-hang.png": ["mkt-hang.png", "mkt-hang-side.png", "ornament/prod-loop.png"],
    "etsy-orn-loop-detail.png": ["mkt-hook-close.png", "mkt-hook-side.png", "ornament/prod-loop.png", "prod-loop.png"],
    # keychain
    "etsy-kc-hero.png": ["kc-hero.png", "keychain/prod-hero.png"],
    "etsy-kc-front.png": ["kc-front.png", "keychain/prod-front.png"],
    "etsy-kc-back.png": ["kc-back.png", "keychain/prod-back.png"],
    "etsy-kc-side.png": ["kc-left.png", "kc-side.png", "keychain/prod-side.png"],
    "etsy-kc-ring-detail.png": ["kc-ring-close.png", "kc-ring-side.png", "keychain/prod-loop.png"],
    "etsy-kc-ring-side.png": ["kc-ring-side.png", "keychain/prod-loop.png"],
    # brick (exact — no props)
    "etsy-brick-hero.png": ["brick/prod-hero.png"],
    "etsy-brick-front.png": ["brick/prod-front.png"],
    "etsy-brick-side.png": ["brick/prod-side.png"],
    "etsy-brick-back.png": ["brick/prod-back.png"],
    "etsy-brick-loop-detail.png": ["brick/prod-loop.png"],
}

CAPTIONS = {
    "etsy-orn-hero.png": "ornament · ~80 mm · printed loop",
    "etsy-kc-hero.png": "keychain · printed ring · no metal",
    "etsy-brick-hero.png": "brick figure · ~75 mm",
}

MIN_PX = 1800


def stamp_caption(path: Path, text: str) -> None:
    im = Image.open(path).convert("RGB")
    draw = ImageDraw.Draw(im)
    w, h = im.size
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
    if font:
        bbox = draw.textbbox((0, 0), text, font=font)
        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
        draw.text(((w - tw) // 2, h - bar_h + (bar_h - th) // 2), text,
                  fill=(244, 241, 234), font=font)
    else:
        draw.text((w // 2 - 40, h - bar_h + 8), text, fill=(244, 241, 234))
    im.save(path, "PNG", optimize=True)


def find_src(candidates: list[str]) -> Path | None:
    for rel in candidates:
        p = MARKETING / rel
        if p.exists() and p.stat().st_size > 0:
            return p
    return None


def main() -> int:
    LOCAL.mkdir(parents=True, exist_ok=True)
    PUBLIC.mkdir(parents=True, exist_ok=True)
    missing = []
    copied = []
    for dest_name, candidates in PACK.items():
        src = find_src(candidates)
        if src is None:
            missing.append(f"{dest_name} <- {candidates[0]}")
            continue
        im = Image.open(src)
        if im.size[0] < MIN_PX:
            print(f"SKIP {src.name}: {im.size} (need ~{MIN_PX}px)")
            missing.append(f"{src.name} ({im.size})")
            continue
        for dest_dir in (LOCAL, PUBLIC):
            dest_dir.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dest_dir / dest_name)
        if dest_name in CAPTIONS:
            stamp_caption(PUBLIC / dest_name, CAPTIONS[dest_name])
        copied.append((dest_name, im.size, (PUBLIC / dest_name).stat().st_size))
        print(f"OK {dest_name:32} {im.size[0]}px  {(PUBLIC / dest_name).stat().st_size // 1024}KB  <- {src.relative_to(MARKETING)}")

    # zip pack for one-click Etsy upload
    import zipfile
    zpath = LOCAL / "oddhobb-etsy-listing-pack.zip"
    with zipfile.ZipFile(zpath, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for dest_name, _, _ in copied:
            zf.write(PUBLIC / dest_name, arcname=dest_name)
    print(f"\nzip: {zpath} ({zpath.stat().st_size // 1024}KB, {len(copied)} files)")
    print(f"pack: {len(copied)} files -> {PUBLIC}")
    if missing:
        print("MISSING:", "; ".join(missing))
    return 0 if not missing else 1


if __name__ == "__main__":
    raise SystemExit(main())
