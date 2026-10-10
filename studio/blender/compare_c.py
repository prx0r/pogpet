#!/usr/bin/env python3
"""Layer C check: intended colour (sim LED mean) vs observed colour (diffuser region of the Blender render).
Writes out/layer_c_sheet.png and out/layer_c_report.json. Flags hue drift > 25 deg or saturation kept < 50%."""
import json, os, glob, colorsys, sys
from PIL import Image, ImageDraw, ImageFont
H = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); O = f'{H}/out'
sys.path.insert(0, H); from simulate import ring, font
keys = json.load(open(f'{O}/mood_lamp_trace_keys.json')); acts = json.load(open(f'{O}/mood_lamp_sim.json'))['actions']
try:
    import cv2, numpy as np
    def denoise(im): return Image.fromarray(cv2.fastNlMeansDenoisingColored(np.array(im), None, 7, 7, 7, 21))
except Exception: denoise = lambda im: im
rows, rep = [], []
for k in keys:
    im = denoise(Image.open(f'{O}/layer_c/c_{k["t"]:05.1f}.png').convert('RGB'))
    reg = im.crop((170, 150, 310, 250)); px = list(reg.get_flattened_data()) if hasattr(reg, 'get_flattened_data') else list(reg.getdata())
    obs = tuple(sum(p[i] for p in px) / len(px) / 255 for i in range(3))
    lit = [p for p in k['leds'] if max(p) > 0]; want = tuple(sum(p[i] for p in lit) / max(len(lit), 1) / 255 for i in range(3))
    hw, sw, vw = colorsys.rgb_to_hsv(*want); ho, so, vo = colorsys.rgb_to_hsv(*obs)
    dh = abs(((ho - hw) * 360 + 180) % 360 - 180); keep = so / sw if sw > 0.05 else 1
    lab = [a['action'].split('->')[-1].strip() for a in acts if a['t'] <= k['t']][-1]
    flag = 'OK' if (sw < 0.1 or dh <= 25) and keep >= 0.5 else 'DRIFT'
    rep.append(dict(t=k['t'], intent=lab, lux=k['lux'], hue_drift_deg=round(dh), saturation_kept=round(keep, 2), verdict=flag))
    rows.append((k, im, lab, dh, keep, flag))
W = 300; sheet = Image.new('RGB', (W * len(rows), 600), (16, 16, 20)); d = ImageDraw.Draw(sheet); F, f2 = font(19), font(16)
for i, (k, im, lab, dh, keep, flag) in enumerate(rows):
    x = i * W; ring(d, x + W // 2, 120, 80, k['leds'], 14)
    d.text((x + 12, 12), f'{k["t"]:.1f}s  {k["lux"]:.0f} lx', fill=(200, 200, 205), font=F)
    d.text((x + 12, 222), lab[:30], fill=(230, 230, 235), font=f2)
    sheet.paste(im.resize((W, W)).crop((0, 20, W, W)), (x, 250))
    d.text((x + 12, 540), f'hue drift {dh:.0f}°, sat kept {keep*100:.0f}%', fill=(120, 230, 140) if flag == 'OK' else (255, 150, 80), font=f2)
    d.text((x + 12, 564), flag, fill=(120, 230, 140) if flag == 'OK' else (255, 150, 80), font=F)
d.text((12, 196), 'intended (sim)', fill=(150, 150, 160), font=f2); d.text((12, 256), 'observed (Blender, diffuser)', fill=(200, 200, 205), font=f2)
sheet.save(f'{O}/layer_c_sheet.png'); json.dump(rep, open(f'{O}/layer_c_report.json', 'w'), indent=1)
for r in rep: print(r)
