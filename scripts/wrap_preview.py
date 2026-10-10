#!/usr/bin/env python3
"""Personalised wrapping paper — pet faces tiled in a repeating pattern.

    python3 scripts/wrap_preview.py --photo data/productimg/prod/prod-hero.png \\
        --size sheet --bg berry --out data/productimg/wrap

0 credits. PIL only. Print-area px come from Prodigi product lookup
(backend/prodigi.py print_area) — sheet 2952x4133, large 4429x5314,
roll 4133x5905. Artwork uploads to Prodigi as the order asset; the
720px shop tile stays with backend/mockup.py shape "paper".
"""
from __future__ import annotations

import argparse
import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SRC = ROOT / "data" / "productimg" / "prod" / "prod-hero.png"
OUT = ROOT / "data" / "productimg" / "wrap"

# Prodigi print-area resolutions (verified live 2026-10-10)
SIZES = {
    "sheet": (2952, 4133),    # WRAP-1-50X70  single 50x70cm
    "large": (4429, 5314),    # WRAP-1-75X90  single 75x90cm
    "roll": (4133, 5905),     # WRAP-ROL-70X100 70cm x 1m roll
    # Printify placeholder px (~300dpi) — render this, downscale for Prodigi.
    "sheet300": (5906, 8268),  # blueprint 848 variant 76531 20x28in
}

BGS = {
    "berry": {"bg": (158, 26, 38), "accent": (250, 244, 232), "dot": (212, 175, 55)},
    "forest": {"bg": (32, 84, 62), "accent": (250, 246, 236), "dot": (212, 175, 55)},
    "cream": {"bg": (250, 246, 236), "accent": (158, 26, 38), "dot": (32, 84, 62)},
}


def load_src(path: Path, zoom: float = 1.0) -> Image.Image:
    im = Image.open(path)
    if im.mode in ("RGBA", "LA") or (im.mode == "P" and "transparency" in im.info):
        im = im.convert("RGBA")
        flat = Image.new("RGB", im.size, (250, 250, 248))
        flat.paste(im, (0, 0), im)
        im = flat
    else:
        im = im.convert("RGB")
    side = min(im.size)
    im = im.crop(((im.width - side) // 2, (im.height - side) // 2,
                    (im.width + side) // 2, (im.height + side) // 2))
    if zoom > 1.0:
        # tighten on the subject — mesh stills ship with wide white margins
        z = min(side, int(side / zoom))
        im = im.crop(((side - z) // 2, (side - z) // 2,
                      (side + z) // 2, (side + z) // 2))
    return im


def circle(im: Image.Image, size: int) -> Image.Image:
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).ellipse([0, 0, size, size], fill=255)
    out = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    out.paste(im.resize((size, size), Image.LANCZOS), (0, 0), mask)
    return out


def star(d: ImageDraw.ImageDraw, cx: int, cy: int, r: int, fill) -> None:
    pts = []
    for i in range(10):
        ang = -math.pi / 2 + i * math.pi / 5
        rad = r if i % 2 == 0 else r * 0.45
        pts.append((cx + rad * math.cos(ang), cy + rad * math.sin(ang)))
    d.polygon(pts, fill=fill)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--photo", default=str(DEFAULT_SRC))
    ap.add_argument("--size", default="sheet", choices=list(SIZES))
    ap.add_argument("--bg", default="berry", choices=list(BGS))
    ap.add_argument("--out", default=str(OUT))
    ap.add_argument("--cols", type=int, default=6,
                    help="pet faces across (rows follow aspect)")
    ap.add_argument("--zoom", type=float, default=1.6,
                    help="subject tighten (mesh stills have wide margins; photos ~1.0)")
    ap.add_argument("--face", default="",
                    help="face box 'x,y,w,h' in source px — medallions centre on"
                         " the face instead of the frame (wrapping paper looks"
                         " for the 'face' tag).")
    ap.add_argument("--face-expand", type=float, default=2.8,
                    help="head+shoulders window as a multiple of face size")
    args = ap.parse_args()

    pal = BGS[args.bg]
    w, h = SIZES[args.size]
    src = load_src(Path(args.photo), zoom=1.0)  # keep full frame for face math
    if args.face:
        try:
            fx, fy, fw, fh = (float(v) for v in args.face.split(","))
        except ValueError:
            raise SystemExit("--face must be 'x,y,w,h'")
        # scale box from original px into the square-cropped src
        side = min(Image.open(Path(args.photo)).size)
        ox = (Image.open(Path(args.photo)).width - side) // 2
        oy = (Image.open(Path(args.photo)).height - side) // 2
        cx, cy = fx - ox + fw / 2, fy - oy + fh / 2
        win = max(fw, fh) * args.face_expand
        src = src.crop((int(cx - win / 2), int(cy - win / 2),
                        int(cx + win / 2), int(cy + win / 2)))
    elif args.zoom > 1.0:
        side = min(src.size)
        z = min(side, int(side / args.zoom))
        src = src.crop(((side - z) // 2, (side - z) // 2,
                        (side + z) // 2, (side + z) // 2))

    img = Image.new("RGB", (w, h), pal["bg"])
    d = ImageDraw.Draw(img, "RGBA")

    cell = w // args.cols
    face = int(cell * 0.62)
    rows = h // cell + 1
    medallion = circle(src, face)

    for r in range(rows):
        for c in range(args.cols):
            # half-drop repeat so the pattern tiles without obvious grid
            x = c * cell + (cell // 2 if r % 2 else 0)
            y = r * cell + cell // 2
            img.paste(medallion, (x - face // 2, y - face // 2), medallion)
            # accent star in the gaps
            sx = x + cell // 2
            sy = y + cell // 2
            if sx < w and sy < h:
                star(d, sx, sy, max(8, cell // 12), pal["dot"][:3] + (255,))

    outdir = Path(args.out)
    outdir.mkdir(parents=True, exist_ok=True)
    stem = Path(args.photo).stem
    full = outdir / f"wrap-{args.bg}-{args.size}-{stem}.png"
    img.save(full, "PNG", optimize=True)

    # 720px Etsy hero slot + shop preview
    hero = img.copy()
    hero.thumbnail((1200, 1200), Image.LANCZOS)
    hero_path = outdir / f"wrap-{args.bg}-{args.size}-{stem}-hero.jpg"
    hero.convert("RGB").save(hero_path, "JPEG", quality=88)

    print(f"full {full} {w}x{h}")
    print(f"hero {hero_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
