"""Step 8: print imposition only. Generated art in, Prodigi 7x5 master + 3 previews out.

Nothing here designs. The front is the generated art, full bleed. Inside-left
is the generated spot vignette. Inside-right is the LIVE message (editable per
order). The back is the fixed oddhobb.com mark.

Prodigi GLOBAL-GRE 7x5 portrait, measured from Prodigi's PSD template:
one JPG 6117x2161 @300dpi; left half = back|front (fold x=1529),
right half = inside-left|inside-right (fold x=4587); bleed 34 px.
"""
from __future__ import annotations
import sys, json, textwrap
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageFilter

HERE = Path(__file__).parent
_FD = HERE / "fonts" if (HERE / "fonts").is_dir() else HERE.parent / "assets" / "fonts"
FONT = {k: str(_FD / f) for k, f in
        {"display": "Fraunces-SemiBold.ttf", "hand": "Caveat-SemiBold.ttf", "body": "Inter-Regular.ttf"}.items()}
PAPER = (251, 247, 238)
INK = (30, 30, 30)
B = 34                      # bleed px
PW, PH = 1563, 2161         # one page with bleed on all four sides
TW, TH = 1495, 2093         # trim
SAFE = 90                   # our content margin inside trim


def cover(img: Image.Image, w: int, h: int) -> Image.Image:
    """Scale-to-cover + centre crop (art is already 5:7, so the crop is a few px)."""
    s = max(w / img.width, h / img.height)
    im = img.resize((round(img.width * s), round(img.height * s)), Image.LANCZOS)
    x, y = (im.width - w) // 2, (im.height - h) // 2
    return im.crop((x, y, x + w, y + h))


def front(art: Image.Image) -> Image.Image:
    return cover(art.convert("RGB"), PW, PH)


def back() -> Image.Image:
    im = Image.new("RGB", (PW, PH), PAPER)
    d = ImageDraw.Draw(im)
    f = ImageFont.truetype(FONT["display"], 64)
    t = "oddhobb."
    d.text(((PW - d.textlength(t, font=f)) / 2, PH - B - 330), t, font=f, fill=INK)
    f2 = ImageFont.truetype(FONT["body"], 34)
    for i, t in enumerate(["Made from your photos", "oddhobb.com"]):
        d.text(((PW - d.textlength(t, font=f2)) / 2, PH - B - 240 + i * 52), t, font=f2, fill=(110, 105, 98))
    return im


def inside_left(spot: Image.Image | None) -> Image.Image:
    im = Image.new("RGB", (PW, PH), PAPER)
    if spot is None:
        return im
    sp = spot.convert("RGB")
    side = 980
    sp = cover(sp, side, side)
    # spots are generated on a flat off-white: re-key that background to the exact
    # paper colour (per-channel gain from the corner median), then feather the edge
    import statistics as st
    px = [sp.getpixel((x, y)) for x in (5, side - 6) for y in (5, side - 6)]
    bg = [st.median(c[i] for c in px) for i in range(3)]
    gain = [PAPER[i] / max(bg[i], 1) for i in range(3)]
    sp = Image.merge("RGB", [ch.point(lambda v, g=g: min(255, round(v * g))) for ch, g in zip(sp.split(), gain)])
    mask = Image.new("L", (side, side), 0)
    ImageDraw.Draw(mask).ellipse((40, 40, side - 40, side - 40), fill=255)
    mask = mask.filter(ImageFilter.GaussianBlur(60))
    im.paste(sp, ((PW - side) // 2, (PH - side) // 2), mask)
    return im


def inside_right(message: str, signature: str, recipient: str = "") -> Image.Image:
    im = Image.new("RGB", (PW, PH), PAPER)
    d = ImageDraw.Draw(im)
    x0, w = B + SAFE + 40, TW - 2 * (SAFE + 40)
    y = B + 640
    if recipient:
        fr = ImageFont.truetype(FONT["hand"], 92)
        d.text((x0, y), recipient + ",", font=fr, fill=INK)
        y += 150
    size = 62
    while True:
        f = ImageFont.truetype(FONT["display"], size)
        lines, cur = [], ""
        for word in message.split():
            t = (cur + " " + word).strip()
            if d.textlength(t, font=f) <= w:
                cur = t
            else:
                lines.append(cur); cur = word
        lines.append(cur)
        if len(lines) * size * 1.4 <= 700 or size <= 44:
            break
        size -= 2
    for ln in lines:
        d.text((x0, y), ln, font=f, fill=INK)
        y += int(size * 1.4)
    fs = ImageFont.truetype(FONT["hand"], 104)
    d.text((x0, y + 70), signature, font=fs, fill=INK)
    return im


def build(art_path, spot_path, message, signature, recipient, outdir):
    out = Path(outdir); out.mkdir(parents=True, exist_ok=True)
    art = Image.open(art_path)
    spot = Image.open(spot_path) if spot_path else None
    fr, bk = front(art), back()
    il, ir = inside_left(spot), inside_right(message, signature, recipient)
    sheet = Image.new("RGB", (6117, 2161), PAPER)
    # outer half: back | front (fold 1529); inner half: inside-left | inside-right (fold 4587)
    sheet.paste(bk.crop((0, 0, 1529, PH)), (0, 0))        # left bleed + trim
    sheet.paste(fr.crop((34, 0, PW, PH)), (1529, 0))      # trim + right bleed
    sheet.paste(il.crop((0, 0, 1529, PH)), (3058, 0))
    sheet.paste(ir.crop((33, 0, PW, PH)), (4587, 0))      # 1530 wide
    sheet.save(out / "print_prodigi_7x5.jpg", quality=95, subsampling=0, dpi=(300, 300))
    trim = lambda im: im.crop((B, B, B + TW, B + TH))
    # previews: exactly three, at trim
    trim(fr).save(out / "1_front.jpg", quality=90)
    spread = Image.new("RGB", (TW * 2, TH), PAPER)
    spread.paste(trim(il), (0, 0)); spread.paste(trim(ir), (TW, 0))
    ImageDraw.Draw(spread).line((TW, 0, TW, TH), fill=(225, 219, 207), width=3)
    spread.save(out / "2_inside.jpg", quality=90)
    trim(bk).save(out / "3_back.jpg", quality=90)
    return out


if __name__ == "__main__":
    a = json.loads(sys.argv[1])
    print(build(**a))
