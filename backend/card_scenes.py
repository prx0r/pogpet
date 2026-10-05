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
    "5x7": {"label": "5 × 7 folded card", "mm": [127, 177.8], "folded": True, "price_cents": 1000},
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
}


def font(size, bold=False):
    suffix = "-Bold" if bold else ""
    for base in ("/usr/share/fonts/truetype/dejavu/DejaVuSans", "/usr/share/fonts/truetype/liberation2/LiberationSans"):
        try:
            return ImageFont.truetype(base + suffix + ".ttf", max(8, int(size)))
        except OSError:
            pass
    return ImageFont.load_default()


class TextOverflow(ValueError):
    pass


def text_block(draw, text, box, colour, size, *, bold=False, align="center"):
    """Wrap and shrink to fit the entire text; never silently clip a headline."""
    x, y, w, h = box
    fitted=False
    for fs in range(max(8,int(size)), 7, -1):
        f = font(fs, bold)
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


def front(design, assets, width=720, height=None, progress=1.0):
    fmt = FORMATS[design["format"]]
    height = height or round(width * fmt["mm"][1] / fmt["mm"][0])
    tpl = TEMPLATES[design["template"]]
    card = Image.new("RGBA", (width, height), tpl["bg"])
    d = ImageDraw.Draw(card)
    w, h = width, height
    accent, ink = tpl["accent"], tpl["ink"]
    d.rectangle((w*.04, h*.03, w*.96, h*.97), outline=accent, width=max(1, w//180))
    title = {"breaking_news": "BREAKING NEWS", "game_winner": "THE GAME WINNER", "awards": "LIFETIME ACHIEVEMENT", "christmas": "THE CHRISTMAS CAST"}.get(design["template"], "ODDHOBB")
    if design["template"] == "breaking_news":
        d.rectangle((w*.04, h*.03, w*.96, h*.13), fill=accent)
    text_block(d, title, (w*.08, h*.06, w*.84, h*.06), ink, w*.035, bold=True)
    slots = design["photos"]
    count = len(slots)
    if count:
        gap, x0, y0 = w*.025, w*.08, h*.16
        cols = 1 if count == 1 else 2
        rows = math.ceil(count / cols)
        sw, sh = (w*.84 - gap*(cols-1))/cols, (h*.49-gap*(rows-1))/rows
        for i, slot in enumerate(slots):
            reveal = max(0.0, min(1.0, progress*2.2-i*.13))
            if reveal <= 0:
                continue
            src = assets[slot["photo_id"]].copy()
            if not slot.get("cutout"):
                src = cropped(src, slot["crop"])
            size = (max(1, round(sw)), max(1, round(sh)))
            if slot.get("cutout"):
                src.thumbnail(size, Image.Resampling.LANCZOS)
                tile = Image.new("RGBA", size)
                tile.alpha_composite(src, ((size[0]-src.width)//2, size[1]-src.height))
            else:
                tile = ImageOps.fit(src, size, method=Image.Resampling.LANCZOS, centering=tuple(slot["focus"]))
            tile.putalpha(tile.getchannel("A").point(lambda v: round(v*reveal)))
            px, py = round(x0+(i%cols)*(sw+gap)), round(y0+(i//cols)*(sh+gap)+(1-reveal)*h*.025)
            card.alpha_composite(tile, (px, py))
    hy = h*.70 if count else h*.30
    if progress > .15:
        text_block(d, design["headline"], (w*.08, hy, w*.84, h*.15 if count else h*.35), ink, w*.065, bold=True)
    text_block(d, design["recipient"], (w*.08, h*.87, w*.84, h*.04), accent, w*.029, bold=True)
    text_block(d, design["sender"], (w*.08, h*.925, w*.84, h*.025), ink, w*.021)
    if design["template"] in ("awards", "game_winner") and progress < 1:
        for i in range(32):
            px = ((i*137)%w)
            py = ((i*83 + round(progress*h*1.8))%h)
            d.rectangle((px,py,px+max(2,w*.006),py+max(4,h*.009)), fill=accent)
    if design["template"] == "christmas":
        for i in range(45):
            px, py = (i*127)%w, (i*97+round(progress*h))%h
            d.ellipse((px,py,px+w*.005,py+w*.005), fill="#ffffff")
    if design["template"] == "breaking_news" and progress < 1:
        d.rectangle((w*.04,h*.97-w*.04,w*.96,h*.97), fill=accent)
        ticker = "OFFICIAL: " + (design["recipient"] or "A LEGEND") + " • "
        f = font(w*.018, True)
        tw = max(1, d.textlength(ticker, font=f))
        for x in range(-round(progress*tw), w+round(tw), round(tw)):
            d.text((x,h*.97-w*.035),ticker,font=f,fill="white")
    return card.convert("RGB")


def inside(design, width=720, height=None):
    fmt = FORMATS[design["format"]]
    height = height or round(width * fmt["mm"][1] / fmt["mm"][0])
    img = Image.new("RGB", (width, height), "#fffdf7")
    d = ImageDraw.Draw(img)
    text_block(d, design["inside_message"], (width*.12,height*.28,width*.76,height*.45), "#22221d", width*.04)
    text_block(d, design["sender"], (width*.12,height*.80,width*.76,height*.10), "#55554d", width*.025)
    return img


def print_pdf(design, assets, dest):
    """300dpi PDF: postcard front/back, or folded outside/inside spreads.

3mm bleed is included. Generic export; supplier SKU matching is separate.
"""
    fmt = FORMATS[design["format"]]
    w,h = [round(mm*300/25.4) for mm in fmt["mm"]]
    bleed = round(3*300/25.4)
    a,b = front(design,assets,w,h), inside(design,w,h)
    back = Image.new("RGB",(w,h),"#fffdf7")
    text_block(ImageDraw.Draw(back), "oddhobb.com", (w*.1,h*.85,w*.8,h*.1), "#55554d",w*.035)
    pages=[]
    pairs = [(back,a),(Image.new("RGB",(w,h),"#fffdf7"),b)] if fmt["folded"] else [(a,),(b,)]
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
