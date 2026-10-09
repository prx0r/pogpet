import sys; exec(open('/workspace/projects/791a7153-8d05-4c9b-b767-8f281ad46eb0/etsy_samples/studio.py').read())
reset()
P = 'p09_ornament'
RED = wjp_colour('#c8202a'); WHT = noise_bump(mat('fur', hexc('#f7f5f0'), rough=0.85, sss=0.1), 6, 0.6); GLD = mat('gold', hexc('#d4af5a'), rough=0.25, metal=1.0)
parts = [load_textured(P, rough=0.62, coat=0.12), load_part(P, 'hat', RED, 35), load_part(P, 'brim', WHT, 35), load_part(P, 'pom', WHT, 35), load_part(P, 'loop', RED, 35)]
# hang it: ribbon from above through the loop
e = place(parts, (0, 0, 40), (0, 0, math.radians(10)))
import json
lz = 40 + 72 + 0
rib = box(3, 0.4, 400, 0, 0, 40 + 81.0, name='ribbon'); setmat(rib, mat('ribbon', hexc('#a3121c'), rough=0.6, sss=0.1))
bg = decal(PROPS + 'bokeh_xmas.png', 900, 900, (0, 600, 80), (math.radians(90), 0, 0))
m = bg.data.materials[0]; nt = m.node_tree; b_ = nt.nodes['Principled BSDF']; tx = [n for n in nt.nodes if n.type == 'TEX_IMAGE'][0]
em = nt.nodes.new('ShaderNodeEmission'); em.inputs['Strength'].default_value = 1.0; nt.links.new(tx.outputs['Color'], em.inputs['Color'])
nt.links.new(em.outputs[0], nt.nodes['Material Output'].inputs['Surface']); bg.visible_shadow = False
world(0.15, '#203028')
light_area((-160, -200, 220), size=200, energy=2.6e5, color=(1, .93, .82))
light_area((200, -100, 160), size=150, energy=1.0e5, color=(1, .85, .7))
light_area((0, 120, 200), size=200, energy=0.9e5, color=(.9, .95, 1))
cam = Vector((-14, -210, 92))
camera(cam, (0, 0, 84), lens=85, fstop=2.8, focus=(cam - Vector((0, 0, 80))).length)
go(P)
