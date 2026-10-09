exec(open('/workspace/projects/791a7153-8d05-4c9b-b767-8f281ad46eb0/etsy_samples/geo.py').read())
# Mahjong card line reader - JLC WJP Full Colour resin (jade body, ivory raised art), 165 x 44 x 2.2 mm.
L, W, T = 165.0, 44.0, 2.2
outline = rect(L, W, r=6)
# thumb notches top + bottom centre so it lifts off the card easily
outline = outline - circle(7, 0, W / 2 + 3.2) - circle(7, 0, -W / 2 - 3.2)
plate = chamfered(outline, T, ch=0.5)
slot = rect(146, 8.6, 0, 8.2, r=4.3)                 # reading window: one card line
plate = plate - ext(slot, T + 2, -1)
# window frame lip for stiffness
lip = ext(rect(150, 12.6, 0, 8.2, r=6.3) - slot, 0.8, T - 0.01)
# name + motif raised 0.9 mm (SLA emboss >= 0.8 mm)
name = text2d('CHRIS', 9.0, font='Fraunces-SemiBold.ttf', x=-44, y=-9.5)
tag = text2d("DAD'S TABLE  -  NO PEEKING", 2.6, font='Inter-Bold.ttf', x=36, y=-4.4)
# little tile row icons (5 mini tiles with dots)
icons = CS()
for i in range(5):
    cx = 8 + i * 11.5; cy = -13.6
    t = rect(9.2, 11.5, cx, cy, r=1.6) - rect(7.6, 9.9, cx, cy, r=1.0)
    n = i + 1
    pts = {1: [(0, 0)], 2: [(0, 2.4), (0, -2.4)], 3: [(-2, 2.6), (0, 0), (2, -2.6)], 4: [(-1.8, 2.3), (1.8, 2.3), (-1.8, -2.3), (1.8, -2.3)], 5: [(-1.8, 2.5), (1.8, 2.5), (0, 0), (-1.8, -2.5), (1.8, -2.5)]}[n]
    r = 1.6 if n == 1 else 0.95
    for (dx, dy) in pts: t = t + circle(r, cx + dx, cy + dy, 48)
    icons = icons + t
relief = ext(name + tag.offset(0.05, JoinType.Round) + icons, 0.9, T - 0.01)
body = union([plate, lip])
save({'body': body, 'relief': relief}, 'p02_line_reader', print_parts=[body, relief])
preview2d(name + tag + icons + slot + (outline - outline.offset(-0.6)), OUT + 'p02_line_reader/art.png', 10)
