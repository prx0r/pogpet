import sys; exec(open('/workspace/projects/791a7153-8d05-4c9b-b767-8f281ad46eb0/etsy_samples/studio.py').read())
reset()
P = 'p01_golf_marker'
AN, LZ = anodised(), laser_mark()
A = [load_part(P, 'marker', AN, 30), load_part(P, 'laser_top', LZ, 30), load_part(P, 'laser_back', LZ, 30)]
place(A, (4, -4, 0), (0, 0, math.radians(-4)))
B = [load_part(P, 'marker', AN, 30), load_part(P, 'laser_top', LZ, 30), load_part(P, 'laser_back', LZ, 30)]
place(B, (-22, 20, 2.0), (math.radians(180), 0, math.radians(185)))
sw = backdrop('#ece6db', size=1500, curve=260); sw.location = (0, 80, 0)
ball = golf_ball(21.35, 28, 30, None)
world(0.25, '#ffffff')
light_area((-150, -130, 230), size=180, energy=1.5e5, color=(1, .96, .9))
light_area((170, -40, 120), size=120, energy=4.0e4, color=(.92, .96, 1))
light_area((-30, 200, 180), size=220, energy=6e4)
reflector((0, -70, 150), (0, 0, 0), 260, 120, 2.0)
cam = Vector((-8, -78, 100))
camera(cam, (-4, 8, 2), lens=85, fstop=8, focus=(cam - Vector((0, 0, 2))).length)
go(P)
