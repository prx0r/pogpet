import numpy as np, re, trimesh, manifold3d as m3
from shapely.geometry import LineString, Point, Polygon, MultiPolygon
from shapely.ops import unary_union
svg=open('../files/uploads/oddhobb-canonical-perfect-black.svg').read()
paths=re.findall(r'<path d="([^"]+)"',svg)
def sample(d):
    nums=[float(x) for x in re.findall(r'-?\d+\.?\d*',d)]
    p0=np.array(nums[:2]); pts=[p0]; rest=nums[2:]
    for i in range(0,len(rest),6):
        c1,c2,p3=np.array(rest[i:i+2]),np.array(rest[i+2:i+4]),np.array(rest[i+4:i+6])
        for t in np.linspace(0,1,40)[1:]:
            pts.append((1-t)**3*p0+3*(1-t)**2*t*c1+3*(1-t)*t**2*c2+t**3*p3)
        p0=p3
    return np.array(pts)
SW=26
strokes=unary_union([LineString(sample(d)).buffer(SW/2,resolution=24,cap_style=1,join_style=1) for d in paths])
clip=Point(500,500).buffer(350,resolution=256)
ring=Point(500,500).buffer(350+SW/2,resolution=256).difference(Point(500,500).buffer(350-SW/2,resolution=256))
glyph=unary_union([strokes.intersection(clip),ring])
S=0.05  # mm per svg unit -> ring OD 36.3mm, coin 40mm
def to_mm(poly):  # centre, flip y (svg y down)
    return [(( x-500)*S, (500-y)*S) for x,y in poly.exterior.coords[:-1]], [[((x-500)*S,(500-y)*S) for x,y in r.coords[:-1]] for r in poly.interiors]
def extrude(geom,h):
    gs=geom.geoms if isinstance(geom,MultiPolygon) else [geom]
    out=None
    for g in gs:
        ext,ints=to_mm(g.simplify(0.4))
        cs=m3.CrossSection([ext]+[i for i in ints],m3.FillRule.EvenOdd) if False else m3.CrossSection([ext]+ints)
        e=m3.Manifold.extrude(cs,h)
        out=e if out is None else out+e
    return out
R=20.0; T=3.0; RIM=1.0; REC=0.35; REL=0.35
body=m3.Manifold.cylinder(T,R,R,512).translate((0,0,-T/2))
field=m3.Manifold.cylinder(REC+0.01,R-RIM,R-RIM,512)
body=body-field.translate((0,0,T/2-REC))-field.translate((0,0,-T/2-0.01))
# reeded edge
n=160
g=m3.Manifold.cylinder(T-0.5,0.16,0.16,12).translate((0,0,-(T-0.5)/2))
for i in range(n):
    a=2*np.pi*i/n; body=body-g.translate((R*np.cos(a),R*np.sin(a),0))
gl=extrude(glyph,REL+0.02)
top=gl.translate((0,0,T/2-REC-0.01))
bot=gl.rotate((180,0,0)).translate((0,0,-T/2+REC+0.01))  # glyph is mirror-symmetric; reads correctly from back
def tm(mf):
    me=mf.to_mesh(); return trimesh.Trimesh(np.array(me.vert_properties)[:,:3],np.array(me.tri_verts))
import os; os.makedirs('out',exist_ok=True)
for nm,mf in [('body',body),('glyph_top',top),('glyph_bot',bot)]:
    t=tm(mf); t.export(f'out/{nm}.obj'); print(nm,len(t.faces),t.is_watertight)
whole=tm(body+top+bot); whole.export('out/oddhobb_coin.stl'); whole.export('out/oddhobb_coin.glb')
print('coin',whole.extents.round(2),whole.is_watertight,round(whole.volume/1000,2),'cm3')
