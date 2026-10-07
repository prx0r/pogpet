"""composite2d — LIVE renderer (cardgen.md §10–11).

Deterministic layers only: photo/cutout + template palette + REAL
typography rendered by us. AI plates (identity_image) slot underneath later;
generated pixels never carry words.
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


def _font(size: int):
    for p in ("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
              "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"):
        if Path(p).exists():
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()


def render_card(*, photo_path: str | None, headline: str, subheadline: str = "",
                bg: str = "#f8f1e6", ink: str = "#22221d", accent: str = "#a64332",
                size: tuple[int, int] = (1500, 2100)) -> Image.Image:
    """5x7 @300dpi card front. Photo up top, slabs of real type below."""
    img = Image.new("RGB", size, bg)
    d = ImageDraw.Draw(img)
    y = 120
    if photo_path and Path(photo_path).exists():
        ph = Image.open(photo_path).convert("RGB")
        ph.thumbnail((size[0] - 240, 900))
        img.paste(ph, ((size[0] - ph.width) // 2, y))
        y += ph.height + 80
    d.text((120, y), headline[:42], font=_font(72), fill=ink)
    y += 130
    if subheadline:
        d.text((120, y), subheadline[:90], font=_font(40), fill=accent)
        y += 120
    d.rectangle([120, size[1] - 160, size[0] - 120, size[1] - 150], fill=accent)
    return img
