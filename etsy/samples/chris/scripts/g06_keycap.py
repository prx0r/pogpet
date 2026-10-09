exec(open('/workspace/projects/791a7153-8d05-4c9b-b767-8f281ad46eb0/etsy_samples/geo.py').read())
# Artisan keycap "the 19th hole" - JLC WJP Full Colour resin. 1u, Cherry MX female cross stem.
H = 9.2
bot = ext(rect(18.0, 18.0, r=1.8), 0.01, 0)
topr = ext(rect(13.2, 12.6, 0, 0.6, r=2.6), 0.01, H)
shell = M.batch_hull([bot, topr])
inner = M.batch_hull([ext(rect(15.6, 15.6, r=1.0), 0.01, -0.01), ext(rect(11.0, 10.4, 0, 0.6, r=1.6), 0.01, H - 1.4)])
cap = shell - inner
stem = cyl(2.75, H - 1.0, 0, 0, 0.6, n=64)
cross = ext(rect(4.15, 1.32) + rect(1.32, 4.15), 4.6, -0.01)
cap = (cap + stem) - cross
# top: putting green mound (separate colour region) + cup + flag
mound = M.sphere(1.0, 96).scale((5.9, 5.6, 1.15)).translate((0, 0.6, H)) ^ cyl(20, 3, 0, 0, H, n=4)
cup = cyl(1.05, 2.0, 2.1, -0.9, H + 0.2, n=48)
green = mound - cup
pin = cyl(0.55, 7.2, 2.1, -0.9, H - 0.2, n=32)
pen = poly([(0, 0), (3.6, 1.2), (0, 2.4)]).extrude(0.9).rotate((90, 0, 0)).translate((2.1 + 0.4, 0.45 - 0.9, H + 4.3))
ball = M.sphere(0.85, 48).translate((-2.4, 2.0, H + 1.55))
# front face text: "CHRIS" on the sloped front (y- side). raised 0.5 mm, white on cream -> printed colour in WJP
name2d = text2d('CHRIS', 1.7, font='Inter-Bold.ttf')
slope = math.degrees(math.atan2(H, (18.0 - 12.6) / 2 + 0.6 * 0 + 0.0))
name = name2d.extrude(0.6).rotate((90 - (90 - slope) * 0 , 0, 0))
# place on front face: front face goes from y=-9 (z=0) to y=-5.7 (z=H); centre z=4.2
ang = math.atan2(9.0 - 5.7, H)          # face tilt from vertical
name = name2d.extrude(0.6).rotate((90, 0, 0)).rotate((-math.degrees(ang), 0, 0)).translate((0, -9.0 + 4.6 * math.tan(ang) + 0.35, 4.6))
save({'cap': cap, 'green': green, 'pin': pin, 'pennant': pen, 'ball': ball, 'name': name}, 'p06_keycap',
     print_parts=[cap, green, pin, pen, ball, name])
