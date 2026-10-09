"""Robust CAD for OddHobb samples: manifold3d (exact, watertight) + matplotlib glyphs.
Units mm, Z up. Blender is only used to render the results."""
import math, os, json
import numpy as np
import manifold3d as mf
from manifold3d import Manifold as M, CrossSection as CS, FillRule, JoinType
from matplotlib.textpath import TextPath
from matplotlib.font_manager import FontProperties
import trimesh

ROOT = '/workspace/projects/791a7153-8d05-4c9b-b767-8f281ad46eb0'
FONTS = ROOT + '/pogpet/assets/fonts/'
OUT = ROOT + '/etsy_samples/out/'
os.makedirs(OUT, exist_ok=True)
mf.set_circular_segments(160) if hasattr(mf, 'set_circular_segments') else None

def _fp(font):
    p = font if font.startswith('/') else FONTS + font
    return FontProperties(fname=p)

def glyphs(s, size, font='Inter-Bold.ttf'):
    """CrossSection of text, baseline-left at origin, cap height ~ size*0.72"""
    tp = TextPath((0, 0), s, size=size, prop=_fp(font))
    polys = [np.asarray(p, float) for p in tp.to_polygons(closed_only=True) if len(p) >= 3]
    if not polys: return CS()
    polys = [p[:-1] if np.allclose(p[0], p[-1]) else p for p in polys]
    from shapely.geometry import Polygon, Point
    sp = [Polygon(p).buffer(0) for p in polys]
    fill, hole = [], []
    for i, p in enumerate(polys):
        if sp[i].is_empty: continue
        rp = sp[i].representative_point()
        depth = sum(1 for j in range(len(polys)) if j != i and sp[j].area > sp[i].area and sp[j].contains(rp))
        c = CS([p], FillRule.NonZero)
        if c.area() == 0: c = CS([p[::-1]], FillRule.NonZero)
        (fill if depth % 2 == 0 else hole).append(c)
    out = CS.batch_boolean(fill, mf.OpType.Add) if fill else CS()
    if hole: out = out - CS.batch_boolean(hole, mf.OpType.Add)
    return out

def bounds2(cs):
    b = cs.bounds(); return b  # (xmin, ymin, xmax, ymax)

def center2(cs, x=0, y=0):
    b = cs.bounds(); return cs.translate(((x - (b[0] + b[2]) / 2), (y - (b[1] + b[3]) / 2)))

def text2d(s, height, font='Inter-Bold.ttf', x=0, y=0, maxw=None, track=0.0):
    """centered text; height = cap height in mm (measured)."""
    if track:
        cs = CS(); cur = 0.0
        for ch in s:
            if ch == ' ':
                cur += height * 0.35; continue
            g = glyphs(ch, 10, font); b = g.bounds()
            if b[2] - b[0] <= 0: continue
            cs = cs + g.translate((cur - b[0], 0)); cur += (b[2] - b[0]) + track * 10
    else:
        cs = glyphs(s, 10, font)
    b = cs.bounds()
    ref = glyphs('H', 10, font).bounds(); capt = ref[3] - ref[1]
    k = height / capt
    cs = cs.scale((k, k)); b = cs.bounds()
    if maxw and (b[2] - b[0]) > maxw:
        f = maxw / (b[2] - b[0]); cs = cs.scale((f, f))
    return center2(cs, x, y)

def arc_text2d(s, height, radius, center_deg=90, font='Inter-Bold.ttf', inward=False, gap=0.12):
    """letters on a circle; top arc reads clockwise, inward=True bottom arc reads left-to-right"""
    ref = glyphs('H', 10, font).bounds(); k = height / (ref[3] - ref[1])
    items = []
    for ch in s:
        if ch == ' ': items.append((None, height * 0.38)); continue
        g = glyphs(ch, 10, font).scale((k, k)); b = g.bounds()
        g = g.translate((-(b[0] + b[2]) / 2, -(ref[1] * k + ref[3] * k) / 2)); items.append((g, b[2] - b[0]))
    total = sum(w for _, w in items) + gap * height * (len(items) - 1)
    cur = -total / 2; out = CS()
    for g, w in items:
        mid = cur + w / 2; cur += w + gap * height
        if g is None: continue
        if not inward:
            th = math.radians(center_deg) - mid / radius; rot = math.degrees(th) - 90
        else:
            th = math.radians(center_deg) + mid / radius; rot = math.degrees(th) + 90
        out = out + g.rotate(rot).translate((radius * math.cos(th), radius * math.sin(th)))
    return out

def circle(r, x=0, y=0, n=180): return CS.circle(r, n).translate((x, y))
def rect(w, h, x=0, y=0, r=0):
    c = CS.square((w, h), True).translate((x, y))
    r = min(r, min(w, h) / 2 - 0.02)
    if r > 0: c = c.offset(-r, JoinType.Round).offset(r, JoinType.Round)
    return c
def poly(pts): return CS([np.asarray(pts, float)], FillRule.NonZero)

def ext(cs, h, z0=0.0, scale_top=None):
    m = cs.extrude(h, scale_top=scale_top) if scale_top else cs.extrude(h)
    return m.translate((0, 0, z0))

def chamfered(cs, h, ch=0.4, z0=0.0, top=True, bottom=True):
    """extrude with 45-degree chamfers (offset-based, works for any outline)"""
    parts = []
    zb = z0; zt = z0 + h
    core_b = zb + (ch if bottom else 0); core_t = zt - (ch if top else 0)
    parts.append(ext(cs, core_t - core_b, core_b))
    steps = 4
    for i in range(steps):
        d = ch * (i + 1) / steps; hh = ch / steps
        inner = cs.offset(-d, JoinType.Round)
        if inner.is_empty(): continue
        if top: parts.append(ext(inner.offset(0), hh + 1e-3, core_t + ch * i / steps))
        if bottom: parts.append(ext(inner, hh + 1e-3, core_b - ch * (i + 1) / steps))
    return M.batch_boolean(parts, mf.OpType.Add)

def rounded_box(sx, sy, sz, r=1.0, x=0, y=0, z=0):
    """box with all edges rounded r (minkowski with sphere)"""
    core = M.cube((sx - 2 * r, sy - 2 * r, sz - 2 * r), True)
    s = M.sphere(r, 24)
    return core.minkowski_sum(s).translate((x, y, z + sz / 2))

def cyl(r, h, x=0, y=0, z=0, r2=None, n=160):
    return M.cylinder(h, r, r if r2 is None else r2, n).translate((x, y, z))

def union(ms): return M.batch_boolean([m for m in ms if not m.is_empty()], mf.OpType.Add)

def to_tm(m):
    mesh = m.to_mesh(); return trimesh.Trimesh(np.asarray(mesh.vert_properties)[:, :3], np.asarray(mesh.tri_verts), process=False)

def save(parts, name, print_parts=None):
    """parts: dict partname -> Manifold (render). writes OUT/name/<part>.obj + name.stl (print union)"""
    d = OUT + name + '/'; os.makedirs(d, exist_ok=True)
    meta = {}
    for k, m in parts.items():
        t = to_tm(m); t.export(d + k + '.obj'); meta[k] = dict(tris=len(t.faces), watertight=bool(t.is_watertight), vol=round(float(t.volume) / 1000, 3), ext=[round(float(x), 2) for x in t.extents])
    pp = print_parts if print_parts is not None else list(parts.values())
    u = union(pp); t = to_tm(u); t.export(OUT + name + '.stl')
    meta['_print'] = dict(tris=len(t.faces), watertight=bool(t.is_watertight), bodies=len(t.split(only_watertight=False)), vol_cm3=round(float(t.volume) / 1000, 3), ext_mm=[round(float(x), 2) for x in t.extents], status=str(u.status()))
    json.dump(meta, open(d + 'meta.json', 'w'), indent=1); print(name, json.dumps(meta['_print']))
    return meta

def preview2d(cs, path, px=20):
    from PIL import Image, ImageDraw
    b = cs.bounds(); w = int((b[2] - b[0]) * px) + 20; h = int((b[3] - b[1]) * px) + 20
    im = Image.new('L', (w, h), 255); d = ImageDraw.Draw(im)
    polys = cs.to_polygons()
    # even-odd fill via XOR layering
    import numpy as np
    acc = np.zeros((h, w), bool)
    for p in polys:
        m = Image.new('1', (w, h), 0); ImageDraw.Draw(m).polygon([((x - b[0]) * px + 10, h - ((y - b[1]) * px + 10)) for x, y in p], fill=1)
        acc ^= np.asarray(m, bool)
    Image.fromarray(np.where(acc, 0, 255).astype('uint8')).save(path)

def chris_manifold(height_mm=70.0):
    """Chris textured mesh -> Manifold with UV props (x,y,z,u,v), Z-up, feet at z=0, centred. Returns (manifold, texture PIL)"""
    s = trimesh.load(ROOT + '/chris/chris_prior_mesh.glb'); g = list(s.geometry.values())[0]
    V = np.asarray(g.vertices, np.float64); F = np.asarray(g.faces, np.int64); UV = np.asarray(g.visual.uv, np.float64)
    V = V[:, [0, 2, 1]] * np.array([1, -1, 1])          # Y-up -> Z-up (x, -z, y)
    k = height_mm / (V[:, 2].max() - V[:, 2].min()); V = V * k
    V[:, 0] -= (V[:, 0].max() + V[:, 0].min()) / 2; V[:, 1] -= (V[:, 1].max() + V[:, 1].min()) / 2; V[:, 2] -= V[:, 2].min()
    # merge vectors for seam duplicates
    key = np.round(V, 5); _, first, inv = np.unique(key, axis=0, return_index=True, return_inverse=True)
    inv = inv.reshape(-1); rep = first[inv]; mask = rep != np.arange(len(V))
    props = np.hstack([V, UV]).astype(np.float32)
    mesh = mf.Mesh(vert_properties=props, tri_verts=F.astype(np.uint32),
                   merge_from_vert=np.nonzero(mask)[0].astype(np.uint32), merge_to_vert=rep[mask].astype(np.uint32))
    m = M(mesh); tex = g.visual.material.baseColorTexture
    return m, tex

def save_textured(m, tex, path_obj):
    """write manifold with uv props as OBJ+MTL+PNG"""
    mesh = m.to_mesh(); P = np.asarray(mesh.vert_properties); T = np.asarray(mesh.tri_verts)
    vis = trimesh.visual.TextureVisuals(uv=P[:, 3:5], image=tex)
    t = trimesh.Trimesh(P[:, :3], T, visual=vis, process=False); t.export(path_obj)
    d = os.path.dirname(path_obj)
    for f in os.listdir(d):
        if f.endswith('.mtl'):
            s = open(os.path.join(d, f)).read()
            s = s.replace('Kd 0.40000000 0.40000000 0.40000000', 'Kd 1.0 1.0 1.0'); open(os.path.join(d, f), 'w').write(s)
    return t
