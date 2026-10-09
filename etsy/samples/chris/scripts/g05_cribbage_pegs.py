exec(open('/workspace/projects/791a7153-8d05-4c9b-b767-8f281ad46eb0/etsy_samples/geo.py').read())
# Cribbage peg set - JLC Binder-Jet 316L stainless, polished. Shaft 3.1 mm (sliding fit in 1/8" holes), 14 mm deep.
def shaft():
    s = cyl(1.55, 13.4, 0, 0, 0.6, n=64) + cyl(1.25, 0.6, 0, 0, 0, r2=1.55, n=64)   # chamfered tip
    collar = cyl(3.0, 1.6, 0, 0, 14.0, n=96) + cyl(2.6, 0.5, 0, 0, 15.6, r2=2.0, n=96)
    return s + collar
def golf_ball_top(z0):
    tee = cyl(1.0, 5.0, 0, 0, z0, r2=2.6, n=64) + cyl(2.6, 0.6, 0, 0, z0 + 5.0, r2=2.9, n=64)
    R = 4.3; c = z0 + 5.6 + R - 0.5
    ball = M.sphere(R, 96).translate((0, 0, c))
    # dimples: fibonacci sphere points
    n = 160; dims = []
    for i in range(n):
        y = 1 - 2 * (i + 0.5) / n; r = math.sqrt(1 - y * y); th = math.pi * (3 - math.sqrt(5)) * i
        p = np.array([math.cos(th) * r, math.sin(th) * r, y])
        if p[2] < -0.75: continue
        dims.append(M.sphere(0.5, 16).translate(tuple(p * (R + 0.3) + np.array([0, 0, c]))))
    return union([tee, ball]) - union(dims)
def flag_top(z0, initials='CP'):
    pin = cyl(0.85, 15.0, 0, 0, z0, n=48) + M.sphere(1.1, 24).translate((0, 0, z0 + 15.2))
    pen = poly([(0.4, 0), (8.8, 2.6), (0.4, 5.2)])
    t = text2d(initials, 2.2, font='Inter-Bold.ttf', x=3.6, y=2.6).offset(0.04, JoinType.Round)
    flag = (pen.extrude(1.6) - t.extrude(0.7).translate((0, 0, 1.0))).rotate((90, 0, 0)).translate((0, 0.8, z0 + 9.6))
    return pin + flag
ball_peg = shaft() + golf_ball_top(16.0)
flag_peg = shaft() + flag_top(16.0)
save({'ball_peg': ball_peg, 'flag_peg': flag_peg}, 'p05_cribbage_pegs', print_parts=[ball_peg])
t2 = to_tm(flag_peg); print('flag peg watertight', t2.is_watertight, round(t2.volume, 1), t2.extents.round(2))
t2.export(OUT + 'p05_cribbage_flag_peg.stl')
