"""Product mockups rendered from the ACTIVE pog.

"Display all the products as their selected mesh" — every catalogue item gets
a rendered preview with that owner's current pog on it. Deterministic and
cheap (PIL only), cached in R2 per (owner, product) so switching the active
pog is the only thing that invalidates them.
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps

from . import config

W = H = 720
BG = (21, 19, 26)          # sits under the dark product card
INK = (17, 17, 17)
PAPER = (250, 250, 248)
VIOLET = (139, 61, 255)
PUMPKIN = (255, 122, 26)
LILAC = (234, 216, 255)


def _font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for cand in (
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ):
        try:
            return ImageFont.truetype(cand, size)
        except OSError:
            continue
    return ImageFont.load_default()


def _photo(path: Path | None, size: int) -> Image.Image | None:
    """Square crop of the source, or None.

    Accepts either the uploaded JPEG or a Blender render (RGBA with a
    transparent background) — alpha is flattened onto paper first so the
    subject doesn't come out as a black silhouette.
    """
    if not path or not path.is_file():
        return None
    try:
        im = Image.open(path)
    except Exception:
        return None
    if im.mode in ("RGBA", "LA") or (im.mode == "P" and "transparency" in im.info):
        im = im.convert("RGBA")
        flat = Image.new("RGB", im.size, PAPER)
        flat.paste(im, (0, 0), im)
        im = flat
    else:
        im = im.convert("RGB")
    side = min(im.size)
    im = im.crop(((im.width - side) // 2, (im.height - side) // 2,
                  (im.width + side) // 2, (im.height + side) // 2))
    return im.resize((size, size), Image.LANCZOS)


def _circle(im: Image.Image, size: int) -> Image.Image:
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).ellipse([0, 0, size, size], fill=255)
    out = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    out.paste(im.resize((size, size), Image.LANCZOS), (0, 0), mask)
    return out


def _frame(d: ImageDraw.ImageDraw, box, radius: int, fill, outline, width: int = 4) -> None:
    d.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)


def render(shape: str, photo: Path | None, label: str, out_path: Path,
           concept: dict | None = None, subject: str = "") -> Path:
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img, "RGBA")
    im = _photo(photo, 300)

    def paste(box, radius=None, mask_circle=False):
        if im is None:
            return
        w = box[2] - box[0]
        h = box[3] - box[1]
        size = min(w, h)
        src = im.resize((size, size), Image.LANCZOS)
        cx = box[0] + (w - size) // 2
        cy = box[1] + (h - size) // 2
        if mask_circle:
            mask = Image.new("L", (size, size), 0)
            ImageDraw.Draw(mask).ellipse([0, 0, size, size], fill=255)
            img.paste(src, (cx, cy), mask)
        else:
            if radius:
                mask = Image.new("L", (size, size), 0)
                ImageDraw.Draw(mask).rounded_rectangle([0, 0, size, size], radius=radius, fill=255)
                img.paste(src, (cx, cy), mask)
            else:
                img.paste(src, (cx, cy))

    # soft glow behind the product — tinted by the concept's world
    tint = VIOLET
    if concept:
        world = (concept.get("world") or "").lower()
        tint = {"wizard": (139, 61, 255), "mystic": (124, 255, 107),
                "christmas": (229, 52, 27)}.get(world, VIOLET)
    glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(glow).ellipse([110, 90, 610, 590], fill=(*tint, 52))
    img.paste(Image.alpha_composite(img.convert("RGBA"), glow).convert("RGB"), (0, 0))

    if shape == "card":
        _frame(d, [70, 90, 650, 610], 18, PAPER, (226, 220, 230), 3)
        d.line([360, 90, 360, 610], fill=(214, 208, 220), width=3)   # fold
        paste([100, 140, 340, 380], radius=14)
        d.text([505, 260], "hello", font=_font(34), fill=VIOLET, anchor="mm")

    elif shape == "postcard":
        _frame(d, [50, 180, 670, 520], 12, PAPER, (226, 220, 230), 3)
        paste([80, 215, 340, 475], radius=10)
        for i in range(5):
            d.line([400, 250 + i * 44, 640, 250 + i * 44], fill=(206, 200, 214), width=3)
        d.rounded_rectangle([590, 205, 650, 265], radius=6, outline=PUMPKIN, width=4)

    elif shape == "sticker":
        d.ellipse([110, 110, 610, 610], fill=PAPER, outline=(255, 255, 255), width=14)
        paste([165, 165, 555, 555], mask_circle=True)
        d.ellipse([110, 110, 610, 610], outline=PUMPKIN, width=6)

    elif shape in ("print", "poster", "photo_tile"):
        outer = [70, 70, 650, 650] if shape != "photo_tile" else [110, 110, 610, 610]
        _frame(d, outer, 6, INK, (60, 54, 70), 10)
        inner = [outer[0] + 34, outer[1] + 34, outer[2] - 34, outer[3] - 34]
        _frame(d, inner, 2, PAPER, VIOLET, 6)
        paste([inner[0] + 16, inner[1] + 16, inner[2] - 16, inner[3] - 16], radius=4)

    elif shape == "cushion":
        d.rounded_rectangle([80, 120, 640, 600], radius=70, fill=(46, 40, 58),
                            outline=(72, 64, 88), width=6)
        paste([150, 170, 570, 550], radius=40)
        d.rounded_rectangle([80, 120, 640, 600], radius=70, outline=VIOLET, width=5)

    elif shape == "mug":
        d.rounded_rectangle([130, 170, 540, 590], radius=26, fill=PAPER,
                            outline=(226, 220, 230), width=4)
        d.arc([500, 250, 660, 510], start=-70, end=70, fill=PUMPKIN, width=34)
        paste([175, 235, 495, 555], radius=16)
        d.rounded_rectangle([130, 170, 540, 590], radius=26, outline=VIOLET, width=5)

    elif shape == "tote":
        d.rounded_rectangle([130, 210, 590, 620], radius=20, fill=PAPER,
                            outline=(226, 220, 230), width=4)
        d.arc([200, 100, 520, 340], start=180, end=360, fill=VIOLET, width=26)
        paste([185, 265, 535, 615], radius=14)

    elif shape == "notebook":
        d.rounded_rectangle([150, 90, 570, 630], radius=12, fill=(34, 30, 44),
                            outline=(60, 54, 74), width=5)
        d.line([190, 90, 190, 630], fill=PUMPKIN, width=8)
        paste([230, 150, 530, 450], radius=10)
        d.text([380, 540], "notes", font=_font(30), fill=LILAC, anchor="mm")

    elif shape == "jigsaw":
        _frame(d, [70, 100, 650, 600], 10, PAPER, (226, 220, 230), 4)
        paste([110, 140, 610, 560], radius=6)
        for i in range(1, 4):   # cut lines — the lid art
            x = 70 + (580 // 4) * i
            for y in range(100, 600, 22):
                d.line([x, y, x, y + 11], fill=(150, 144, 160), width=3)
            y = 100 + (500 // 4) * i
            for x in range(70, 650, 22):
                d.line([x, y, x + 11, y], fill=(150, 144, 160), width=3)

    elif shape == "paper":
        d.rounded_rectangle([40, 130, 680, 590], radius=8, fill=(38, 32, 50),
                            outline=(70, 62, 86), width=4)
        for x in range(60, 680, 96):        # fold creases
            d.line([x, 130, x, 590], fill=(58, 50, 74), width=2)
        for i, px in enumerate(range(70, 640, 145)):
            paste([px, 175, px + 130, 305], radius=10)
        d.text([360, 480], "wrap it", font=_font(36), fill=PUMPKIN, anchor="mm")

    else:                                    # generic fallback tile
        _frame(d, [90, 130, 630, 590], 18, (38, 32, 50), VIOLET, 5)
        paste([150, 190, 570, 530], radius=18)

    # footer: label + brand, always on; concept/subject when personalising
    y = H - 46
    if concept:
        cname = concept.get("name") or ""
        cworld = (concept.get("world") or "").upper()
        d.text([W // 2, y - 34], cname, font=_font(30), fill=tint, anchor="mm")
        d.text([W // 2, y], f"{cworld} · {label}", font=_font(24),
               fill=(150, 146, 158), anchor="mm")
    else:
        d.text([W // 2, y], label, font=_font(26), fill=(150, 146, 158), anchor="mm")
    if subject:
        # the owner's name sits on the plinth, like the printed base would
        d.text([W // 2, 60], subject, font=_font(38), fill=(250, 250, 248), anchor="mm")
    d.text([W // 2, H - 26], "pog.", font=_font(28), fill=(120, 116, 130), anchor="mm")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(out_path, "PNG", optimize=True)
    return out_path
