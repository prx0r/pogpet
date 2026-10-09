# Generate prop textures (mahjong tile faces, a hand card) with PIL.
import os, random
from PIL import Image, ImageDraw, ImageFont, ImageFilter
D = '/workspace/projects/791a7153-8d05-4c9b-b767-8f281ad46eb0/etsy_samples/props/'
os.makedirs(D, exist_ok=True)
F = '/workspace/projects/791a7153-8d05-4c9b-b767-8f281ad46eb0/pogpet/assets/fonts/'
IVORY = (246, 240, 226)
RED, GRN, BLU = (196, 36, 40), (24, 120, 70), (28, 64, 150)
W, H = 420, 560

def base():
    im = Image.new('RGB', (W, H), IVORY); return im, ImageDraw.Draw(im)

def dot(d, cx, cy, r, col):
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=col)
    d.ellipse([cx - r * .72, cy - r * .72, cx + r * .72, cy + r * .72], fill=IVORY)
    d.ellipse([cx - r * .5, cy - r * .5, cx + r * .5, cy + r * .5], fill=col)
    d.ellipse([cx - r * .18, cy - r * .18, cx + r * .18, cy + r * .18], fill=IVORY)

LAY = {1: [(0, 0)], 2: [(0, -1), (0, 1)], 3: [(-1, -1), (0, 0), (1, 1)], 4: [(-1, -1), (1, -1), (-1, 1), (1, 1)],
       5: [(-1, -1), (1, -1), (0, 0), (-1, 1), (1, 1)], 6: [(-1, -1.2), (1, -1.2), (-1, 0), (1, 0), (-1, 1.2), (1, 1.2)],
       7: [(-1, -1.4), (0, -1.1), (1, -0.8), (-1, 0.4), (1, 0.4), (-1, 1.4), (1, 1.4)],
       8: [(-1, -1.5), (1, -1.5), (-1, -.5), (1, -.5), (-1, .5), (1, .5), (-1, 1.5), (1, 1.5)],
       9: [(-1, -1.2), (0, -1.2), (1, -1.2), (-1, 0), (0, 0), (1, 0), (-1, 1.2), (0, 1.2), (1, 1.2)]}

def dots(n):
    im, d = base(); cols = [BLU, GRN, RED]
    r = 120 if n == 1 else (62 if n <= 4 else 52 if n <= 6 else 44)
    for i, (x, y) in enumerate(LAY[n]):
        dot(d, W / 2 + x * 105, H / 2 + y * 120, r, RED if (n == 1 or (n in (5, 9) and (x, y) == (0, 0))) else cols[i % 2])
    return im

def bams(n):
    im, d = base()
    for i, (x, y) in enumerate(LAY[n]):
        cx, cy = W / 2 + x * 110, H / 2 + y * (150 if n <= 3 else 118); col = RED if (n in (5, 7, 9) and (x, y) == (0, 0)) or (n == 7 and i == 0) else GRN
        hh = 120 if n <= 3 else 52
        d.rounded_rectangle([cx - 24, cy - hh, cx + 24, cy + hh], 16, fill=col)
        for k in (-0.55, 0, 0.55): d.rectangle([cx - 29, cy + k * hh - 5, cx + 29, cy + k * hh + 5], fill=col)
        d.line([cx, cy - hh + 10, cx, cy + hh - 10], fill=IVORY, width=6)
    return im

def joker():
    im, d = base(); f = ImageFont.truetype(F + 'Fraunces-SemiBold.ttf', 84)
    d.text((W / 2, H / 2 - 40), 'JOKER', font=f, fill=RED, anchor='mm')
    d.ellipse([W / 2 - 70, H / 2 + 40, W / 2 + 70, H / 2 + 180], outline=GRN, width=12)
    d.text((W / 2, H / 2 + 110), '★', font=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 90), fill=BLU, anchor='mm')
    return im

def frame(im):
    d = ImageDraw.Draw(im); d.rounded_rectangle([6, 6, W - 6, H - 6], 30, outline=(225, 214, 190), width=6)
    return im.filter(ImageFilter.GaussianBlur(0.6))

for n in range(1, 10): frame(dots(n)).save(D + f'tile_dot{n}.png'); frame(bams(n)).save(D + f'tile_bam{n}.png')
frame(joker()).save(D + 'tile_joker.png')

# hand card (generic, not a real league card)
CW, CH = 2400, 3200
im = Image.new('RGB', (CW, CH), (252, 249, 241)); d = ImageDraw.Draw(im)
fb = ImageFont.truetype(F + 'Inter-Bold.ttf', 74); fr = ImageFont.truetype(F + 'Inter-Regular.ttf', 44); fh = ImageFont.truetype(F + 'Fraunces-SemiBold.ttf', 120)
d.text((CW / 2, 150), 'FAMILY TABLE  ·  2026 HANDS', font=fh, fill=(40, 40, 40), anchor='mm')
d.line([120, 260, CW - 120, 260], fill=(60, 60, 60), width=6)
random.seed(7)
y = 360; sections = ['2026', '2468', 'ANY LIKE NUMBERS', 'QUINTS', 'CONSECUTIVE RUN', '13579', 'WINDS - DRAGONS', '369', 'SINGLES AND PAIRS']
for s in sections:
    d.text((140, y), s, font=fb, fill=(30, 30, 30)); y += 110
    for k in range(3):
        x = 160
        groups = random.choice([['FFFF', '2026', '222', '222'], ['22', '444', '666', '8888'], ['111', '2222', '333', '4444'], ['NNNN', 'EW', 'SSSS', '2026'], ['1111', '33', '5555', '7777'], ['333', '666', '6666', '9999']])
        for g in groups:
            col = random.choice([(196, 36, 40), (24, 120, 70), (28, 64, 150)])
            d.text((x, y), g, font=fb, fill=col); x += d.textlength(g, font=fb) + 60
        d.text((CW - 300, y), random.choice(['X 25', 'C 30', 'X 35', 'C 50']), font=fb, fill=(60, 60, 60))
        y += 98
    y += 40
    d.line([140, y - 30, CW - 140, y - 30], fill=(210, 205, 195), width=3)
    if y > CH - 200: break
im.save(D + 'card.png')
print('ok')

# playing cards
SU = {'S': ('♠', (25, 25, 30)), 'H': ('♥', (200, 30, 40)), 'D': ('♦', (200, 30, 40)), 'C': ('♣', (25, 25, 30))}
fs = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 120); fbig = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 420)
fr = ImageFont.truetype(F + 'Fraunces-SemiBold.ttf', 120); fface = ImageFont.truetype(F + 'Fraunces-SemiBold.ttf', 300)
for rank in ['A', 'K', 'Q', 'J', '10', '9', '7', '5', '3']:
    for s in 'SHDC':
        sym, col = SU[s]
        im = Image.new('RGB', (630, 880), (252, 252, 250)); d = ImageDraw.Draw(im)
        d.rounded_rectangle([4, 4, 626, 876], 40, outline=(200, 200, 200), width=4)
        d.text((60, 70), rank, font=fr, fill=col, anchor='mm'); d.text((60, 175), sym, font=fs, fill=col, anchor='mm')
        im2 = im.rotate(180); d2 = ImageDraw.Draw(im2); d2.text((60, 70), rank, font=fr, fill=col, anchor='mm'); d2.text((60, 175), sym, font=fs, fill=col, anchor='mm'); im = im2.rotate(180); d = ImageDraw.Draw(im)
        if rank in 'KQJ':
            d.rounded_rectangle([130, 150, 500, 730], 20, outline=col, width=8)
            d.text((315, 380), rank, font=fface, fill=col, anchor='mm'); d.text((315, 610), sym, font=fs, fill=col, anchor='mm')
        else:
            d.text((315, 450), sym, font=fbig if rank == 'A' else ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 220), fill=col, anchor='mm')
            if rank != 'A': d.text((315, 700), rank, font=fr, fill=col, anchor='mm')
        im.save(D + f'card_{rank}{s}.png')
print('cards ok')
