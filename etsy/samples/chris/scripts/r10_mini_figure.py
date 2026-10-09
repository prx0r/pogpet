import sys; exec(open('/workspace/projects/791a7153-8d05-4c9b-b767-8f281ad46eb0/etsy_samples/studio.py').read())
reset()
P = 'p10_mini_figure'
CRE = wjp_colour('#f3eee3'); GRN = noise_bump(mat('turf', hexc('#4a9b45'), rough=0.8, coat=0.1), 3.0, 0.5)
WHT = wjp_colour('#fbfbf8'); RED = wjp_colour('#d42a2a'); NAV = wjp_colour('#1d2f55'); BLK = wjp_colour('#141414')
parts = [load_textured(P, rough=0.62, coat=0.12), load_part(P, 'plinth', CRE, 30), load_part(P, 'turf', GRN, 30), load_part(P, 'cup', BLK, 30),
         load_part(P, 'pin', WHT, 30), load_part(P, 'pennant', RED, 30), load_part(P, 'ball', WHT, 30), load_part(P, 'name', NAV, 30)]
place(parts, (0, 0, 0), (0, 0, math.radians(14)))
sw = backdrop('#dfe7ea', size=2000, curve=300); sw.location = (0, 120, 0)
world(0.3, '#ffffff')
light_area((-180, -200, 260), size=220, energy=3.4e5, color=(1, .95, .88))
light_area((220, -80, 140), size=160, energy=1.2e5, color=(.88, .94, 1))
light_area((40, 220, 240), size=240, energy=2.0e5)
cam = Vector((-30, -215, 96))
camera(cam, (0, 0, 33), lens=85, fstop=8, focus=(cam - Vector((0, 0, 40))).length)
go(P)
