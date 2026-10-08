"""Golden geometry for the canonical product: layout invariants the suite
can actually see. Pixels differ ≠ design exists; these assert the design."""
from PIL import Image, ImageDraw

from backend import card_scenes as S

W = 720
SCL = W / 1500.0


def _design():
    return {
        "template": "birthday_4photo", "format": "5x7",
        "headline": "Happy Birthday, Chris!", "recipient": "Chris",
        "sender": "Ben & Peter", "inside_message": "You carried Christmas again.",
        "headline_font": "fraunces", "title_vibe": "playful_balloons",
        "title_art_key": "",
        "photos": [{"photo_id": f"p{i}", "crop": [0, 0, 1, 1],
                    "focus": [0.5, 0.5], "cutout": ""} for i in range(4)],
        "inside": {
            "left": {"mode": "blank", "text": "", "font": "inter",
                     "size": "M", "colour": "ink", "align": "center"},
            "right": {"mode": "message", "message": "You carried Christmas again.",
                      "font": "inter", "size": "M", "colour": "ink",
                      "align": "center"}},
    }


def _assets():
    out = {}
    for i in range(4):
        im = Image.new("RGB", (600, 600), (150 + i * 20, 110 + i * 8, 95))
        d = ImageDraw.Draw(im)
        d.ellipse((150, 100, 450, 400), fill=(220 + i * 5, 190, 160))
        out[f"p{i}"] = im.convert("RGBA")
    return out


def _ink_fraction(img, box):
    x0, y0, x1, y1 = [max(0, int(v)) for v in box]
    region = img.convert("L").crop((x0, y0, x1, y1))
    px = list(region.getdata())
    dark = sum(1 for v in px if v < 100)
    return dark / max(1, len(px))


def _box(zone):
    x, y, w, h = [v * SCL for v in zone]
    return (x, y, x + w, y + h)


def test_title_zone_sits_between_photo_rows():
    """The founder's geometry: two photos, TITLE, two photos. A future
    'tight grid' must fail here, loudly."""
    photos = S.CANONICAL_ZONES["photos"]
    top_bottom = max(z[1] + z[3] for z in photos[:2])
    title = S.CANONICAL_ZONES["title_art"]
    bottom_top = min(z[1] for z in photos[2:])
    assert title[1] > top_bottom, "title must start below the top row"
    assert title[1] + title[3] < bottom_top, "title must end above the bottom row"


def test_front_has_four_photos_and_middle_title():
    front = S.front(_design(), _assets(), W)
    assert front.size == (W, round(W * 177.8 / 127))
    for i, z in enumerate(S.CANONICAL_ZONES["photos"]):
        # photo slots read as photos, not stock: differ from cream bg
        crop = front.crop(_box(z))
        px = list(crop.convert("L").getdata())
        assert sum(1 for v in px if abs(v - 246) > 12) / len(px) > 0.9, f"slot {i} empty"
    # middle title band carries real lettering (fallback serif counts)
    assert _ink_fraction(front, _box(S.CANONICAL_ZONES["title_art"])) > 0.005
    # footer is garnish, not a billboard
    assert _ink_fraction(front, _box(S.CANONICAL_ZONES["front_footer"])) < 0.25


def test_inside_message_right_blank_left():
    inside = S.inside(_design(), width=1440, assets={})
    s = 1440 / 3000.0
    mx, my, mw, mh = [v * s for v in S.CANONICAL_ZONES["inside_message"]]
    assert _ink_fraction(inside, (mx, my, mx + mw, my + mh)) > 0.005
    w, h = inside.size
    assert _ink_fraction(inside, (0, 0, w * 0.45, h)) < 0.005


def test_back_is_quiet_brand_only():
    back = S.back(_design(), W)
    w, h = back.size
    frac = _ink_fraction(back, (0, 0, w, h))
    assert 0.001 < frac < 0.05, frac
    # mass sits centre-frame, not shouting from the top
    gray = back.convert("L")
    xs = [x for y in range(0, h, 8) for x in range(0, w, 8)
          if gray.getpixel((x, y)) < 100]
    ys = [y for y in range(0, h, 8) for x in range(0, w, 8)
          if gray.getpixel((x, y)) < 100]
    assert w * 0.3 < sum(xs) / len(xs) < w * 0.7
    assert sum(ys) / len(ys) > h * 0.3


def test_title_contract_rejects_opaque():
    from backend import cards as C
    assert C.TITLE_ART_SIZE == (930, 320)
    opaque = Image.new("RGB", (1200, 500), (200, 30, 40))
    assert C.fit_title_art(opaque) is None
    rgba = Image.new("RGBA", (1200, 500), (0, 0, 0, 0))
    d = ImageDraw.Draw(rgba)
    d.text((300, 150), "Happy Birthday", fill=(20, 20, 20, 255))
    fitted = C.fit_title_art(rgba)
    assert fitted is not None and fitted.size == (930, 320)


def test_triptych_panels_share_one_height():
    design, assets = _design(), _assets()
    front = S.front(design, assets, 360)
    inside = S.inside(design, width=720, assets={})
    back = S.back(design, 360)
    tri = S.triptych(front, inside, back, height=504)
    # every panel scaled individually to one height: 360 + 360 + 360 + pads
    assert tri.size == (360 * 3 + 36 * 4, 504 + 72)
