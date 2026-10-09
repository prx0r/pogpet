exec(open('/workspace/projects/791a7153-8d05-4c9b-b767-8f281ad46eb0/etsy_samples/geo.py').read())
# Dart stand - JLC MJF PA12 nylon (dyed black). 110 mm dartboard plinth, 3 towers with 12 mm x 40 mm bores.
R0, H0 = 55.0, 12.0
base = chamfered(circle(R0, n=240), H0, ch=1.2)
# underside pocket to save powder/cost (open bottom, 2.5 mm walls)
base = base - ext(circle(R0 - 3.5, n=240), H0 - 3.0, -1)
top = H0 - 0.01
# dartboard relief (0.9 mm): rings + 20 segment spokes + bull
rel = CS()
for r_out, w in [(47.5, 1.1), (44.0, 0.9), (29.0, 0.9), (25.5, 0.9)]:
    rel = rel + (circle(r_out, n=240) - circle(r_out - w, n=240))
for i in range(20):
    a = math.radians(i * 18 + 9)
    sp = rect(0.9, 47.5 - 6.5, 0, 6.5 + (47.5 - 6.5) / 2).rotate(math.degrees(a) - 90)
    rel = rel + sp
rel = rel + (circle(6.5) - circle(5.5)) + circle(2.6)
# treble + double band fills (alternate segments raised extra = colour-ready for hand paint)
bands = CS()
for i in range(20):
    if i % 2: continue
    a0, a1 = i * 18 + 9, i * 18 + 27
    def wedge(r1, r2):
        pts = [(r1 * math.cos(math.radians(a)), r1 * math.sin(math.radians(a))) for a in np.linspace(a0, a1, 12)]
        pts += [(r2 * math.cos(math.radians(a)), r2 * math.sin(math.radians(a))) for a in np.linspace(a1, a0, 12)]
        return poly(pts)
    bands = bands + wedge(43.1, 47.5) + wedge(25.5, 28.1)
relief = ext(rel, 0.9, top)
band_m = ext(bands, 0.6, top)
# towers (back), bores 12.4 mm (clearance on 12) x 40 deep, 1 mm lead-in chamfer
T = []
bore_pos = [(-22, 16, 34), (0, 23, 42), (22, 16, 34)]
for (x, y, h) in bore_pos:
    tw = cyl(9.8, h, x, y, top - 0.5, r2=8.4, n=160)
    T.append(tw)
towers = union(T)
bores = union([cyl(6.2, 41, x, y, top + h - 40, n=96) + cyl(6.2, 1.2, x, y, top + h - 0.6, r2=7.2, n=96) for (x, y, h) in bore_pos])
# front banner with raised name
ban = rect(66, 15, 0, -31, r=3)
banner = chamfered(ban, 2.4, ch=0.6, z0=top - 0.2, bottom=False)
name = text2d('CHRIS', 7.4, font='Fraunces-SemiBold.ttf', x=0, y=-29.6)
sub = text2d('180 CLUB', 2.4, font='Inter-Bold.ttf', x=0, y=-36.0)
txt = ext(name + sub.offset(0.05, JoinType.Round), 1.0, top + 2.19)
arc = ext(arc_text2d("DAD'S DARTS", 3.4, 50.9, 270, font='Inter-Bold.ttf', inward=True, gap=0.3), 0.8, top - 0.01)
body = union([base, relief, towers, banner]) - bores
paint = union([band_m, txt, arc])
save({'body': body, 'paint': paint}, 'p04_dart_stand', print_parts=[body, paint])
