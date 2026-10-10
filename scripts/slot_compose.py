#!/usr/bin/env python3
"""Slot compositor: any name on a pre-rendered blank 'plate' in milliseconds.

A plate = a render of the fixed mesh with empty slots + <plate>.json (the
camera projection of each slot plane). Slots are planar: one homography per
plane is exact; text is extruded by stacking warps base->top. No re-render,
no remesh, no AI lettering (AI misspells and drifts from print).

Plates live in data/productimg/plates/<line>/ (PNG + JSON pairs). Absent
plates → staged with a clear reason (see backend/slots.py).

usage: python3 scripts/slot_compose.py plates/midnight-gold-hero.png \
  '{"name":"SAM","tagline":"JUNIOR 180 CLUB","arc":"SAM'"'"'S OCHE","accent":"#D7B25A"}' out.png

Ported from the product team's slotcomp.py; paths rooted at repo ROOT,
fonts from assets/fonts/, spec from backend/slot_specs/dart_stand.json.
"""
import json
import math
import sys
import time
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageFont, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
FONTS = str(ROOT / "assets" / "fonts") + "/"
SPEC = json.loads((ROOT / "backend" / "slot_specs" / "dart_stand.json").read_text())
PX = 20.0
HALF = 60.0
T = int(2 * HALF * PX)  # texture: 20 px/mm over +-60 mm


def mm2px(x, y):
    return ((x + HALF) * PX, (HALF - y) * PX)


def font_for(fname, cap_mm):
    f = ImageFont.truetype(FONTS + fname, 200)
    b = f.getbbox('H')
    cap = b[3] - b[1]
    return ImageFont.truetype(FONTS + fname, max(4, int(round(200 * cap_mm * PX / cap))))


def draw_centered(mask, s, fname, cap_mm, cx, cy, maxw=None):
    f = font_for(fname, cap_mm)
    d = ImageDraw.Draw(mask)
    b = d.textbbox((0, 0), s, font=f)
    w = (b[2] - b[0]) / PX
    if maxw and w > maxw:
        cap_mm *= maxw / w
        f = font_for(fname, cap_mm)
        b = d.textbbox((0, 0), s, font=f)
    px, py = mm2px(cx, cy)
    d.text((px - (b[0] + b[2]) / 2, py - (b[1] + b[3]) / 2), s, font=f, fill=255)
    return cap_mm


def draw_arc(mask, s, fname, cap_mm, R, center_deg=270, gap=0.21):
    f = font_for(fname, cap_mm)
    items = []
    for ch in s:
        if ch == ' ':
            items.append((None, cap_mm * 0.38))
            continue
        b = f.getbbox(ch)
        items.append((ch, (b[2] - b[0]) / PX))
    total = sum(w for _, w in items) + gap * cap_mm * (len(items) - 1)
    cur = -total / 2
    hb = f.getbbox('H')
    for ch, w in items:
        mid = cur + w / 2
        cur += w + gap * cap_mm
        if ch is None:
            continue
        th = math.radians(center_deg) + mid / R
        rot = math.degrees(th) + 90
        b = f.getbbox(ch)
        g = Image.new('L', (b[2] + 20, hb[3] + 20), 0)
        ImageDraw.Draw(g).text((10 - b[0], 10), ch, font=f, fill=255)
        g = g.crop((10, 10 + hb[1], 10 + b[2] - b[0], 10 + hb[3]))
        g = g.rotate(rot, resample=Image.BICUBIC, expand=True)
        px, py = mm2px(R * math.cos(th), R * math.sin(th))
        mask.paste(255, (int(px - g.width / 2), int(py - g.height / 2)), g)


def H(corners):  # noqa: N802 - homography matrix, matches product notation
    src = np.float32([[0, T], [T, T], [T, 0], [0, 0]])
    return cv2.getPerspectiveTransform(src, np.float32(corners))


def lerp(a, b, t):
    return [[a[i][0] + (b[i][0] - a[i][0]) * t, a[i][1] + (b[i][1] - a[i][1]) * t] for i in range(4)]


def hexrgb(h):
    h = h.lstrip('#')
    return np.array([int(h[i:i + 2], 16) for i in (0, 2, 4)], float)


def extrude(img, mask, c_base, c_top, accent, layers=10, light=(-0.6, -0.8)):
    W, Hh = img.shape[1], img.shape[0]
    m = np.asarray(mask, np.float32) / 255

    def warp(cs):
        return cv2.warpPerspective(m, H(cs), (W, Hh), flags=cv2.INTER_LINEAR)
    base = warp(c_base)
    top = warp(c_top)
    sh = cv2.GaussianBlur(np.roll(np.roll(base, int(4 * W / 1200), 1), int(5 * W / 1200), 0), (0, 0), 3 * W / 1200)
    img = img * (1 - 0.55 * sh[..., None])
    side = accent * 0.42
    for i in range(layers):
        t = i / layers
        a = warp(lerp(c_base, c_top, t))
        c = side * (0.75 + 0.35 * t)
        img = img * (1 - a[..., None]) + c * a[..., None]
    gy, gx = np.gradient(cv2.GaussianBlur(top, (0, 0), 1.2 * W / 1200))
    rim = np.clip(-(gx * light[0] + gy * light[1]) * 6, 0, 1)
    yy = np.linspace(1.08, 0.9, Hh)[:, None]
    face = np.clip(accent[None, None] * yy[..., None] + 120 * rim[..., None], 0, 255)
    img = img * (1 - top[..., None]) + face * top[..., None]
    return img


def compose(plate, params, out):
    t0 = time.time()
    Pj = plate.replace('.png', '.json')
    if not Path(Pj).is_file():
        raise FileNotFoundError(f"no plate projection {Pj} — render the blank plate first")
    P = json.load(open(Pj))
    C = P['corners']
    img = np.asarray(Image.open(plate).convert('RGB'), np.float32)
    acc = hexrgb(params.get('accent', '#D7B25A'))
    F = SPEC['fields']
    rep = {}
    name = params['name'].upper()
    mn = Image.new('L', (T, T), 0)
    cap = draw_centered(mn, name, F['name']['font'], F['name']['cap_mm'], 0, -29.6, maxw=F['name']['max_width_mm'])
    if cap < F['name']['min_cap_mm']:
        raise ValueError('name too long')
    rep['name_cap_mm'] = round(cap, 2)
    if params.get('tagline'):
        draw_centered(mn, params['tagline'].upper(), F['tagline']['font'], F['tagline']['cap_mm'], 0, -36.0,
                      maxw=F['tagline']['max_width_mm'])
    img = extrude(img, mn, C['name_base'], C['name_top'], acc)
    if params.get('arc'):
        ma = Image.new('L', (T, T), 0)
        draw_arc(ma, params['arc'].upper(), F['arc']['font'], F['arc']['cap_mm'], F['arc']['radius_mm'])
        img = extrude(img, ma, C['arc_base'], C['arc_top'], acc, layers=6)
    Image.fromarray(np.clip(img, 0, 255).astype(np.uint8)).save(out)
    rep['ms'] = int((time.time() - t0) * 1000)
    print(json.dumps(rep))
    return rep


if __name__ == '__main__':
    compose(sys.argv[1], json.loads(sys.argv[2]), sys.argv[3])
