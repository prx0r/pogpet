"""Deterministic scene artwork: the same composition powers paper and MP4.

No generation services. All assets passed here are validated local images.
Coordinates are proportional so preview and print use identical layouts.
"""
from __future__ import annotations

import math
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps

VERSION = 1
FORMATS = {
    "A6": {"label": "A6 postcard", "mm": [105, 148], "folded": False, "price_cents": 500},
    "5x7": {"label": "5 × 7 folded card", "mm": [127, 177.8], "folded": True, "price_cents": 799},
    "A5": {"label": "A5 folded card", "mm": [148, 210], "folded": True, "price_cents": 1500},
}
TEMPLATES = {
    "portrait": {"label": "The birthday portrait", "headline": "Happy birthday, legend.", "max_photos": 1, "min_photos": 1, "motion": "photo reveal", "bg": "#f8f1e6", "ink": "#22221d", "accent": "#a64332"},
    "family": {"label": "From the whole family", "headline": "Our favourite person.", "max_photos": 5, "min_photos": 1, "motion": "family photo reveals", "bg": "#f4eee4", "ink": "#22221d", "accent": "#31594b"},
    "breaking_news": {"label": "Breaking news", "headline": "Local dad officially declared a legend.", "max_photos": 1, "min_photos": 1, "motion": "news reveal + moving ticker", "bg": "#122433", "ink": "#ffffff", "accent": "#e34536"},
    "game_winner": {"label": "The game winner", "headline": "Still putting us all to shame.", "max_photos": 1, "min_photos": 1, "motion": "champion reveal + confetti", "bg": "#133e34", "ink": "#fff9e7", "accent": "#e5ba62"},
    "awards": {"label": "Lifetime achievement", "headline": "A lifetime of being a legend.", "max_photos": 1, "min_photos": 1, "motion": "award reveal + confetti", "bg": "#24222d", "ink": "#fff9e7", "accent": "#e5ba62"},
    "christmas": {"label": "The Christmas cast", "headline": "Merry Christmas", "max_photos": 5, "min_photos": 1, "motion": "snowfall + photo reveals", "bg": "#18382d", "ink": "#fff9e7", "accent": "#e6bd78"},
    "typography": {"label": "Say it properly", "headline": "You're one of a kind.", "max_photos": 0, "min_photos": 0, "motion": "title reveal", "bg": "#f4d651", "ink": "#22221d", "accent": "#22221d"},
    # ── the birthday five: locked product templates. Agent chooses photos +
    # text only — fonts are fixed per template (see "fonts"), enforced in save.
    "birthday_arch": {"label": "Birthday arch", "headline": "Happy birthday, legend.", "max_photos": 1, "min_photos": 1, "motion": "photo reveal", "bg": "#faf3e7", "ink": "#22221d", "accent": "#b34a30", "fonts": {"headline": "fraunces", "body": "courier"}},
    "birthday_dots": {"label": "Birthday dots", "headline": "Hip hip hooray!", "max_photos": 3, "min_photos": 1, "motion": "dot reveal", "bg": "#fdfdf8", "ink": "#1d1d22", "accent": "#3056b3", "fonts": {"headline": "inter_bold", "body": "inter"}},
    "birthday_news": {"label": "Birthday newsflash", "headline": "Local legend in birthday shocker.", "max_photos": 1, "min_photos": 1, "motion": "news reveal + moving ticker", "bg": "#14202e", "ink": "#ffffff", "accent": "#d43a2f", "fonts": {"headline": "inter_bold", "body": "courier"}},
    "birthday_gold": {"label": "Birthday gold", "headline": "Another year, more legend.", "max_photos": 1, "min_photos": 1, "motion": "champion reveal + confetti", "bg": "#1d1a16", "ink": "#fff6e3", "accent": "#d9a441", "fonts": {"headline": "fraunces", "body": "inter"}},
    "birthday_wall": {"label": "Birthday wall", "headline": "Our favourite person.", "max_photos": 5, "min_photos": 2, "motion": "wall reveals", "bg": "#f6efe3", "ink": "#26221c", "accent": "#2e6b4f", "fonts": {"headline": "fraunces", "body": "courier"}},
    # ── canonical product: birthday_4photo_title_v1 (docs/cardspec.md) ──
    # 4 rounded photo slots, generated title-art zone in the middle, flat
    # subline + footer zones. Exact zones live in CANONICAL_ZONES (1500×2100
    # trim space). Agent supplies photos + bounded copy only.
    "birthday_4photo": {"label": "Birthday four-photo", "headline": "Happy Birthday!", "max_photos": 4, "min_photos": 4, "motion": "photo reveal", "bg": "#faf6ee", "ink": "#23201b", "accent": "#b34a30", "fonts": {"headline": "fraunces", "body": "inter"}},
}

# Canonical zones in 1500×2100 trim px (see docs/cardspec.md §2–4).
# Grid gutter (56px) stays ≤ twice the slot corner radius: slots read as one
# grid, never four stickers. Type zones sit on flat stock, never on photos.
CANONICAL_ZONES = {
    "photos": [(120, 160, 602, 560), (778, 160, 602, 560),
               (120, 776, 602, 560), (778, 776, 602, 560)],
    "photo_radius": 28,
    "title_art": (285, 1390, 930, 320),
    "front_footer": (525, 1990, 450, 45),
    "inside_message": (1710, 430, 1040, 820),
    "inside_signature": (1710, 1330, 520, 120),
    "back_logo": (525, 1740, 450, 80),
    "back_url": (585, 1970, 330, 36),
}

# Frozen title-art vibes. The model may style lettering + mini-elements;
# never layout, logos, or extra text.
TITLE_VIBES = ("playful_balloons", "retro_party", "floral_soft", "comic_burst",
               "sports_energy", "clean_luxury", "childlike_doodle", "festive_confetti")

TITLE_PROMPT = ("Create a decorative title graphic on a transparent background. "
                "Render exactly this text: “{text}”. Style: {vibe}. "
                "Canvas size: {w}x{h} pixels. Keep the design centered and fully "
                "contained within the canvas with comfortable margins. No extra text. "
                "No border. No mockup. No card. Transparent background only. Make the "
                "lettering bold, clean, legible, and celebration-appropriate.")


def title_prompt(text: str, vibe: str, w: int = 930, h: int = 320) -> str:
    """Constrained generation-zone prompt: lettering + mini-elements only."""
    if vibe not in TITLE_VIBES:
        raise ValueError(f"title vibe must be one of {TITLE_VIBES}")
    return TITLE_PROMPT.format(text=str(text or "")[:40], vibe=vibe, w=w, h=h)

# Birthday product set: the only templates the agent offers for birthdays.
BIRTHDAY_TEMPLATES = ("birthday_4photo", "birthday_arch", "birthday_dots",
                      "birthday_news", "birthday_gold", "birthday_wall")
# Composition sharing: birthday covers reuse proven layouts with their own
# palettes, art and mastheads (one composition codebase, five products).
BIRTHDAY_COMP = {"birthday_arch": "portrait", "birthday_news": "breaking_news",
                 "birthday_gold": "game_winner"}

# ── design contracts (same reusable format as STUDIO_LINES) ─────────────
# domain "paper": locked = print truths a designer must not move; envelope =
# largest trim; material = stock; cost = rough print cost per format ex-VAT
# (live Prodigi quote wins). Photo counts mirror min/max above — the filter
# a model designs against.
CARD_DESIGN_CONTRACTS = {
    "portrait": {
        "domain": "paper",
        "locked": ["3mm bleed all round", "300dpi floor at trim", "folded formats: artwork keeps clear of the spine 6mm",
                   "1 photo exactly (face crop with focus point)"],
        "envelope_mm": [148, 210], "material": "350gsm silk", "colors_max": 0,
        "formats": ["A6", "5x7", "A5"],
        "cost_target_cents": {"A6": 120, "5x7": 200, "A5": 280},
        "verify": [],
    },
    "family": {
        "domain": "paper",
        "locked": ["3mm bleed all round", "300dpi floor at trim", "1–5 photos in 2-col grid, order preserved",
                   "folded formats: spine clearance 6mm"],
        "envelope_mm": [148, 210], "material": "350gsm silk", "colors_max": 0,
        "formats": ["A6", "5x7", "A5"],
        "cost_target_cents": {"A6": 120, "5x7": 200, "A5": 280},
        "verify": [],
    },
    "breaking_news": {
        "domain": "paper",
        "locked": ["3mm bleed all round", "300dpi floor at trim", "1 photo exactly",
                   "ticker zone reserved at foot on folded formats"],
        "envelope_mm": [148, 210], "material": "350gsm silk", "colors_max": 0,
        "formats": ["A6", "5x7", "A5"],
        "cost_target_cents": {"A6": 120, "5x7": 200, "A5": 280},
        "verify": [],
    },
    "game_winner": {
        "domain": "paper",
        "locked": ["3mm bleed all round", "300dpi floor at trim", "1 photo exactly",
                   "confetti zone keeps clear of the face crop"],
        "envelope_mm": [148, 210], "material": "350gsm silk", "colors_max": 0,
        "formats": ["A6", "5x7", "A5"],
        "cost_target_cents": {"A6": 120, "5x7": 200, "A5": 280},
        "verify": [],
    },
    "awards": {
        "domain": "paper",
        "locked": ["3mm bleed all round", "300dpi floor at trim", "1 photo exactly"],
        "envelope_mm": [148, 210], "material": "350gsm silk", "colors_max": 0,
        "formats": ["A6", "5x7", "A5"],
        "cost_target_cents": {"A6": 120, "5x7": 200, "A5": 280},
        "verify": [],
    },
    "christmas": {
        "domain": "paper",
        "locked": ["3mm bleed all round", "300dpi floor at trim", "1–5 photos in 2-col grid",
                   "snowfall zone keeps clear of faces"],
        "envelope_mm": [148, 210], "material": "350gsm silk", "colors_max": 0,
        "formats": ["A6", "5x7", "A5"],
        "cost_target_cents": {"A6": 120, "5x7": 200, "A5": 280},
        "verify": [],
    },
    "typography": {
        "domain": "paper",
        "locked": ["3mm bleed all round", "0 photos — type only", "headline wraps, never clips"],
        "envelope_mm": [148, 210], "material": "350gsm silk", "colors_max": 0,
        "formats": ["A6", "5x7", "A5"],
        "cost_target_cents": {"A6": 120, "5x7": 200, "A5": 280},
        "verify": [],
    },
    "birthday_arch": {
        "domain": "paper",
        "locked": ["3mm bleed all round", "300dpi floor at trim", "1 photo exactly in the arch slot",
                   "fonts fixed: fraunces headline, courier inside — agent chooses photos + text only"],
        "envelope_mm": [148, 210], "material": "350gsm silk", "colors_max": 0,
        "formats": ["5x7"],
        "cost_target_cents": {"5x7": 200},
        "verify": [],
    },
    "birthday_dots": {
        "domain": "paper",
        "locked": ["3mm bleed all round", "300dpi floor at trim", "1–3 photos in dot circles",
                   "fonts fixed: inter_bold headline, inter inside — agent chooses photos + text only"],
        "envelope_mm": [148, 210], "material": "350gsm silk", "colors_max": 0,
        "formats": ["5x7"],
        "cost_target_cents": {"5x7": 200},
        "verify": [],
    },
    "birthday_news": {
        "domain": "paper",
        "locked": ["3mm bleed all round", "300dpi floor at trim", "1 photo exactly in the frame slot",
                   "ticker zone reserved at foot", "fonts fixed: inter_bold headline, courier inside"],
        "envelope_mm": [148, 210], "material": "350gsm silk", "colors_max": 0,
        "formats": ["5x7"],
        "cost_target_cents": {"5x7": 200},
        "verify": [],
    },
    "birthday_gold": {
        "domain": "paper",
        "locked": ["3mm bleed all round", "300dpi floor at trim", "1 photo exactly in the medallion",
                   "fonts fixed: fraunces headline, inter inside — agent chooses photos + text only"],
        "envelope_mm": [148, 210], "material": "350gsm silk", "colors_max": 0,
        "formats": ["5x7"],
        "cost_target_cents": {"5x7": 200},
        "verify": [],
    },
    "birthday_wall": {
        "domain": "paper",
        "locked": ["3mm bleed all round", "300dpi floor at trim", "2–5 photos in the wall grid, order preserved",
                   "fonts fixed: fraunces headline, courier inside — agent chooses photos + text only"],
        "envelope_mm": [148, 210], "material": "350gsm silk", "colors_max": 0,
        "formats": ["5x7"],
        "cost_target_cents": {"5x7": 200},
        "verify": [],
    },
    "birthday_4photo": {
        "domain": "paper",
        "locked": ["3mm bleed all round", "300dpi floor at trim", "exactly 4 photos in fixed slots r28",
                   "title art 930x320 transparent in the middle zone only",
                   "fonts fixed by template — agent supplies 4 photos + bounded copy only"],
        "envelope_mm": [148, 210], "material": "350gsm silk", "colors_max": 0,
        "formats": ["5x7"],
        "cost_target_cents": {"5x7": 200},
        "verify": [],
    },
}

for _tid, _contract in CARD_DESIGN_CONTRACTS.items():
    if _tid in TEMPLATES:
        TEMPLATES[_tid]["design_contract"] = _contract
del _tid, _contract


def font(size, bold=False):
    # House type system (assets/fonts, all OFL commercial-print-safe):
    # display = Fraunces (headlines), hand = Caveat (names/signatures only),
    # sans = Inter (everything else). DejaVu is the fallback, never the look.
    return get_font("sans", size, bold=bold)


def get_font(role, size, bold=False):
    from pathlib import Path as _P
    here = _P(__file__).resolve().parent.parent / "assets" / "fonts"
    cands = {
        "display": [here / "Fraunces-SemiBold.ttf"],
        "hand": [here / "Caveat-SemiBold.ttf"],
        "sans": [here / "Inter-Bold.ttf" if bold else here / "Inter-Regular.ttf"],
    }[role]
    cands += ["/usr/share/fonts/truetype/dejavu/DejaVuSans" +
              ("-Bold" if bold else "") + ".ttf"]
    for base in cands:
        try:
            return ImageFont.truetype(str(base), max(8, int(size)))
        except OSError:
            pass
    return ImageFont.load_default()


# ── curated font registry (controlled custom, like coats) ──────────
# Buyers pick an id, never a file. Every file here is OFL,
# commercial-print-safe (see assets/fonts/OFL-NOTES.md). The renderer owns
# geometry; the registry owns taste. No free-form font inputs exist.
CARD_FONTS = {
    "fraunces": {"label": "Literary serif",
                 "mood": "warm, editorial headlines",
                 "vibes": ["warm", "proud", "romantic", "editorial"],
                 "occasions": ["birthday", "anniversary", "mothers_day",
                               "fathers_day", "retirement", "christmas"],
                 "use_for": ["headline"],
                 "file": "Fraunces-SemiBold.ttf"},
    "caveat": {"label": "Handwritten",
               "mood": "names, signatures, short affectionate accents",
               "vibes": ["playful", "affectionate", "personal"],
               "occasions": ["birthday", "valentines", "mothers_day",
                             "fathers_day", "anniversary", "general"],
               "use_for": ["name", "headline", "accent"],
               "file": "Caveat-SemiBold.ttf"},
    "inter": {"label": "Clean sans", "mood": "clear body copy",
              "vibes": ["sincere", "modern", "calm"],
              "occasions": ["general", "graduation", "new_baby",
                            "retirement", "mothers_day"],
              "use_for": ["body"],
              "file": "Inter-Regular.ttf"},
    "inter_bold": {"label": "Bold sans", "mood": "confident headlines",
                   "vibes": ["bold", "celebratory", "funny-loud"],
                   "occasions": ["birthday", "graduation", "retirement",
                                 "fathers_day"],
                   "use_for": ["headline"],
                   "file": "Inter-Bold.ttf"},
    "courier": {"label": "Typewriter",
                "mood": "typed-letter inside messages",
                "vibes": ["nostalgic", "sincere", "dry-funny"],
                "occasions": ["fathers_day", "birthday", "christmas",
                              "anniversary", "general"],
                "use_for": ["body"],
                "file": "CourierPrime-Regular.ttf"},
}
CARD_FONT_IDS = tuple(CARD_FONTS)
# size scale (multiplier on the panel base size) — S/M/L, never free points
CARD_SIZES = {"S": 0.8, "M": 1.0, "L": 1.25}
# semantic colours, resolved per template so contrast always holds
CARD_COLOURS = ("ink", "soft", "accent")
CARD_ALIGN = ("center", "left")


def font_for(font_id, size, bold=False):
    """Resolve a registry font id to a PIL font. Unknown ids fall back to
    Inter (sans) — never fail a render on taste."""
    from pathlib import Path as _P
    spec = CARD_FONTS.get(font_id) or {}
    fname = spec.get("file") or "Inter-Regular.ttf"
    if bold and fname == "Inter-Regular.ttf":
        fname = "Inter-Bold.ttf"
    if bold and fname == "CourierPrime-Regular.ttf":
        fname = "CourierPrime-Bold.ttf"
    here = _P(__file__).resolve().parent.parent / "assets" / "fonts"
    for base in (here / fname,
                 "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"):
        try:
            return ImageFont.truetype(str(base), max(8, int(size)))
        except OSError:
            pass
    return ImageFont.load_default()


# ── generative backdrops: beauty is generated ONCE per template ─────
# The template keeps rigid slots (photo zones, type zones). fal.ai paints
# only the backdrop: a text-free party texture that fills the whole cover.
# One paid generation per template, reused for every card forever.
# Backdrops live in assets/card-art/backdrops/<template>.png + SOURCES.
# Missing file = flat template colour. Geometry never moves.
TEMPLATE_BACKDROPS = {
    "birthday_arch": "birthday party balloon sky, soft cream bokeh, festive but airy, wide empty center",
    "birthday_dots": "pastel polka confetti field, light and airy, lots of empty cream space",
    "birthday_news": "dark navy broadcast studio glow, subtle light streaks, empty center",
    "birthday_gold": "dark champagne celebration bokeh, golden light spots, empty center",
    "birthday_wall": "warm cream party garland along the top edge only, rest empty",
}
_BACKDROP_CACHE: dict = {}


def _backdrop(tid, size):
    """Generated backdrop scaled to cover, or None (flat colour fallback)."""
    if tid in _BACKDROP_CACHE:
        bg = _BACKDROP_CACHE[tid]
        return bg.resize(size, Image.Resampling.LANCZOS) if bg else None
    from pathlib import Path as _P
    p = _P(__file__).resolve().parent.parent / "assets" / "card-art" / "backdrops" / f"{tid}.png"
    try:
        bg = Image.open(p).convert("RGB")
    except OSError:
        bg = None
    _BACKDROP_CACHE[tid] = bg
    return bg.resize(size, Image.Resampling.LANCZOS) if bg else None
# Real illustration composited around the photo slot — the Moonpig model:
# the template IS artwork, the photo is one ingredient. Only files listed
# in SOURCES.md may be used here. Missing files render without art, never fail.
# ── CC0 art library (assets/card-art, see SOURCES.md) ──────────────
# Real illustration composited around the photo slot — the Moonpig model:
# the template IS artwork, the photo is one ingredient. Only files listed
# in SOURCES.md may be used here. Missing files render without art, never fail.
CARD_ART = {
    "portrait": [("frame-mono-colored-34-14201-800.png", (0.0, 0.0, 1.0, 1.0), "fill"),
                 ("colored-balloons-191040-800.png", (0.02, 0.035, 0.30, 0.20)),
                 ("birthday-cake-3-304095-800.png", (0.74, 0.045, 0.22, 0.15))],
    "birthday_arch": [("balloon-border-3024-800.png", (0.0, 0.0, 1.0, 1.0), "fill"),
                      ("birthday-cake-296924-800.png", (0.74, 0.045, 0.22, 0.15))],
    "birthday_dots": [("pink-bow-170156-800.png", (0.40, 0.045, 0.20, 0.075))],
}
_ART_CACHE: dict = {}


def _art(name):
    """Load a library PNG once (RGBA). None if absent — art is garnish."""
    if name in _ART_CACHE:
        return _ART_CACHE[name]
    from pathlib import Path as _P
    p = _P(__file__).resolve().parent.parent / "assets" / "card-art" / name
    try:
        img = Image.open(p).convert("RGBA")
    except OSError:
        img = None
    _ART_CACHE[name] = img
    return img


def _sticker(card, name, box, mode="fit"):
    """Paste one art file into a relative box, alpha-honoured.
    fit = aspect-kept (stickers); fill = stretched edge-to-edge (borders)."""
    img = _art(name)
    if img is None:
        return
    w, h = card.size
    bw, bh = box[2] * w, box[3] * h
    if mode == "fill":
        thumb = img.resize((max(1, round(bw)), max(1, round(bh))),
                           Image.Resampling.LANCZOS)
        card.alpha_composite(thumb, (round(box[0] * w), round(box[1] * h)))
        return
    r = min(bw / img.width, bh / img.height)
    tw, th = max(1, round(img.width * r)), max(1, round(img.height * r))
    thumb = img.resize((tw, th), Image.Resampling.LANCZOS)
    card.alpha_composite(thumb, (round(box[0] * w + (bw - tw) / 2),
                                 round(box[1] * h + (bh - th) / 2)))


def _luminance(hexcol):
    hexcol = hexcol.lstrip("#")
    r, g, b = (int(hexcol[i:i + 2], 16) / 255 for i in (0, 2, 4))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def ink_for(design, which="ink", *, paper="#fffdf7"):
    """Semantic colour → hex. On the card front the reference is the
    template palette; on inside paper (always light cream) ink must stay
    dark no matter how light the front ink is (white front ink on cream
    paper is invisible — the dark-card bug)."""
    tpl = TEMPLATES[design["template"]]
    if which == "accent":
        # gold accents vanish on cream — deepen them there
        if paper == "#fffdf7" and _luminance(tpl["accent"]) > 0.6:
            return "#8a6a2f"
        return tpl["accent"]
    if which == "soft":
        return "#55554d" if _luminance(paper) > 0.5 else "#cfcabb"
    if paper == "#fffdf7" and _luminance(tpl["ink"]) > 0.7:
        return "#22221d"
    return tpl["ink"]


def back(design, width=720, height=None):
    """Canonical back: brand mark, tagline, URL, quiet margins. The renderer
    owns it — never AI, never blank."""
    fmt = FORMATS[design["format"]]
    height = height or round(width * fmt["mm"][1] / fmt["mm"][0])
    img = Image.new("RGB", (width, height), "#fffdf7")
    d = ImageDraw.Draw(img)
    ink, muted, gold = "#22221d", "#55554d", "#8a6a2f"
    d.text((width / 2, height * 0.42), "oddhobb.", font=get_font("display", width * 0.09),
           fill=ink, anchor="mm")
    d.text((width / 2, height * 0.50), "odd little gifts for the things they're obsessed with",
           font=get_font("sans", width * 0.028), fill=muted, anchor="mm")
    d.text((width / 2, height * 0.90), "oddhobb.com", font=get_font("sans", width * 0.03),
           fill=gold, anchor="mm")
    return img


class TextOverflow(ValueError):
    pass


def text_block(draw, text, box, colour, size, *, bold=False, align="center",
               role="sans", font_id=None):
    """Wrap and shrink to fit the entire text; never silently clip a headline.
    font_id (registry) wins over role when given."""
    x, y, w, h = box
    fitted=False
    for fs in range(max(8,int(size)), 7, -1):
        f = font_for(font_id, fs, bold) if font_id else get_font(role, fs, bold)
        lines = []
        for paragraph in str(text).split("\n"):
            line = ""
            for word in paragraph.split():
                # Break a single unspaced token too.
                pieces = [word]
                if draw.textlength(word, font=f) > w:
                    pieces, part = [], ""
                    for char in word:
                        if part and draw.textlength(part + char, font=f) > w:
                            pieces.append(part); part = ""
                        part += char
                    if part:
                        pieces.append(part)
                for piece in pieces:
                    candidate = (line + " " + piece).strip()
                    if line and draw.textlength(candidate, font=f) > w:
                        lines.append(line); line = piece
                    else:
                        line = candidate
            lines.append(line)
        lh = fs * 1.35
        if lh * len(lines) <= h and all(draw.textlength(line,font=f)<=w for line in lines):
            fitted=True
            break
    if not fitted:
        raise TextOverflow("Text does not fit this card. Shorten it or remove some line breaks.")
    for n, line in enumerate(lines):
        dx = x if align == "left" else x + (w - draw.textlength(line, font=f)) / 2
        draw.text((dx, y + n * lh), line, fill=colour, font=f)


def cropped(img, box):
    img = ImageOps.exif_transpose(img).convert("RGBA")
    x, y, w, h = box
    return img.crop((round(x * img.width), round(y * img.height),
                     round((x + w) * img.width), round((y + h) * img.height)))


MASTHEAD = {"breaking_news": "BREAKING NEWS", "game_winner": "THE GAME WINNER",
            "awards": "LIFETIME ACHIEVEMENT", "christmas": "THE CHRISTMAS CAST",
            "birthday_news": "HAPPY BIRTHDAY", "birthday_gold": "HIP HIP HOORAY"}


def _tile(slot, assets, size, progress, i):
    reveal = max(0.0, min(1.0, progress * 2.2 - i * .13))
    if reveal <= 0:
        return None, 0.0
    src = assets[slot["photo_id"]].copy()
    if not slot.get("cutout"):
        src = cropped(src, slot["crop"])
    if slot.get("cutout"):
        src.thumbnail(size, Image.Resampling.LANCZOS)
        tile = Image.new("RGBA", size)
        tile.alpha_composite(src, ((size[0] - src.width) // 2, size[1] - src.height))
    else:
        tile = ImageOps.fit(src, size, method=Image.Resampling.LANCZOS,
                            centering=tuple(slot["focus"]))
    tile.putalpha(tile.getchannel("A").point(lambda v: round(v * reveal)))
    return tile, reveal


def _scatter(draw, w, h, n, seed, colors, box, size=0.012):
    """Seeded confetti/dots inside a relative box — deterministic per design."""
    import random as _r
    rng = _r.Random(seed)
    x0, y0, bw, bh = box
    for i in range(n):
        cx, cy = x0 + rng.random() * bw, y0 + rng.random() * bh
        r = max(2, round(w * size * (0.6 + rng.random() * 0.8)))
        draw.ellipse((w * cx - r, h * cy - r, w * cx + r, h * cy + r),
                     fill=colors[i % len(colors)])


def _shape_mask(size, shape, radius=None):
    """L-mode mask: arch | circle | round | rect."""
    from PIL import Image as _I
    sw, sh = size
    mask = _I.new("L", size, 0)
    md = ImageDraw.Draw(mask)
    if shape == "circle":
        md.ellipse((0, 0, sw, sh), fill=255)
    elif shape == "arch":
        md.rectangle((0, sh // 3, sw, sh), fill=255)
        md.ellipse((0, 0, sw, sh * 2 // 3), fill=255)
    elif shape == "round":
        r = min(sw, sh) // 8 if radius is None else int(radius)
        md.rounded_rectangle((0, 0, sw, sh), radius=r, fill=255)
    else:
        md.rectangle((0, 0, sw, sh), fill=255)
    return mask


def _photo_zone(slot, assets, size, *, shape="round", border=0,
                border_fill="#ffffff", progress=1.0, seed=0, radius=None):
    """A photo slotted into a designed frame: masked shape + border ring.
    Crop/focus/cutout all honoured — the zone shows the crop, never raw full-frame."""
    sw, sh = max(1, round(size[0])), max(1, round(size[1]))
    reveal = max(0.0, min(1.0, progress * 2.2 - seed * .13))
    if reveal <= 0:
        return None, 0.0
    src = assets[slot["photo_id"]].copy()
    if not slot.get("cutout"):
        src = cropped(src, slot["crop"])
    if slot.get("cutout"):
        src.thumbnail((sw, sh), Image.Resampling.LANCZOS)
        tile = Image.new("RGBA", (sw, sh))
        tile.alpha_composite(src, ((sw - src.width) // 2, sh - src.height))
    else:
        tile = ImageOps.fit(src, (sw, sh), method=Image.Resampling.LANCZOS,
                            centering=tuple(slot["focus"]))
    tile.putalpha(Image.composite(tile.getchannel("A"),
                                  Image.new("L", tile.size, 0),
                                  _shape_mask((sw, sh), shape, radius)))
    tile.putalpha(tile.getchannel("A").point(lambda v: round(v * reveal)))
    if border:
        ring = Image.new("RGBA", (sw + border * 2, sh + border * 2), (0, 0, 0, 0))
        bd = ImageDraw.Draw(ring)
        if shape == "circle":
            bd.ellipse((0, 0, ring.width, ring.height), fill=border_fill)
        elif shape == "arch":
            bd.rectangle((0, ring.height // 3, ring.width, ring.height), fill=border_fill)
            bd.ellipse((0, 0, ring.width, ring.height * 2 // 3), fill=border_fill)
        elif shape == "round":
            bd.rounded_rectangle((0, 0, ring.width, ring.height),
                                 radius=min(ring.size) // 8, fill=border_fill)
        else:
            bd.rectangle((0, 0, ring.width, ring.height), fill=border_fill)
        ring.alpha_composite(tile, (border, border))
        return ring, reveal
    return tile, reveal


def _frames(card, draw, design, assets, boxes, *, shape="round", border=0,
            border_fill="#ffffff", progress=1.0):
    """Slot each photo into its designed box. Boxes are relative (x,y,w,h)."""
    w, h = card.size
    for i, (slot, box) in enumerate(zip(design["photos"], boxes)):
        tile, reveal = _photo_zone(slot, assets,
                                   (box[2] * w, box[3] * h), shape=shape,
                                   border=max(0, round(border * w)),
                                   border_fill=border_fill,
                                   progress=progress, seed=i)
        if tile is None:
            continue
        tw, th = tile.size
        px = round(box[0] * w + (box[2] * w - tw) / 2 + (1 - reveal) * h * .02)
        py = round(box[1] * h + (1 - reveal) * h * .025)
        card.alpha_composite(tile, (px, py))


def front(design, assets, width=720, height=None, progress=1.0):
    """Designed covers: every template is a real composition — masked photo
    zones slotted into graphics, type in flat zones that never sit on faces.
    Same signature in/out so print, motion, gallery and MCP keep working."""
    fmt = FORMATS[design["format"]]
    height = height or round(width * fmt["mm"][1] / fmt["mm"][0])
    tpl = TEMPLATES[design["template"]]
    card = Image.new("RGBA", (width, height), tpl["bg"])
    _bg = _backdrop(design["template"], (width, height))
    if _bg is not None:
        card.alpha_composite(_bg.convert("RGBA"))
    d = ImageDraw.Draw(card)
    w, h = width, height
    accent, ink, bg = tpl["accent"], tpl["ink"], tpl["bg"]
    slots = design["photos"]
    count = len(slots)
    tid = design["template"]
    comp = BIRTHDAY_COMP.get(tid, tid)
    hfont = design.get("headline_font") or "fraunces"

    d.rectangle((w*.04, h*.03, w*.96, h*.97), outline=accent, width=max(1, w//180))

    if comp == "portrait" and count:
        # illustrated birthday cover: art around an arch photo slot
        for _entry in CARD_ART.get(tid, []):
            _name, _box = _entry[0], _entry[1]
            _sticker(card, _name, _box, *(_entry[2:3] or ("fit",)))
        _scatter(d, w, h, 26, 7, [accent, "#e5ba62", ink], (0.06, 0.045, 0.88, 0.05))
        _frames(card, d, design, assets, [(0.16, 0.11, 0.68, 0.50)],
                shape="arch", border=0.008, border_fill="#ffffff",
                progress=progress)
        if progress > .15:
            text_block(d, design["headline"], (w*.08, h*.65, w*.84, h*.14),
                       ink, w*.062, bold=True, font_id=hfont)
        text_block(d, design["recipient"], (w*.08, h*.82, w*.84, h*.05),
                   accent, w*.03, bold=True, role="hand")
        text_block(d, design["sender"], (w*.08, h*.885, w*.84, h*.03), ink, w*.021)
        return card.convert("RGB")

    if comp == "breaking_news":
        # broadcast card: red masthead, framed photo, cream headline band
        d.rectangle((w*.04, h*.03, w*.96, h*.13), fill=accent)
        text_block(d, MASTHEAD.get(tid, "BREAKING NEWS"), (w*.08, h*.055, w*.84, h*.06),
                   "#ffffff", w*.038, bold=True)
        if count:
            _frames(card, d, design, assets, [(0.12, 0.17, 0.76, 0.40)],
                    shape="round", border=0.006, border_fill="#ffffff",
                    progress=progress)
        if progress > .15:
            text_block(d, design["headline"], (w*.08, h*.60, w*.84, h*.14),
                       "#ffffff", w*.058, bold=True, font_id=hfont)
        text_block(d, design["recipient"], (w*.08, h*.77, w*.84, h*.05),
                   accent, w*.03, bold=True, role="hand")
        text_block(d, design["sender"], (w*.08, h*.83, w*.84, h*.03), ink, w*.021)
        d.rectangle((w*.04, h*.90, w*.96, h*.97), fill=accent)
        if progress < 1:
            ticker = "OFFICIAL: " + (design["recipient"] or "A LEGEND") + " • "
            f = font(w*.018, True)
            tw = max(1, d.textlength(ticker, font=f))
            for x in range(-round(progress*tw), w+round(tw), round(tw)):
                d.text((x, h*.915), ticker, font=f, fill="white")
        else:
            f = font(w*.018, True)
            d.text((w*.08, h*.915), "OFFICIAL • VERIFIED • LIVE", font=f, fill="white")
        return card.convert("RGB")

    if comp in ("game_winner", "awards"):
        # medallion card: gold-ringed circle on confetti, cream headline band
        _scatter(d, w, h, 40, 21, [accent, "#ffffff", ink], (0.05, 0.04, 0.90, 0.90), 0.010)
        title = MASTHEAD.get(tid)
        if title:
            text_block(d, title, (w*.08, h*.05, w*.84, h*.06), ink, w*.032, bold=True)
        if count:
            _frames(card, d, design, assets, [(0.24, 0.13, 0.52, 0.42)],
                    shape="circle", border=0.012, border_fill=accent,
                    progress=progress)
        if progress > .15:
            text_block(d, design["headline"], (w*.08, h*.60, w*.84, h*.14),
                       ink, w*.058, bold=True, font_id=hfont)
        text_block(d, design["recipient"], (w*.08, h*.77, w*.84, h*.05),
                   accent, w*.03, bold=True, role="hand")
        text_block(d, design["sender"], (w*.08, h*.83, w*.84, h*.03), ink, w*.021)
        return card.convert("RGB")

    if tid == "christmas":
        # ornament row: gold-rimmed baubles on snow, gold serif below
        for i in range(45):
            px, py = (i*127) % w, (i*97 + round(progress*h)) % h
            d.ellipse((px, py, px+w*.005, py+w*.005), fill="#ffffff")
        if count:
            n = min(count, 5)
            if n == 1:
                boxes = [(0.28, 0.10, 0.44, 0.36)]
            else:
                gw = 0.80 / n
                boxes = [(0.10 + i*gw + gw*0.08, 0.12, gw*0.84, 0.30) for i in range(n)]
            _frames(card, d, design, assets, boxes[:n],
                    shape="circle", border=0.008, border_fill="#e6bd78",
                    progress=progress)
            d.rectangle((w*.48, h*.045, w*.52, h*.10), fill="#e6bd78")
        if progress > .15:
            text_block(d, design["headline"], (w*.08, h*.50 if count else h*.30, w*.84, h*.16),
                       "#fff9e7", w*.06, bold=True, font_id=hfont)
        text_block(d, design["recipient"], (w*.08, h*.70 if count else h*.60, w*.84, h*.05),
                   "#e6bd78", w*.03, bold=True, role="hand")
        text_block(d, "THE CHRISTMAS CAST", (w*.08, h*.055, w*.84, h*.05),
                   "#e6bd78", w*.03, bold=True)
        text_block(d, design["sender"], (w*.08, h*.78, w*.84, h*.03), "#fff9e7", w*.021)
        return card.convert("RGB")

    if tid == "family":
        # framed grid on warm stock with a solid headline band
        if count:
            n = min(count, 5)
            cols = 2 if n > 1 else 1
            rows = math.ceil(n / cols)
            gap = 0.03
            cw, ch = (0.84 - gap*(cols-1)) / cols, 0.46 / rows
            boxes = [(0.08 + (i % cols)*(cw+gap), 0.09 + (i//cols)*(ch+gap), cw, ch)
                     for i in range(n)]
            _frames(card, d, design, assets, boxes, shape="round",
                    border=0.005, border_fill="#ffffff", progress=progress)
        d.rectangle((w*.04, h*.62, w*.96, h*.84), fill=ink)
        if progress > .15:
            text_block(d, design["headline"], (w*.08, h*.645, w*.84, h*.12),
                       "#fff9e7", w*.052, bold=True, font_id=hfont)
        text_block(d, design["recipient"], (w*.08, h*.775, w*.84, h*.04),
                   accent, w*.028, bold=True, role="hand")
        text_block(d, design["sender"], (w*.08, h*.875, w*.84, h*.03), ink, w*.021)
        return card.convert("RGB")

    if tid == "birthday_dots" and count:
        # dot field: 1–3 circle slots on scattered dots, bold headline band
        for _entry in CARD_ART.get(tid, []):
            _name, _box = _entry[0], _entry[1]
            _sticker(card, _name, _box, *(_entry[2:3] or ("fit",)))
        _scatter(d, w, h, 60, 42, [accent, "#e08a3c", "#3cb35e"],
                 (0.05, 0.04, 0.90, 0.55), 0.014)
        n = min(count, 3)
        gw = 0.84 / n
        boxes = [(0.08 + i * gw + gw * 0.1, 0.16, gw * 0.8, 0.34) for i in range(n)]
        _frames(card, d, design, assets, boxes, shape="circle",
                border=0.007, border_fill=accent, progress=progress)
        d.rectangle((w*.04, h*.58, w*.96, h*.80), fill=ink)
        if progress > .15:
            text_block(d, design["headline"], (w*.08, h*.605, w*.84, h*.14),
                       "#ffffff", w*.055, bold=True, font_id=hfont)
        text_block(d, design["recipient"], (w*.08, h*.83, w*.84, h*.05),
                   accent, w*.03, bold=True, role="hand")
        text_block(d, design["sender"], (w*.08, h*.895, w*.84, h*.03), ink, w*.021)
        return card.convert("RGB")

    if tid == "birthday_wall" and count:
        # photo wall: 2–5 white-bordered frames over a solid headline band
        n = min(max(count, 2), 5)
        cols = 2
        rows = math.ceil(n / cols)
        gap = 0.03
        cw, ch = (0.84 - gap * (cols - 1)) / cols, 0.44 / rows
        boxes = [(0.08 + (i % cols) * (cw + gap), 0.07 + (i // cols) * (ch + gap), cw, ch)
                 for i in range(n)]
        _frames(card, d, design, assets, boxes, shape="round",
                border=0.005, border_fill="#ffffff", progress=progress)
        d.rectangle((w*.04, h*.60, w*.96, h*.82), fill=ink)
        if progress > .15:
            text_block(d, design["headline"], (w*.08, h*.625, w*.84, h*.12),
                       "#fffdf7", w*.05, bold=True, font_id=hfont)
        text_block(d, design["recipient"], (w*.08, h*.775, w*.84, h*.04),
                   accent, w*.028, bold=True, role="hand")
        text_block(d, design["sender"], (w*.08, h*.875, w*.84, h*.03), ink, w*.021)
        return card.convert("RGB")

    if tid == "birthday_4photo" and count == 4:
        # canonical product: 4 rounded slots, title-art zone, subline + footer
        s = w / 1500.0
        d.rectangle((w*.04, h*.03, w*.96, h*.97), outline=accent, width=max(1, w//180))
        for slot, (zx, zy, zw, zh) in zip(slots, CANONICAL_ZONES["photos"]):
            tile, reveal = _photo_zone(slot, assets,
                                       (zw * s, zh * s), shape="round",
                                       border=0, progress=progress, seed=0,
                                       radius=28 * s)
            if tile is None:
                continue
            # fixed 28px corner radius at trim scale
            card.alpha_composite(tile, (round(zx * s), round(zy * s)))
        tx, ty, tw, th = [v * s for v in CANONICAL_ZONES["title_art"]]
        art = None
        tkey = design.get("title_art_key") or ""
        if tkey:
            try:
                from backend import cards as _cardsmod
                with Image.open(_cardsmod.local_asset(tkey)) as _im:
                    art = _im.convert("RGBA")
            except OSError:
                art = None
        if art is not None:
            r = min(tw / art.width, th / art.height)
            art = art.resize((max(1, round(art.width * r)), max(1, round(art.height * r))),
                             Image.Resampling.LANCZOS)
            card.alpha_composite(art, (round(tx + (tw - art.width) / 2),
                                       round(ty + (th - art.height) / 2)))
        elif progress > .15:
            # fallback lettering fills the zone on ONE line — shrink to fit,
            # never wrap small. Generated title art replaces this when present.
            _t = design["headline"]
            _fs = round(th * 0.30)
            while _fs > 8:
                _f = font_for(design.get("headline_font") or "fraunces", _fs, True)
                if d.textlength(_t, font=_f) <= tw:
                    break
                _fs -= 2
            else:
                _f = font_for(design.get("headline_font") or "fraunces", 8, True)
            d.text((tx + (tw - d.textlength(_t, font=_f)) / 2, ty + (th - _fs) / 2),
                   _t, font=_f, fill=ink)
        sx, sy, sw, sh = [v * s for v in CANONICAL_ZONES["front_footer"]]
        # footer is the bare signature — no prefixes stacked, no recipient echo
        foot = design.get("sender", "") if len(design.get("sender", "")) <= 32 else ""
        if foot:
            try:
                text_block(d, foot, (sx, sy, sw, sh), ink, sw * 0.075)
            except TextOverflow:
                pass  # footer is garnish — small previews skip it, print keeps it
        return card.convert("RGB")

    # typography + fallback: full-bleed type poster (no photos by design)
    if count:
        gap, x0, y0 = w*.025, w*.08, h*.08
        cols = 1 if count == 1 else 2
        rows = math.ceil(count / cols)
        sw, sh = (w*.84 - gap*(cols-1))/cols, (h*.60-gap*(rows-1))/rows
        for i, slot in enumerate(slots):
            tile, reveal = _tile(slot, assets, (max(1, round(sw)), max(1, round(sh))), progress, i)
            if tile is None:
                continue
            px, py = round(x0+(i%cols)*(sw+gap)), round(y0+(i//cols)*(sh+gap)+(1-reveal)*h*.025)
            card.alpha_composite(tile, (px, py))
    hy = h*.70 if count else h*.30
    if progress > .15:
        text_block(d, design["headline"], (w*.08, hy, w*.84, h*.15 if count else h*.35), ink, w*.065, bold=True, font_id=hfont)
    text_block(d, design["recipient"], (w*.08, h*.87, w*.84, h*.04), accent, w*.029, bold=True, role="hand")
    text_block(d, design["sender"], (w*.08, h*.925, w*.84, h*.025), ink, w*.021)
    return card.convert("RGB")


def _panel_style(panel: dict, default_font: str) -> tuple:
    """(font_id, scale, colour_name, align) with safe defaults."""
    panel = panel or {}
    font = panel.get("font") if panel.get("font") in CARD_FONT_IDS else default_font
    size = panel.get("size") if panel.get("size") in CARD_SIZES else "M"
    colour = panel.get("colour") if panel.get("colour") in CARD_COLOURS else "ink"
    align = panel.get("align") if panel.get("align") in CARD_ALIGN else "center"
    return font, CARD_SIZES[size], colour, align


def inside(design, width=720, height=None):
    """Folded inside spread, double-panel wide: left half then right half.
    Left defaults blank (quiet stock); right carries the message + sender.
    Per-panel font/size/colour/align ride in design["inside"]."""
    fmt = FORMATS[design["format"]]
    height = height or round(width * fmt["mm"][1] / fmt["mm"][0])
    if design.get("template") == "birthday_4photo":
        # canonical spread: 3000×2100 space, blank left, message + signature
        # + brand zones on the right. Coordinates from CANONICAL_ZONES.
        img = Image.new("RGB", (width, height), "#fffdf7")
        d = ImageDraw.Draw(img)
        s = width / 3000.0
        mx, my, mw, mh = [v * s for v in CANONICAL_ZONES["inside_message"]]
        right = ((design.get("inside") or {}).get("right")) or {}
        rfont = right.get("font") if right.get("font") in CARD_FONT_IDS else "inter"
        text_block(d, right.get("message", design.get("inside_message", "")),
                   (mx, my, mw, mh), "#23201b", mw * 0.062, align="center",
                   font_id=rfont)
        sx, sy, sw, sh = [v * s for v in CANONICAL_ZONES["inside_signature"]]
        text_block(d, design.get("sender", ""), (sx, sy, sw, sh),
                   "#55554d", sw * 0.09, align="center", font_id="caveat")
        # no brand mark inside a personal card — back only
        return img
    img = Image.new("RGB", (width, height), "#fffdf7")
    d = ImageDraw.Draw(img)
    hw = width / 2
    inner = design.get("inside") or {}
    # right: the message (legacy inside_message feeds it)
    right = inner.get("right") or {}
    rfont, rscale, rcolour, ralign = _panel_style(right, "inter")
    rmsg = right.get("message", design.get("inside_message", ""))
    text_block(d, rmsg, (hw + width*.06, height*.24, width*.38, height*.44),
               ink_for(design, rcolour), width*.04*rscale, align=ralign,
               font_id=rfont)
    text_block(d, design.get("sender", ""), (hw + width*.06, height*.78, width*.38, height*.10),
               ink_for(design, "soft"), width*.025, font_id="caveat")
    # left: blank, or a short secondary note
    left = inner.get("left") or {}
    if (left.get("mode") or "blank") == "message" and left.get("text"):
        lfont, lscale, lcolour, lalign = _panel_style(left, "inter")
        text_block(d, left["text"], (width*.06, height*.24, width*.38, height*.44),
                   ink_for(design, lcolour), width*.036*lscale, align=lalign,
                   font_id=lfont)
    return img


def inside_half(design, half="right", width=720, height=None):
    """One inside half as its own PNG (agent-showable panels)."""
    fmt = FORMATS[design["format"]]
    height = height or round(width * fmt["mm"][1] / fmt["mm"][0])
    full = inside(design, width * 2, height)
    return full.crop((0, 0, width, height) if half == "left"
                     else (width, 0, width * 2, height))


def print_pdf(design, assets, dest):
    """300dpi PDF: postcard front/back, or folded outside/inside spreads.

3mm bleed is included. Generic export; supplier SKU matching is separate.
"""
    fmt = FORMATS[design["format"]]
    w,h = [round(mm*300/25.4) for mm in fmt["mm"]]
    bleed = round(3*300/25.4)
    a,b = front(design,assets,w,h), inside(design,w,h)
    back_img = back(design, w, h)
    pages=[]
    pairs = [(back_img,a),(Image.new("RGB",(w,h),"#fffdf7"),b)] if fmt["folded"] else [(a,),(b,)]
    for panels in pairs:
        spread=Image.new("RGB",(w*len(panels),h),"#fffdf7")
        for i,panel in enumerate(panels):
            spread.paste(panel,(i*w,0))
        # Extend edge pixels into bleed rather than add a white rim.
        page=Image.new("RGB",(spread.width+2*bleed,h+2*bleed))
        page.paste(spread,(bleed,bleed))
        page.paste(spread.crop((0,0,spread.width,1)).resize((spread.width,bleed)),(bleed,0))
        page.paste(spread.crop((0,h-1,spread.width,h)).resize((spread.width,bleed)),(bleed,h+bleed))
        page.paste(page.crop((bleed,0,bleed+1,page.height)).resize((bleed,page.height)),(0,0))
        page.paste(page.crop((spread.width+bleed-1,0,spread.width+bleed,page.height)).resize((bleed,page.height)),(spread.width+bleed,0))
        pages.append(page)
    pages[0].save(dest,"PDF",resolution=300,save_all=True,append_images=pages[1:])


def motion(design, assets, dest, seconds=6, fps=18):
    """Bounded CPU render streamed to ffmpeg; no frame directory or shell."""
    width=480
    height=round(width*FORMATS[design["format"]]["mm"][1]/FORMATS[design["format"]]["mm"][0]/2)*2
    cmd=["ffmpeg","-hide_banner","-loglevel","error","-y","-f","rawvideo","-pix_fmt","rgb24","-s",f"{width}x{height}","-r",str(fps),"-i","-","-an","-c:v","libx264","-preset","veryfast","-threads","2","-pix_fmt","yuv420p","-movflags","+faststart",str(dest)]
    import tempfile
    with tempfile.TemporaryFile() as log:
        p=subprocess.Popen(cmd,stdin=subprocess.PIPE,stderr=log)
        try:
            for frame in range(seconds*fps):
                # Final frame is exactly the printed front composition.
                t=frame/max(1,seconds*fps-1)
                img=front(design,assets,width,height,t)
                p.stdin.write(img.tobytes())
            p.stdin.close()
            if p.wait(timeout=60):
                log.seek(0)
                raise RuntimeError("Video encoder failed: "+log.read(500).decode(errors="replace"))
        finally:
            if p.poll() is None:
                p.kill();p.wait()
