import sys, json; exec(open('/workspace/projects/791a7153-8d05-4c9b-b767-8f281ad46eb0/etsy_samples/studio.py').read())
reset()
P = 'p05_cribbage_pegs'
HP = json.load(open(OUT + 'p05_board/holes.json'))
bd = [load_part('p05_board', 'board', walnut(), 40), load_part('p05_board', 'inlay', mat('brassin', hexc('#c9a24e'), rough=0.3, metal=1), 30)]
for o in bd: o.location.z = -18
ST = mat('316sat', hexc('#cfd2d6'), rough=0.16, metal=1.0)
# pegs in holes: shaft bottom 14 mm below board top (z=0 now)
picks_ball = [HP[33], HP[38], HP[7]]     # track 2 front, track1
picks_flag = [HP[64], HP[69], HP[66]]
for (x, y) in picks_ball[:2]: load_part(P, 'ball_peg', ST, 35, loc=(x, y, -14.0), rot=(0, 0, 0))
for (x, y) in picks_flag[:2]: load_part(P, 'flag_peg', ST, 35, loc=(x, y, -14.0), rot=(0, 0, math.radians(-15)))
# spare pegs lying on the board
load_part(P, 'ball_peg', ST, 35, loc=(-112, -28, 3.0), rot=(math.radians(90), 0, math.radians(100)))
load_part(P, 'flag_peg', ST, 35, loc=(-50, -30, 3.0), rot=(math.radians(90), math.radians(0), math.radians(-110)))
sw = backdrop('#e8e0d2', size=2000, curve=300); sw.location = (0, 140, -18)
world(0.3, '#fff6ea')
light_area((-220, -220, 300), size=260, energy=4.0e5, color=(1, .95, .86))
light_area((260, -80, 160), size=180, energy=1.2e5, color=(.9, .95, 1))
light_area((0, 240, 240), size=260, energy=1.6e5)
reflector((0, -120, 140), (0, 0, 0), 260, 110, 2.0)
tx, ty = -80, -6
cam = Vector((tx - 40, ty - 175, 110))
camera(cam, (tx + 4, ty - 6, 8), lens=100, fstop=5.6, focus=(cam - Vector((tx - 4, ty - 4, 12))).length)
go(P)
