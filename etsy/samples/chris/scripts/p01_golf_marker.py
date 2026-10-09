import sys; exec(open('/workspace/projects/791a7153-8d05-4c9b-b767-8f281ad46eb0/etsy_samples/studio.py').read())
FAST = '--fast' in sys.argv
reset()
# ---- Golf ball marker: JLC Binder-Jet 316L stainless, polished. 25 mm dia, 2.4 mm thick, raised 0.5 mm art
D, T, R = 25.0, 2.4, 0.5
coin = cyl(D / 2, T, v=192, name='marker')
mod(coin, 'BEVEL', width=0.45, segments=4, limit_method='ANGLE')
# recessed field inside a raised rim (rim 1.2 wide)
field = cyl(D / 2 - 1.3, 0.35, z=T - 0.35, v=192)
boolean(coin, field, 'DIFFERENCE')
top = T - 0.35
ADD = []
# flag pin + flag + cup
# simpler: build pennant from a cylinder with 3 verts
pen = cyl(2.2, R + 0.05, 1.75, 1.7, top - 0.05, v=3)
pen.rotation_euler = (0, 0, 0); apply(pen)
ADD.append(pen)
# pin as a rounded bar lying flat (relief, not standing)
bar = box(0.8, 7.6, R + 0.05, 0.0, -0.6, top - 0.05)
ADD.append(bar)
hole = cyl(1.6, R + 0.05, 0.0, -4.6, top - 0.05, v=48)
ring = cyl(1.0, R + 0.2, 0.0, -4.6, top - 0.1, v=48)
boolean(hole, ring, 'DIFFERENCE')
ADD.append(hole)
# arched text
t1 = arc_text('CHRIS', 3.0, 7.7, 90, depth=R + 0.05, z=top - 0.05, font='Inter-Bold.ttf', track=1.6)
ADD.append(t1)
t2 = arc_text('PAR IS OPTIONAL', 1.45, 8.75, 270, depth=R + 0.05, z=top - 0.05, inward=True, font='Inter-Bold.ttf', track=1.0)
ADD.append(t2)
# back: small engraved line
t3 = solid_text('LOVE, THE KIDS', 1.6, 0, 0, 0.3, depth=0.32, rot=(math.pi, 0, 0), voxel=0.04)
boolean(coin, t3, 'DIFFERENCE')
coin = join([coin] + ADD); remesh(coin, 0.035)
print('marker dims', coin.dimensions, 'faces', len(coin.data.polygons))
export_stl([coin], OUT + 'p01_golf_marker.stl')
setmat(coin, steel_316(True))
coin.rotation_euler = (math.radians(0), 0, math.radians(-12)); coin.location = (0, 0, 0)

# ---- scene: putting green, ball behind, marker front
felt_green(color='#4c9a44')
ball = golf_ball(21.35, 30, 40, None)
# second marker leaning on ball showing back? keep clean: ball + tee
world(0.8, '#e6eeff')
light_area((-160, -120, 220), size=160, energy=1.6e5, color=(1, .95, .88))
light_area((150, -60, 120), size=120, energy=5e4, color=(.9, .95, 1))
light_area((0, 160, 160), size=200, energy=7e4)
camera((-6, -62, 58), (2, 4, 0), lens=100, fstop=5.6, focus=(Vector((-6,-62,58))-Vector((0,0,1))).length)
if FAST: render('p01_golf_marker_fast', res=(800, 800), samples=48, final=800)
else: render('p01_golf_marker', samples=300)
