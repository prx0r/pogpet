exec(open('/workspace/projects/791a7153-8d05-4c9b-b767-8f281ad46eb0/etsy_samples/geo.py').read())
import json
# Mesh lines (face_swap): template = canonical figure GLB; Chris's textured mesh replaces it. JLC WJP Full Colour.
import sys
which = sys.argv[1:] or ['figure', 'ornament', 'keychain']

def head_info(m):
    P = np.asarray(m.to_mesh().vert_properties)[:, :3]; H = P[:, 2].max()
    hp = P[P[:, 2] > H * 0.90]
    c = hp[:, :2].mean(0); r = np.percentile(np.linalg.norm(hp[:, :2] - c, axis=1), 95)
    return H, c, r

def write_parts(name, textured, parts, tex):
    d = OUT + name + '/'; os.makedirs(d, exist_ok=True)
    save_textured(textured, tex, d + 'chris.obj')
    meta = {}
    for k, v in parts.items(): to_tm(v).export(d + k + '.obj')
    allp = union([textured] + list(parts.values()))
    t = to_tm(allp); t.merge_vertices(digits_vertex=5); t = trimesh.Trimesh(t.vertices, t.faces, process=True)
    bs = [b for b in t.split(only_watertight=False) if abs(b.volume) > 1.0]; t = trimesh.util.concatenate(bs); t.export(OUT + name + '.stl')
    info = dict(watertight=bool(t.is_watertight), bodies=len(t.split(only_watertight=False)), vol_cm3=round(float(t.volume) / 1000, 2), ext_mm=[round(float(x), 2) for x in t.extents])
    json.dump(info, open(d + 'meta.json', 'w')); print(name, info)

if 'figure' in which:
    # p10 Mini-Me desk figure: 75 mm overall, Chris 66 mm on a 46 mm putting-green plinth
    ch, tex = chris_manifold(66.0); ch = ch.translate((0, 0, 7.25))
    plinth = chamfered(circle(23, n=200), 6.0, ch=0.8, top=False)
    turf = ext(circle(22.2, n=200), 1.6, 6.0)
    cup = cyl(2.6, 2.0, 11.5, -9.0, 6.4, n=64)
    turf = turf - cup
    cupw = cyl(2.6, 0.3, 11.5, -9.0, 6.3, n=64)
    pin = cyl(0.75, 26.2, 11.5, -9.0, 6.2, n=32)
    pen = poly([(0, 0), (8.5, 2.8), (0, 5.6)]).extrude(1.2).rotate((90, 0, 0)).translate((11.5 + 0.6, 0.6 - 9.0, 6.4 + 19.6))
    ball = M.sphere(1.9, 64).translate((-12.5, -11.0, 7.6 + 1.9 - 0.3))
    # name band on the plinth wall: raised letters following the cylinder (flat-approx on front)
    name = text2d('CHRIS', 3.6, font='Fraunces-SemiBold.ttf').extrude(3.2).rotate((90, 0, 0)).translate((0, -20.4, 2.9))
    name = name ^ (cyl(23.6, 8, 0, 0, -1, n=200))
    write_parts('p10_mini_figure', ch, {'plinth': plinth, 'turf': turf, 'cup': cupw, 'pin': pin, 'pennant': pen, 'ball': ball, 'name': name}, tex)

if 'ornament' in which:
    # p09 Christmas ornament: Chris 72 mm + Santa hat + printed hanging loop (hole 5.0 mm, wire 2.4 mm per template)
    ch, tex = chris_manifold(72.0)
    H, c, r = head_info(ch)
    hr = r * 1.08; zb = H - 4.6
    brim = M.cylinder(2.6, hr * 1.06, hr * 1.06, 120).translate((c[0], c[1], zb))
    brim = brim.minkowski_sum(M.sphere(0.9, 16)) if False else brim
    cone = M.cylinder(r * 2.3, hr * 0.98, 1.2, 96).translate((c[0], c[1], zb + 2.0))
    # flop the tip sideways: warp verts above brim
    def flop(v):
        z = v[2] - (zb + 2.0)
        if z > 0:
            t = z / (r * 2.3); v[0] += (t ** 2) * r * 1.3; v[2] -= (t ** 2) * r * 0.6
        return v
    cone = cone.refine(4).warp(flop)
    tipx = c[0] + r * 1.3; tipz = zb + 2.0 + r * 2.3 - r * 0.6
    pom = M.sphere(2.4, 48).translate((tipx - 0.9, c[1], tipz - 0.6))
    hat_red = cone - M.cylinder(2.7, hr * 1.2, hr * 1.2, 96).translate((c[0], c[1], zb - 0.05))
    # loop through the top of the hat (hole 5.0 / wire 2.4 -> torus R=3.7, r=1.2)
    R_t, r_t = 2.5 + 1.2, 1.2
    top_z = zb + 2.0 + r * 1.2
    loop = M.revolve(CS.circle(r_t, 32).translate((R_t, 0)), 64).rotate((90, 0, 0)).translate((c[0] + r * 0.25, c[1], top_z + 1.6 + R_t))
    stalk = cyl(1.3, 2.6, c[0] + r * 0.25, c[1], top_z - 0.6, n=32)
    write_parts('p09_ornament', ch, {'brim': brim, 'hat': hat_red, 'pom': pom, 'loop': loop + stalk}, tex)

if 'keychain' in which:
    # p08 keychain: Chris bust (head + shoulders) 40 mm, printed loop (ring hole 4.0 per template), name plinth
    ch, tex = chris_manifold(230.0)        # big, then trim & scale so the bust is ~40 mm
    H, c, r = head_info(ch)
    zcut = H - 230.0 * 0.205
    bust = ch.trim_by_plane((0, 0, 1), zcut).translate((0, 0, -zcut))
    bb = bust.bounding_box(); k = 34.0 / (bb[5] - bb[2]); bust = bust.scale((k, k, k)).translate((0, 0, 4.0))
    bb = bust.bounding_box()
    yc = (bb[1] + bb[4]) / 2 - 3.0
    plate = chamfered(rect(bb[3] - bb[0] + 4, 19, 0, yc, r=3), 4.2, ch=0.6)
    P = np.asarray(bust.to_mesh().vert_properties)[:, :3]; Ht = P[:, 2].max()
    hp = P[P[:, 2] > Ht - 3]; hc = hp[:, :2].mean(0)
    R_t, r_t = 2.0 + 1.3, 1.3
    loop = M.revolve(CS.circle(r_t, 32).translate((R_t, 0)), 64).rotate((90, 0, 0)).translate((hc[0], hc[1], Ht + R_t + 0.2))
    tag = text2d('CHRIS', 3.4, font='Inter-Bold.ttf').extrude(0.8).rotate((90, 0, 0)).translate((0, yc - 9.5 + 0.4, 2.1))
    write_parts('p08_keychain', bust, {'plate': plate, 'loop': loop, 'name': tag}, tex)
