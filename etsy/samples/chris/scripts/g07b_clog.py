exec(open('/workspace/projects/791a7153-8d05-4c9b-b767-8f281ad46eb0/etsy_samples/geo.py').read())
# prop: section of a clog upper - curved foam shell 5 mm with 10 mm vent holes
Rr = 70.0
shell = (cyl(Rr, 140, 0, 0, -70, n=240) - cyl(Rr - 5, 142, 0, 0, -71, n=240)).rotate((0, 90, 0))   # axis along X
shell = shell ^ M.cube((140, 140, 80), True).translate((0, 0, Rr - 30))
holes = []
for i, x in enumerate([-44, -22, 0, 22, 44]):
    for j, a in enumerate([-24, -8, 8, 24]):
        ang = math.radians(a + (8 if i % 2 else 0))
        h = cyl(5.0, 20, 0, 0, -10, n=48).rotate((math.degrees(-ang), 0, 0)).translate((x, Rr * math.sin(ang), Rr * math.cos(ang)))
        holes.append(h)
shell = shell - union(holes)
save({'clog': shell}, 'p07_clog')
