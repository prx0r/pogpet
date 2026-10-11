"""Photo-grid birthday card: lettering + age + the best photos, on white.

A template family inside the existing card stack (template id "photo_grid" in
card_scenes.TEMPLATES). card_scenes.front/inside/back dispatch here, so
preview, spread, export, the Prodigi compositor and checkout run unchanged.

No generation at render time. The "Happy Birthday" header is one of six
pre-made transparent plates (assets/card-art/photo-grid/hb_<style>.png, made
once and spell-checked by eye); the age ordinal and the name are typeset from
bundled OFL fonts, so any age or name works without new art.

Geometry is in TRIM pixels of a 5x7 at 300 dpi (1500x2100). A canvas with the
trim aspect is all trim (previews). The Prodigi CLASSIC-GRE-FEDR-7X5-BLA panel
is 1530x2160 (trim + bleed): the trim sits centred and the bleed is plain white
paper, so nothing that matters can be trimmed. Every element sits inside a
90 px (7.6 mm) white margin, the same on all four sides.
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps

ROOT = Path(__file__).resolve().parent.parent
PLATES = ROOT / "assets" / "card-art" / "photo-grid"
FONTS = ROOT / "assets" / "fonts"

TRIM = (1500, 2100)
PRODIGI_PANEL = (1530, 2160)          # one panel of the 6120x2160 print area
MARGIN = 90
GUTTER = 24
PAPER = "#ffffff"
GRIDS = (1, 4, 6, 10)

# header height per grid (the photos take the rest, margins stay equal)
_HEADER = {1: 430, 4: 560, 6: 560, 10: 560}


def _unit_grid(cols: int, rows: int, top: int, height: int):
    uw = (TRIM[0] - 2 * MARGIN - (cols - 1) * GUTTER) / cols
    uh = (height - (rows - 1) * GUTTER) / rows

    def cell(c, r, cw=1, rh=1):
        return (MARGIN + c * (uw + GUTTER), top + r * (uh + GUTTER),
                cw * uw + (cw - 1) * GUTTER, rh * uh + (rh - 1) * GUTTER)
    return cell


def layout(n: int) -> dict:
    """{"header": (x,y,w,h), "cells": [(x,y,w,h)...]} in trim px. cells[0] is the hero."""
    if n not in GRIDS:
        raise ValueError(f"photo grid must be one of {GRIDS}")
    hh = _HEADER[n]
    top = MARGIN + hh + 40
    height = TRIM[1] - MARGIN - top
    header = (MARGIN, MARGIN, TRIM[0] - 2 * MARGIN, hh)
    if n == 1:
        cells = [(MARGIN, top, TRIM[0] - 2 * MARGIN, height)]
    elif n == 4:
        g = _unit_grid(2, 2, top, height)
        cells = [g(0, 0), g(1, 0), g(0, 1), g(1, 1)]
    elif n == 6:
        g = _unit_grid(3, 3, top, height)
        cells = [g(0, 0, 2, 2), g(2, 0), g(2, 1), g(0, 2), g(1, 2), g(2, 2)]
    else:  # 10: hero 2x2, three wide 2x1, six singles on a 4x4 unit grid
        g = _unit_grid(4, 4, top, height)
        cells = [g(0, 0, 2, 2), g(2, 0, 2, 1), g(2, 1), g(3, 1),
                 g(0, 2), g(1, 2), g(2, 2, 2, 1),
                 g(0, 3, 2, 1), g(2, 3), g(3, 3)]
    return {"header": header, "cells": cells}


def cells_for(n: int) -> list:
    """Cells as photo_select wants them: aspect (w/h), print px tall, hero flag."""
    out = []
    for i, (_x, _y, w, h) in enumerate(layout(n)["cells"]):
        out.append({"aspect": w / h, "px_h": h, "hero": i == 0, "rect": [_x, _y, w, h],
                    "face_frac": 0.30 if n == 1 else (0.30 if i == 0 else 0.34)})
    return out


# ── styles: plate + typeset fonts + accents (6 max) ─────────────────────
STYLES = {
    "classic": {"label": "Classic gold", "plate": "hb_classic.png",
                "age_font": "Fraunces-SemiBold.ttf", "age_fill": ["#A8842F"],
                "name_font": "Fraunces-SemiBold.ttf", "name_fill": "#6E5B31", "name_caps": True,
                "name_track": 0.22, "rules": "#C9A962", "radius": 0, "msg_font": "fraunces"},
    "bold": {"label": "Bold modern", "plate": "hb_bold.png",
             "age_font": "Anton-Regular.ttf", "age_fill": ["#1A1A1A"], "suffix_fill": "#E8553D",
             "name_font": "Anton-Regular.ttf", "name_fill": "#E8553D", "name_caps": True,
             "name_track": 0.12, "rules": None, "radius": 0, "msg_font": "inter_bold"},
    "playful": {"label": "Playful hand-lettered", "plate": "hb_playful.png",
                "age_font": "Pacifico-Regular.ttf", "age_fill": ["#12988F"],
                "name_font": "Pacifico-Regular.ttf", "name_fill": "#E8553D", "name_caps": False,
                "name_track": 0.0, "rules": None, "radius": 26, "msg_font": "caveat"},
    "botanical": {"label": "Botanical", "plate": "hb_botanical.png",
                  "age_font": "Fraunces-SemiBold.ttf", "age_fill": ["#B76E79"],
                  "name_font": "GreatVibes-Regular.ttf", "name_fill": "#9C5A64", "name_caps": False,
                  "name_track": 0.0, "rules": None, "radius": 14, "msg_font": "fraunces"},
    "sporty": {"label": "Sporty varsity", "plate": "hb_sporty.png",
               "age_font": "Graduate-Regular.ttf", "age_fill": ["#1F3A68"], "suffix_fill": "#C8102E",
               "name_font": "Graduate-Regular.ttf", "name_fill": "#C8102E", "name_caps": True,
               "name_track": 0.10, "rules": None, "radius": 0, "msg_font": "inter_bold"},
    "kids": {"label": "Kids", "plate": "hb_kids.png",
             "age_font": "LuckiestGuy-Regular.ttf",
             "age_fill": ["#E53935", "#FB8C00", "#43A047", "#1E88E5", "#8E24AA"],
             "name_font": "LuckiestGuy-Regular.ttf", "name_fill": "#1E88E5", "name_caps": True,
             "name_track": 0.06, "rules": None, "radius": 30, "msg_font": "inter_bold"},
}
STYLE_IDS = tuple(STYLES)

_PLATE_CACHE: dict = {}


def plate(style: str) -> Image.Image:
    name = STYLES[style]["plate"]
    if name not in _PLATE_CACHE:
        _PLATE_CACHE[name] = Image.open(PLATES / name).convert("RGBA")
    return _PLATE_CACHE[name]


def _font(name: str, size: float):
    try:
        return ImageFont.truetype(str(FONTS / name), max(8, int(size)))
    except OSError:
        return ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", max(8, int(size)))


def ordinal(n: int) -> tuple[str, str]:
    n = int(n)
    suf = "th" if 10 <= n % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return str(n), suf


def _text_w(font, s: str, track: float = 0.0) -> float:
    if not s:
        return 0.0
    if not track:
        return font.getlength(s)
    return sum(font.getlength(ch) for ch in s) + track * font.size * (len(s) - 1)


def _draw_tracked(d, xy, s, font, fill, track=0.0):
    x, y = xy
    if not track:
        d.text((x, y), s, font=font, fill=fill, anchor="ls")
        return
    for ch in s:
        d.text((x, y), ch, font=font, fill=fill, anchor="ls")
        x += font.getlength(ch) + track * font.size


def _age_strip(style: str, age: int, max_w: float, size: float) -> Image.Image:
    """'70' + small raised 'th', typeset. Transparent strip sized to its ink."""
    st = STYLES[style]
    num, suf = ordinal(age)
    for s in range(int(size), 20, -4):
        fnum = _font(st["age_font"], s)
        fsuf = _font(st["age_font"], s * 0.42)
        w = _text_w(fnum, num) + s * 0.05 + _text_w(fsuf, suf)
        if w <= max_w:
            break
    asc, desc = fnum.getmetrics()
    img = Image.new("RGBA", (int(w + s * 0.2), int(asc + desc + s * 0.1)), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    x, base = s * 0.1, asc
    fills = st["age_fill"]
    for i, ch in enumerate(num):
        d.text((x, base), ch, font=fnum, fill=fills[i % len(fills)], anchor="ls")
        x += fnum.getlength(ch)
    x += s * 0.05
    cap_top = base + fnum.getbbox("8", anchor="ls")[1]   # bbox top is negative from the baseline
    sfill = st.get("suffix_fill") or fills[-1 if len(fills) > 1 else 0]
    d.text((x, cap_top), suf, font=fsuf, fill=sfill, anchor="lt")
    bb = img.getbbox()
    return img.crop(bb) if bb else img


def _name_strip(style: str, name: str, max_w: float, size: float) -> Image.Image:
    st = STYLES[style]
    s_txt = name.upper() if st["name_caps"] else name
    track = st["name_track"]
    for s in range(int(size), 14, -2):
        f = _font(st["name_font"], s)
        w = _text_w(f, s_txt, track)
        if w <= max_w:
            break
    asc, desc = f.getmetrics()
    pad = int(s * 0.6)
    img = Image.new("RGBA", (int(w + 2 * pad), int(asc + desc + pad)), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    _draw_tracked(d, (pad, asc + pad // 4), s_txt, f, st["name_fill"], track)
    bb = img.getbbox()
    img = img.crop(bb) if bb else img
    if st.get("rules") and img.width < max_w * 0.7:
        # classic: hairline gold rules either side of the name
        rl = min(160.0, (max_w - img.width) / 2 - 30)
        out = Image.new("RGBA", (int(img.width + 2 * (rl + 30)), img.height), (0, 0, 0, 0))
        out.alpha_composite(img, (int(rl + 30), 0))
        d = ImageDraw.Draw(out)
        y = img.height // 2
        lw = max(2, round(s * 0.05))
        d.line((0, y, rl, y), fill=st["rules"], width=lw)
        d.line((out.width - rl, y, out.width, y), fill=st["rules"], width=lw)
        img = out
    return img


def header_image(style: str, age: int, name: str, size: tuple) -> Image.Image:
    """The header block (transparent) at trim size `size` (w, h)."""
    hw, hh = size
    p = plate(style)
    parts = []
    age_h = hh * 0.30 if age else 0
    name_h = hh * 0.19 if name else 0
    plate_h = hh - age_h - name_h - hh * 0.06 * (bool(age) + bool(name))
    if age:
        parts.append(_age_strip(style, age, hw * 0.6, age_h * 1.25))
    r = min(hw * 0.92 / p.width, plate_h / p.height)
    parts.append(p.resize((max(1, round(p.width * r)), max(1, round(p.height * r))), Image.Resampling.LANCZOS))
    if name:
        parts.append(_name_strip(style, name, hw * 0.9, name_h * 1.25))
    gap = hh * 0.05
    total = sum(x.height for x in parts) + gap * (len(parts) - 1)
    k = min(1.0, hh / total)
    out = Image.new("RGBA", (hw, hh), (0, 0, 0, 0))
    y = (hh - total * k) / 2
    for x in parts:
        if k < 1.0:
            x = x.resize((max(1, round(x.width * k)), max(1, round(x.height * k))), Image.Resampling.LANCZOS)
        out.alpha_composite(x, (round((hw - x.width) / 2), round(y)))
        y += x.height + gap * k
    return out


def trim_box(width: int, height: int) -> tuple:
    """(x, y, w, h) of the trim inside a canvas. Trim-aspect canvas = all trim;
    otherwise the canvas is trim + bleed in Prodigi panel proportions."""
    if abs(width / height - TRIM[0] / TRIM[1]) < 0.004:
        return 0, 0, width, height
    tw = round(width * TRIM[0] / PRODIGI_PANEL[0])
    th = round(height * TRIM[1] / PRODIGI_PANEL[1])
    return (width - tw) // 2, (height - th) // 2, tw, th


def _cell_photo(img: Image.Image, crop: list, size: tuple, radius: int) -> Image.Image:
    from backend.card_scenes import cropped
    src = cropped(img, crop).convert("RGB")
    tile = ImageOps.fit(src, size, method=Image.Resampling.LANCZOS, centering=(0.5, 0.5)).convert("RGBA")
    if radius:
        m = Image.new("L", size, 0)
        ImageDraw.Draw(m).rounded_rectangle((0, 0, size[0] - 1, size[1] - 1), radius=radius, fill=255)
        tile.putalpha(m)
    return tile


def _pale_edges(tile: Image.Image) -> bool:
    g = tile.convert("L")
    w, h = g.size
    k = max(2, min(w, h) // 40)
    strips = [g.crop((0, 0, w, k)), g.crop((0, h - k, w, h)), g.crop((0, 0, k, h)), g.crop((w - k, 0, w, h))]
    import numpy as np
    pale = sum(float((np.asarray(st) > 238).mean()) for st in strips) / 4
    return pale > 0.35


def front(design: dict, assets: dict, width: int = 720, height: int | None = None,
          progress: float = 1.0) -> Image.Image:
    height = height or round(width * TRIM[1] / TRIM[0])
    tx, ty, tw, th = trim_box(width, height)
    s = tw / TRIM[0]
    n = int(design.get("grid") or len(design["photos"]))
    style = design.get("grid_style") if design.get("grid_style") in STYLES else "classic"
    lay = layout(n)
    card = Image.new("RGBA", (width, height), PAPER)
    hx, hy, hw, hh = lay["header"]
    head = header_image(style, int(design.get("age") or 0), design.get("recipient", ""),
                        (max(1, round(hw * s)), max(1, round(hh * s))))
    card.alpha_composite(head, (tx + round(hx * s), ty + round(hy * s)))
    radius = round(STYLES[style]["radius"] * s)
    for i, (slot, (cx, cy, cw, ch)) in enumerate(zip(design["photos"], lay["cells"])):
        reveal = max(0.0, min(1.0, progress * 2.2 - i * 0.08))
        if reveal <= 0:
            continue
        x0, y0 = tx + round(cx * s), ty + round(cy * s)
        x1, y1 = tx + round((cx + cw) * s), ty + round((cy + ch) * s)
        tile = _cell_photo(assets[slot["photo_id"]], slot["crop"], (x1 - x0, y1 - y0), radius)
        if _pale_edges(tile):
            # a photo with a white background would melt into the paper: hairline keeps the grid
            ImageDraw.Draw(tile).rounded_rectangle((0, 0, tile.width - 1, tile.height - 1), radius=radius,
                                                   outline="#dcdcdc", width=max(1, round(3 * s)))
        if reveal < 1.0:
            tile.putalpha(tile.getchannel("A").point(lambda v: round(v * reveal)))
        card.alpha_composite(tile, (x0, y0))
    return card.convert("RGB")


_MSG_FONT = {"classic": ("Fraunces-SemiBold.ttf", 1.0), "bold": ("Inter-Bold.ttf", 0.92),
             "playful": ("Caveat-SemiBold.ttf", 1.35), "botanical": ("Fraunces-SemiBold.ttf", 1.0),
             "sporty": ("Inter-Bold.ttf", 0.92), "kids": ("Inter-Bold.ttf", 0.95)}


def _fit(draw, text: str, font_file: str, w: float, h: float, size: float):
    """Largest size (<= size) at which the words wrap inside w x h. (font, lines, line height)."""
    for fs in range(int(size), 9, -1):
        f = _font(font_file, fs)
        lines = []
        for para in str(text or "").split("\n"):
            line = ""
            for word in para.split():
                cand = (line + " " + word).strip()
                if line and draw.textlength(cand, font=f) > w:
                    lines.append(line)
                    line = word
                else:
                    line = cand
            lines.append(line)
        lh = fs * 1.32
        if lh * len(lines) <= h and all(draw.textlength(x, font=f) <= w for x in lines):
            return f, lines, lh
    from backend.card_scenes import TextOverflow
    raise TextOverflow("Text does not fit this card. Shorten it.")


def inside(design: dict, width: int = 720, height: int | None = None, assets=None) -> Image.Image:
    """White spread: blank left page; on the right page the message, a small rule in
    the lettering colour and the handwritten signature, centred as one block.
    The message face follows the lettering style. Brand lives on the back only."""
    height = height or round(width * TRIM[1] / (2 * TRIM[0]))   # a spread is two pages wide
    img = Image.new("RGB", (width, height), PAPER)
    d = ImageDraw.Draw(img)
    style = design.get("grid_style") if design.get("grid_style") in STYLES else "classic"
    right = ((design.get("inside") or {}).get("right")) or {}
    msg = right.get("message", design.get("inside_message", "")) or ""
    sig = design.get("sender", "") or ""
    page_w = width / 2
    mw, mh = page_w * 0.74, height * 0.46
    ffile, scale = _MSG_FONT[style]
    f, lines, lh = _fit(d, msg, ffile, mw, mh, page_w * 0.062 * scale)
    sf = gap = None
    block = lh * len(lines)
    if sig:
        sf, slines, slh = _fit(d, sig, "Caveat-SemiBold.ttf", mw * 0.8, height * 0.12, page_w * 0.075)
        gap = height * 0.07
        block += gap + slh * len(slines)
    cx = page_w + page_w / 2
    y = (height - block) / 2
    for line in lines:
        d.text((cx, y), line, font=f, fill="#23201b", anchor="ma")
        y += lh
    if sig:
        rule = STYLES[style]["name_fill"]
        ry = y + gap * 0.42
        d.line((cx - page_w * 0.05, ry, cx + page_w * 0.05, ry), fill=rule, width=max(1, round(width / 700)))
        y += gap
        for line in slines:
            d.text((cx, y), line, font=sf, fill="#3a3a32", anchor="ma")
            y += slh
    return img
