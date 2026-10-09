import sys; exec(open('/workspace/projects/791a7153-8d05-4c9b-b767-8f281ad46eb0/etsy_samples/studio.py').read())
reset()
P = 'p04_dart_stand'
BLK = mjf_pa12('#232427'); GOLD = mat('gold', hexc('#d7b25a'), rough=0.32, metal=1.0)
st = [load_part(P, 'body', BLK, 30), load_part(P, 'paint', GOLD, 30)]
place(st, (0, 0, 0), (0, 0, math.radians(-8)))
import math as _m
top = 12.0
for (x, y, h), col in zip([(-22, 16, 34), (0, 23, 42), (22, 16, 34)], ['#c8242c', '#127a5a', '#c8242c']):
    a = _m.radians(-8); X = x * _m.cos(a) - y * _m.sin(a); Y = x * _m.sin(a) + y * _m.cos(a)
    dart(X, Y, top + h - 38, col, rz=_m.radians(20 + x))
sw = backdrop('#5d6b7c', size=2200, curve=420); sw.location = (0, 160, 0)
bpy.data.materials['backdrop'].node_tree.nodes['Principled BSDF'].inputs['Roughness'].default_value = 0.95
world(0.25, '#dfe6f2')
light_area((-260, -260, 380), size=320, energy=9e5, color=(1, .94, .85))
light_area((300, -100, 220), size=220, energy=3.2e5, color=(.85, .92, 1))
light_area((0, 260, 420), size=300, energy=4.5e5, color=(1, .9, .8))
cam = Vector((-55, -290, 180))
camera(cam, (0, 8, 70), lens=60, fstop=9, focus=(cam - Vector((0, -10, 20))).length)
go(P)
