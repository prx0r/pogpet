"""composite2d — LIVE renderer (cardgen.md §10–11).

Deterministic layers only: photo/cutout + template palette + REAL
typography rendered by us. AI plates (identity_image) slot underneath later;
generated pixels never carry words.

render_from_manifest() is the real template engine: regions, safe area and
bleed come from the manifest + print contract, and every geometric claim is
measured (textbbox, photo placement, canvas dims) — QC fails loudly.
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps

# Per-style looks for the viral library. The manifest engine
# (render_from_manifest) stays canonical for print; these dress previews.
PALETTES = {
    "xmasaisketch": ("#fffefb", "#171717", "#171717"),
    "comicstory": ("#fff9e7", "#171717", "#cf4035"),
    "studioroast": ("#141217", "#fff8e8", "#d6aa55"),
    "sportspresser": ("#0d1a24", "#f5f2e9", "#d4ad55"),
    "newsparody": ("#f4f4f2", "#151515", "#cf2f2f"),
    "cinechaos": ("#1a1412", "#fff2d2", "#c89a45"),
    "screenshottalk": ("#f5f5f2", "#181818", "#4b70e2"),
    "generic": ("#f8f1e6", "#22221d", "#a64332"),
}


def _font(size: int):
    for p in ("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
              "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"):
        if Path(p).exists():
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()


def contract_pixels(contract: dict) -> tuple[int, int, int]:
    """(print_w, print_h, preview_scale): print canvas = trim + bleed @dpi."""
    dpi = int(contract.get("dpi") or 300)
    tw, th = contract["trim_mm"]
    bleed = float(contract.get("bleed_mm") or 0)
    pw = round((tw + 2 * bleed) / 25.4 * dpi)
    ph = round((th + 2 * bleed) / 25.4 * dpi)
    return pw, ph, dpi


def _place(photo: Image.Image, box: tuple[int, int, int, int]) -> Image.Image:
    x0, y0, x1, y1 = box
    w, h = max(1, x1 - x0), max(1, y1 - y0)
    ph = photo.copy().convert("RGB")
    ph.thumbnail((w * 2, h * 2))
    canvas = Image.new("RGB", (w, h), (0, 0, 0))
    canvas.paste(ph.resize((w, h)), (0, 0))
    return canvas


def render_from_manifest(manifest: dict, contract: dict, *,
                         photo_path: str | None, copy: dict,
                         palette: dict | None = None) -> tuple[Image.Image, list[str]]:
    """Returns (print_master_image, gaps). Preview is a downscale of print —
    one render, two artifacts, never divergent."""
    pal = palette or {"bg": "#f4f1ea", "ink": "#141414", "accent": "#8a6a2f"}
    lay = manifest.get("layout") or {}
    pw, ph, dpi = contract_pixels(contract)
    gaps: list[str] = []
    img = Image.new("RGB", (pw, ph), pal["bg"])
    d = ImageDraw.Draw(img)
    # designed backdrop: accent footer band + hairline frame, so the cover
    # reads as artwork with or without a photo slotted in
    band_h = max(8, ph // 28)
    d.rectangle([0, ph - band_h, pw, ph], fill=pal["accent"])
    d.rectangle([24, 24, pw - 24, ph - 24], outline=pal["accent"], width=max(3, pw // 400))

    def region(key: str) -> tuple[int, int, int, int]:
        fx0, fy0, fx1, fy1 = lay.get(key, [0, 0, 1, 1])
        return (round(fx0 * pw), round(fy0 * ph), round(fx1 * pw), round(fy1 * ph))

    if photo_path and Path(photo_path).exists():
        x0, y0, x1, y1 = region("photo")
        ph = Image.open(photo_path).convert("RGB")
        ph = ImageOps.fit(ph, (x1 - x0, y1 - y0), Image.Resampling.LANCZOS,
                          centering=(.5, .35))
        mask = Image.new("L", ph.size, 0)
        ImageDraw.Draw(mask).rounded_rectangle([0, 0, ph.width, ph.height],
                                               radius=min(ph.size) // 10, fill=255)
        img.paste(ph, (x0, y0), mask)
        d.rounded_rectangle([x0 - 6, y0 - 6, x1 + 6, y1 + 6],
                            radius=min(x1 - x0, y1 - y0) // 10,
                            outline=pal["accent"], width=max(3, pw // 400))
    else:
        gaps.append("photo region empty — no subject asset")

    slots = (manifest.get("slots") or {})
    for key in ("headline", "caption", "subheadline"):
        if key not in slots:
            continue
        text = str(copy.get(key) or slots[key].get("default", ""))
        if not text:
            if slots[key].get("required"):
                gaps.append(f"missing required field: {key}")
            continue
        x0, y0, x1, y1 = region(key if key in lay else "caption")
        size = max(12, (y1 - y0) // 2)
        font = _font(size)
        while size > 12:
            bb = d.textbbox((0, 0), text, font=font)
            if bb[2] - bb[0] <= (x1 - x0):
                break
            size -= 4
            font = _font(size)
        else:
            bb = d.textbbox((0, 0), text, font=font)
        if bb[2] - bb[0] > (x1 - x0):
            gaps.append(f"text overflow: {key} wider than its region")
        else:
            fill = pal["ink"] if key == "headline" else pal["accent"]
            d.text((x0, y0), text, font=font, fill=fill)

    # safe-area verification: text regions must sit inside the safe rect
    safe_px = round(float(lay.get("safe_inset_mm", 5)) / 25.4 * dpi)
    if img.width != pw or img.height != ph:
        gaps.append("canvas mismatch vs print contract")
    for key in ("headline", "caption", "subheadline"):
        if key in lay:
            x0, y0, x1, y1 = region(key)
            if x0 < safe_px or y0 < safe_px or x1 > pw - safe_px or y1 > ph - safe_px:
                gaps.append(f"{key} region breaks the safe area")
    return img, gaps


def render_card(*, photo_path: str | None, headline: str, subheadline: str = "",
                bg: str | None = None, ink: str | None = None, accent: str | None = None,
                style_id: str = "generic", template_id: str = "",
                size: tuple[int, int] = (1500, 2100)) -> Image.Image:
    """5x7 @300dpi card front. Style-aware looks per viral family; the generic
    path preserves the original composition."""
    bg0, ink0, accent0 = PALETTES.get(style_id, PALETTES["generic"])
    bg, ink, accent = bg or bg0, ink or ink0, accent or accent0
    img = Image.new("RGB", size, bg)
    d = ImageDraw.Draw(img)
    w, h = size
    if style_id not in ("generic", ""):
        _render_style(d, img, style_id, photo_path, headline, subheadline, w, h)
        return img
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


def _fit(draw, text, box, *, fill, start=76, bold=True, align="left"):
    x, y, w, h = box
    text = str(text or "")
    for fs in range(int(start), 15, -2):
        f = _font(fs)
        lines, line = [], ""
        for word in text.split():
            test = (line + " " + word).strip()
            if line and draw.textlength(test, font=f) > w:
                lines.append(line)
                line = word
            else:
                line = test
        if line:
            lines.append(line)
        lh = fs * 1.22
        if len(lines) * lh <= h:
            for i, row in enumerate(lines):
                xx = x if align != "center" else x + (w - draw.textlength(row, font=f)) / 2
                draw.text((xx, y + i * lh), row, font=f, fill=fill)
            return


def _photo_box(img, path, box, mono=False):
    if not path or not Path(path).exists():
        return
    x, y, w, h = map(int, box)
    ph = Image.open(path).convert("RGB")
    ph = ImageOps.fit(ph, (w, h), Image.Resampling.LANCZOS, centering=(.5, .35))
    if mono:
        ph = ImageOps.autocontrast(ph.convert("L")).convert("RGB")
    img.paste(ph, (x, y))


def _render_style(d, img, style_id, photo_path, headline, subheadline, w, h):
    if style_id in ("xmasaisketch", "original"):
        _photo_box(img, photo_path, (90, 120, w - 180, 1120), mono=True)
        d.rectangle((76, 90, w - 76, 1300), outline=(23, 23, 23), width=5)
        d.line((100, 1400, w - 100, 1400), fill=(23, 23, 23), width=3)
        _fit(d, headline.upper(), (120, 1450, w - 240, 170), fill=(23, 23, 23),
             start=70, align="center")
        _fit(d, subheadline, (150, 1640, w - 300, 260), fill=(23, 23, 23),
             start=48, bold=False, align="center")
    elif style_id == "comicstory":
        _photo_box(img, photo_path, (110, 130, 580, 610), mono=True)
        _fit(d, headline.upper(), (100, 1510, w - 200, 150), fill=(23, 23, 23),
             start=62, align="center")
        _fit(d, subheadline, (120, 1690, w - 240, 250), fill=(207, 64, 53),
             start=42, bold=False, align="center")
    elif style_id == "newsparody":
        d.rectangle((0, 0, w, 210), fill=(207, 47, 47))
        _fit(d, "LIVE  •  ODDHOBB NEWS", (80, 60, w - 160, 100), fill="#fff", start=58)
        _photo_box(img, photo_path, (80, 260, w - 160, 1120))
        d.rectangle((70, 1410, w - 70, 1880), fill="#fff")
        d.rectangle((70, 1410, 320, 1475), fill=(207, 47, 47))
        _fit(d, "BREAKING", (92, 1420, 210, 50), fill="#fff", start=34)
        _fit(d, headline.upper(), (100, 1500, w - 200, 150), fill="#111", start=68)
        _fit(d, subheadline, (100, 1685, w - 200, 160), fill="#333",
             start=40, bold=False)
    elif style_id == "sportspresser":
        _photo_box(img, photo_path, (80, 90, w - 160, 1250))
        d.rectangle((70, 1370, w - 70, 1920), fill="#101318")
        d.rectangle((70, 1370, w - 70, 1390), fill=(212, 173, 85))
        _fit(d, headline.upper(), (110, 1460, w - 220, 160), fill="#fff", start=72)
        _fit(d, subheadline, (110, 1660, w - 220, 180), fill=(212, 173, 85),
             start=44, bold=False)
    elif style_id in ("studioroast", "cinechaos"):
        _photo_box(img, photo_path, (80, 90, w - 160, 1280))
        _fit(d, headline.upper(), (110, 1480, w - 220, 170), fill="#fff8e8",
             start=72, align="center")
        _fit(d, subheadline, (130, 1690, w - 260, 220), fill=(214, 170, 85),
             start=43, bold=False, align="center")
    elif style_id == "screenshottalk":
        d.rounded_rectangle((90, 100, w - 90, 1650), radius=55, fill="#fff",
                            outline="#deded8", width=4)
        _photo_box(img, photo_path, (160, 190, w - 320, 520))
        _fit(d, headline, (130, 1420, w - 260, 130), fill=(24, 24, 24),
             start=58, align="center")
        _fit(d, subheadline, (130, 1710, w - 260, 220), fill=(24, 24, 24),
             start=40, bold=False, align="center")
    else:
        _photo_box(img, photo_path, (120, 120, w - 240, 980))
        _fit(d, headline, (120, 1220, w - 240, 180), fill=(34, 34, 29), start=72)
        _fit(d, subheadline, (120, 1450, w - 240, 220), fill=(138, 106, 47),
             start=42, bold=False)


def render_panels(manifest: dict, contract: dict, *,
                  panels: list, palette: dict | None = None,
                  photo_path: str | None = None):
    """Comic strip: N captioned panels stacked (setup/escalation/reversal/payoff).
    Deterministic boxes + real type, same QC discipline as single cards.
    The star photo opens panel 1 (portrait box); without it the strip is
    captions on art-directed panels — never bare wireframes."""
    pal = palette or {"bg": "#ffffff", "ink": "#141414", "accent": "#8a6a2f"}
    n = max(1, int((manifest.get("layout") or {}).get("panels", len(panels) or 1)))
    caps = [str(c or "")[:80] for c in list(panels)[:n]]
    while len(caps) < n:
        caps.append("")
    pw, ph, _dpi = contract_pixels(contract)
    gaps = []
    img = Image.new("RGB", (pw, ph), pal["bg"])
    d = ImageDraw.Draw(img)
    gutter, top = 24, 24
    ph_each = (ph - top * 2 - gutter * (n - 1)) // n
    have_photo = bool(photo_path and Path(photo_path).exists())
    for i, text in enumerate(caps):
        y0 = top + i * (ph_each + gutter)
        d.rectangle([24, y0, pw - 24, y0 + ph_each], fill="#fdfbf6",
                    outline=pal["ink"], width=4)
        d.rectangle([24, y0, pw - 24, y0 + 14], fill=pal["accent"])
        tx = 60
        if i == 0 and have_photo:
            pw_ = min(300, (pw - 120) // 3)
            _photo_box(img, photo_path, (60, y0 + 30, pw_, ph_each - 60))
            tx = 60 + pw_ + 40
        size = 44
        font = _font(size)
        while size > 16:
            bb = d.textbbox((0, 0), text, font=font)
            if bb[2] - bb[0] <= pw - tx - 60:
                break
            size -= 4
            font = _font(size)
        bb = d.textbbox((0, 0), text, font=font)
        if text and bb[2] - bb[0] > pw - tx - 60:
            gaps.append("panel %d caption overflows" % (i + 1))
        elif text:
            d.text((tx, y0 + 40), text, font=font, fill=pal["ink"])
        d.text((pw - 140, y0 + ph_each - 50), "%d/%d" % (i + 1, n),
               font=_font(28), fill=pal["accent"])
    if not have_photo and not any(caps):
        gaps.append("strip is blank — no captions and no star photo")
    return img, gaps
