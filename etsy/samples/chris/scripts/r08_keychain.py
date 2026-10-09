import sys; exec(open('/workspace/projects/791a7153-8d05-4c9b-b767-8f281ad46eb0/etsy_samples/studio.py').read())
reset()
P = 'p08_keychain'
NAV = wjp_colour('#1d2f55'); WHT = wjp_colour('#f6f3ec')
parts = [load_textured(P, rough=0.62, coat=0.12), load_part(P, 'plate', NAV, 30), load_part(P, 'loop', NAV, 30), load_part(P, 'name', WHT, 30)]
place(parts, (0, 0, 0), (0, 0, math.radians(-12)))
# keys + split ring props
ST = mat('keysteel', hexc('#c7c9cc'), rough=0.25, metal=1.0); BR = brass()
for i, (dx, rz, m_) in enumerate([(22, -30, BR), (30, 10, ST)]):
    k = box(40, 9, 2.0, 0, 0, 0, bevel=0.8); h = cyl(9, 2.0, -22, 0, 0, v=64); kk = join([k, h]); setmat(kk, m_)
    kk.location = (48 + dx * 0.6, 40 + 12 * i, 0.2 + i * 2.2); kk.rotation_euler = (0, 0, math.radians(rz))
sw = backdrop('#efe6da', size=2000, curve=300); sw.location = (0, 140, 0)
world(0.3, '#ffffff')
light_area((-180, -200, 260), size=220, energy=3.0e5, color=(1, .95, .88))
light_area((220, -80, 140), size=160, energy=1.0e5, color=(.88, .94, 1))
light_area((40, 220, 240), size=240, energy=1.6e5)
cam = Vector((-20, -150, 70))
camera(cam, (8, 4, 18), lens=85, fstop=6.3, focus=(cam - Vector((0, 0, 20))).length)
go(P)
