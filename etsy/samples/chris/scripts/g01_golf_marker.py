exec(open('/workspace/projects/791a7153-8d05-4c9b-b767-8f281ad46eb0/etsy_samples/geo.py').read())
# Golf ball marker - JLC CNC 6061 aluminium, black anodised, laser-etched artwork (both faces).
D, T = 24.0, 2.0  # template contract: dia 24, thickness 2.0
body = chamfered(circle(D / 2), T, ch=0.3)
# shallow 0.25 mm dished field inside a 1.1 mm rim (machined step catches light)
body = body - ext(circle(D / 2 - 1.4), 0.3, T - 0.2)
top = T - 0.2
art = CS()
art = art + rect(0.7, 8.0, -0.9, -0.55, r=0.3)                               # pin
art = art + poly([(-0.55, 3.6), (4.2, 2.1), (-0.55, 0.6)])                   # pennant
art = art + circle(1.0, -0.9, -4.6).scale((1, 1)).translate((0, 0)).__class__.circle(1.0, 96).scale((2.4, 0.85)).translate((-0.9, -4.6))  # cup
art = art + (CS.circle(1.0, 96).scale((4.6, 1.75)).translate((-0.9, -4.6)) - CS.circle(1.0, 96).scale((4.0, 1.25)).translate((-0.9, -4.6)))  # green ring
art = art + arc_text2d('CHRIS', 2.9, 7.65, 90, font='Inter-Bold.ttf', gap=0.15)
art = art + arc_text2d('PAR IS OPTIONAL', 1.5, 8.45, 270, font='Inter-Bold.ttf', inward=True, gap=0.18)
art = art + circle(0.4, -8.6, 0.0) + circle(0.4, 8.6, 0.0)
laser_top = ext(art, 0.03, top - 0.01)
back = text2d('LOVE,', 1.9, y=2.6) + text2d('THE KIDS', 1.9, y=0.0) + text2d('XMAS 2026', 1.3, y=-2.8, font='Inter-Regular.ttf') + (circle(9.2) - circle(8.85))
laser_back = ext(back.mirror((1, 0)), 0.03, -0.02)
save({'marker': body, 'laser_top': laser_top, 'laser_back': laser_back}, 'p01_golf_marker', print_parts=[body])
preview2d(art, OUT + 'p01_golf_marker/art_front.png', 60); preview2d(back, OUT + 'p01_golf_marker/art_back.png', 60)
