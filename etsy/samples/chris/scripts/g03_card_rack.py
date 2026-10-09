exec(open('/workspace/projects/791a7153-8d05-4c9b-b767-8f281ad46eb0/etsy_samples/geo.py').read())
# Playing-card hand rack, 3 tiers - JLC MJF PA12 nylon, dyed black, bead-blasted + JLC spray paint option.
# Name panel is a separate WJP full-colour inlay? No: kept single-part for cost -> engraved 1.0 mm, paint-filled look in render.
L, Dp = 200.0, 62.0   # template contract: length >= 200, grooves 2.5 mm
# side profile in (y, z): y front=-31 .. back=+31
G = 2.5  # groove width per contract
prof = [(-31, 0), (31, 0), (31, 30), (27, 34), (17, 34),   # back block top
        (17, 18), (17 - G, 18),                            # groove 3
        (17 - G, 25), (2, 25),                             # tier 2 top
        (2, 10), (2 - G, 10),                              # groove 2
        (2 - G, 16), (-13, 16),                            # tier 1 top
        (-13, 4), (-13 - G, 4),                            # groove 1
        (-13 - G, 10), (-29, 10), (-31, 8)]
sect = CS([np.array(prof, float)], FillRule.NonZero)
if sect.area() == 0: sect = CS([np.array(prof[::-1], float)], FillRule.NonZero)
body = sect.extrude(L).rotate((90, 0, 90)).translate((-L / 2, 0, 0))   # profile YZ, extrude along X
# round the plan corners: intersect with rounded footprint
foot = ext(rect(L, Dp, r=8), 40, -1)
body = body ^ foot
# open-bottom shell: 2.5 mm walls, powder escapes through the open underside (no trapped volume)
inner = sect.offset(-2.5, JoinType.Miter) + rect(Dp - 5, 8, 0, -1)
inner = inner ^ rect(Dp - 5, 80, 0, 37.5)          # keep z >= -2 .. inside
cav = inner.extrude(L - 5).rotate((90, 0, 90)).translate((-(L - 5) / 2, 0, 0))
ribs = union([ext(rect(2.4, Dp, x, 0), 40, -1) for x in (-47, 0, 47)])
body = body - (cav - ribs)
# tilt grooves are vertical (cards lean back on the step face) - fine for MJF, no supports needed.
# engraved name on front face (y = -31 plane, z 1..9)
name = text2d('CHRIS', 6.2, font='Fraunces-SemiBold.ttf', x=0, y=5.0)
suits = CS()
for i, (ch, x) in enumerate([('♠', -62), ('♥', -50), ('♦', 50), ('♣', 62)]):
    suits = suits + text2d(ch, 4.6, font='/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', x=x, y=5.0)
eng2d = name + suits
eng = eng2d.extrude(1.4).rotate((90, 0, 0)).translate((0, -31 + 1.0, 0))  # cut 1.0 into front face
body = body - eng
inlay = eng2d.offset(-0.05, JoinType.Round).extrude(0.95).rotate((90, 0, 0)).translate((0, -31 + 1.0 - 0.0, 0))
save({'rack': body, 'fill': inlay}, 'p03_card_rack', print_parts=[body])
