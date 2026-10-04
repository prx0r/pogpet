#!/usr/bin/env python3
"""Personal card preview — mesh still + greeting text on a card mockup.

    python3 scripts/xmas_card_preview.py --template merry_xmas --size 5x7 \
        --name Buster [--photo path.jpg] [--out data/productimg/prod]

0 Meshy credits. Uses existing dog hero still OR a real uploaded photo.
"""
from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance, ImageFont

ROOT = Path(__file__).resolve().parent.parent
HERO = ROOT / "data" / "productimg" / "prod" / "prod-hero.png"
OUT = ROOT / "data" / "productimg" / "prod"

SIZES = {
    "A6": (1050, 1480),   # 105×148mm @10dpi-ish working px
    "5x7": (1270, 1780),
    "A5": (1480, 2100),
}

TEMPLATES = {
    "merry_xmas": {"msg": "Merry Xmas", "sub": "from the whole pack", "bg": (250, 248, 244), "accent": (160, 30, 40)},
    "happy_holidays": {"msg": "Happy Holidays", "sub": "love from us", "bg": (248, 246, 240), "accent": (40, 90, 60)},
    "thank_you": {"msg": "Thank you", "sub": "you're the best", "bg": (250, 248, 244), "accent": (180, 120, 40)},
    "happy_birthday": {"msg": "Happy Birthday", "sub": "woof woof", "bg": (250, 247, 250), "accent": (120, 40, 140)},
}


def font(size: int, bold: bool = True):
    paths = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSerif-Bold.ttf",
    ]
    for fp in paths:
        if Path(fp).exists():
            try:
                return ImageFont.truetype(fp, size)
            except OSError:
                pass
    return ImageFont.load_default()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--template", default="merry_xmas", choices=list(TEMPLATES))
    ap.add_argument("--size", default="5x7", choices=list(SIZES))
    ap.add_argument("--name", default="Buster")
    ap.add_argument("--photo", default="", help="optional real PNG/JPEG (overrides mesh still)")
    ap.add_argument("--out", default=str(OUT))
    ap.add_argument("--message", default="", help="override greeting text")
    args = ap.parse_args()

    tpl = TEMPLATES[args.template]
    w, h = SIZES[args.size]
    outdir = Path(args.out)
    outdir.mkdir(parents=True, exist_ok=True)

    card = Image.new("RGB", (w, h), tpl["bg"])
    d = ImageDraw.Draw(card)

    # border
    m = int(min(w, h) * 0.04)
    d.rectangle([m, m, w - m, h - m], outline=tpl["accent"], width=6)

    # image panel
    img_h = int(h * 0.58)
    img_w = int(w * 0.86)
    ix, iy = (w - img_w) // 2, m + int(h * 0.06)
    panel = Image.new("RGB", (img_w, img_h), (255, 255, 255))
    if args.photo and Path(args.photo).exists():
        src = Image.open(args.photo).convert("RGB")
    else:
        src = Image.open(HERO).convert("RGB")
    src = ImageEnhance.Color(src).enhance(1.08)
    # cover-fit into panel
    scale = max(img_w / src.width, img_h / src.height)
    src = src.resize((int(src.width * scale), int(src.height * scale)), Image.Resampling.LANCZOS)
    left = (src.width - img_w) // 2
    top = (src.height - img_h) // 2
    panel = src.crop((left, top, left + img_w, top + img_h))
    card.paste(panel, (ix, iy))
    d = ImageDraw.Draw(card)
    d.rectangle([ix, iy, ix + img_w, iy + img_h], outline=(220, 210, 200), width=3)

    # greeting
    msg = args.message or tpl["msg"]
    f_msg = font(int(h * 0.07))
    f_sub = font(int(h * 0.03), bold=False)
    f_name = font(int(h * 0.035))
    ty = iy + img_h + int(h * 0.05)
    # centre text
    bbox = d.textbbox((0, 0), msg, font=f_msg)
    d.text(((w - (bbox[2] - bbox[0])) // 2, ty), msg, fill=tpl["accent"], font=f_msg)
    ty2 = ty + int(h * 0.08)
    sub = tpl["sub"].replace("[pet name]", args.name)
    bbox = d.textbbox((0, 0), sub, font=f_sub)
    d.text(((w - (bbox[2] - bbox[0])) // 2, ty2), sub, fill=(80, 80, 80), font=f_sub)
    if args.name:
        line = "— " + args.name + " —"
        bbox = d.textbbox((0, 0), line, font=f_name)
        d.text(((w - (bbox[2] - bbox[0])) // 2, ty2 + int(h * 0.045)), line, fill=(40, 40, 40), font=f_name)

    dest = outdir / f"card-{args.template}-{args.size}.png"
    card.save(dest, "PNG")
    print("wrote", dest, dest.stat().st_size)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
