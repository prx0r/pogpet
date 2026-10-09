import sys; exec(open('/workspace/projects/791a7153-8d05-4c9b-b767-8f281ad46eb0/etsy_samples/studio.py').read())
reset()
P = 'p02_line_reader'
felt_green(color='#1f4a3b')
bpy.data.materials['green'].node_tree.nodes['Principled BSDF'].inputs['Base Color'].links and None
# hand card
card = decal(PROPS + 'card.png', 150, 200, (0, 8, 0.3), (0, 0, math.radians(-4)), rough=0.7, coat=0.0)
JADE = wjp_colour('#2f8f74'); IVR = wjp_colour('#f4ecd6')
rd = [load_part(P, 'body', JADE, 35), load_part(P, 'relief', IVR, 35)]
place(rd, (10, 3.9, 0.6), (0, 0, math.radians(-4)))
# tiles: a row at the top, a couple scattered
faces = ['tile_dot1', 'tile_bam5', 'tile_dot9', 'tile_joker', 'tile_bam2', 'tile_dot5', 'tile_bam7']
for i, f in enumerate(faces):
    mj_tile(f, -72 + i * 23.2, 132, 0, math.radians(-4), back='#e2a93b')
mj_tile('tile_dot3', 104, 40, 0, math.radians(18), back='#e2a93b'); mj_tile('tile_bam9', 112, 70, 0, math.radians(-12), back='#e2a93b')
mj_tile('tile_joker', -108, -40, 0, math.radians(28), back='#e2a93b')
world(0.35, '#fff6ea')
light_area((-260, -220, 420), size=360, energy=7e5, color=(1, .95, .86))
light_area((320, -80, 220), size=220, energy=1.6e5, color=(.9, .95, 1))
light_area((0, 360, 300), size=320, energy=2.2e5)
cam = Vector((20, -250, 245))
camera(cam, (14, 24, 0), lens=60, fstop=9, focus=(cam - Vector((6, -6, 2))).length)
go(P)
