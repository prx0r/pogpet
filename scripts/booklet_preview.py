#!/usr/bin/env python3
"""Personalised booklet proof — unique print per order (the warehouse-print
question answered in miniature).

    python3 scripts/booklet_preview.py --title "Chris's Charm Lab" \\
        --message "Made for Chris" --photo data/tmp/xxx.jpg --out data/productimg/booklets/

PIL only, 0 credits. A5 portrait pages (1748x2480 @210dpi-ish working px):
cover + one photo page per --photo (step caption via --steps) + back.
Real warehouses print the PDF; the point is every order CAN be unique.
"""
from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "productimg" / "booklets"
W, H = 1240, 1754  # A5-ish working px
BG = (250, 246, 236)
INK = (30, 26, 22)
ACCENT = (158, 26, 38)


def font(size: int):
    for cand in ("/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf",
                 "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"):
        try:
            return ImageFont.truetype(cand, size)
        except OSError:
            continue
    return ImageFont.load_default()


def fit(im: Image.Image, box) -> Image.Image:
    w, h = box[2] - box[0], box[3] - box[1]
    r = min(w / im.width, h / im.height)
    im = im.resize((max(1, int(im.width * r)), max(1, int(im.height * r))),
                   Image.LANCZOS)
    page = Image.new("RGB", (w, h), BG)
    page.paste(im, ((w - im.width) // 2, (h - im.height) // 2))
    return page


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--title", required=True)
    ap.add_argument("--message", default="")
    ap.add_argument("--photo", action="append", default=[])
    ap.add_argument("--step", action="append", default=[])
    ap.add_argument("--out", default=str(OUT))
    args = ap.parse_args()

    pages = []
    cover = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(cover)
    d.text([W // 2, 620], args.title, font=font(96), fill=ACCENT, anchor="mm")
    d.text([W // 2, 780], "a personalised project", font=font(48),
           fill=INK, anchor="mm")
    pages.append(cover)

    for i, ph in enumerate(args.photo):
        try:
            im = Image.open(ph).convert("RGB")
        except Exception as e:
            print(f"skip {ph}: {e}")
            continue
        page = Image.new("RGB", (W, H), BG)
        page.paste(fit(im, (120, 140, W - 120, 1180)), (120, 140))
        dd = ImageDraw.Draw(page)
        caption = args.step[i] if i < len(args.step) else f"step {i + 1}"
        dd.text([W // 2, 1400], caption, font=font(56), fill=INK, anchor="mm")
        pages.append(page)

    back = Image.new("RGB", (W, H), BG)
    dd = ImageDraw.Draw(back)
    dd.text([W // 2, H // 2 - 40], args.message or "made with oddhobb",
            font=font(64), fill=ACCENT, anchor="mm")
    dd.text([W // 2, H // 2 + 80], "oddhobb.com", font=font(44),
            fill=INK, anchor="mm")
    pages.append(back)

    outdir = Path(args.out)
    outdir.mkdir(parents=True, exist_ok=True)
    slug = "".join(c if c.isalnum() else "-" for c in args.title.lower())[:40]
    dest = outdir / f"booklet-{slug}.pdf"
    pages[0].save(dest, "PDF", save_all=True, append_images=pages[1:])
    print(f"wrote {dest} ({len(pages)} pages, {dest.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
