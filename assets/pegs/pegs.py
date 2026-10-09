# Cribbage peg masters per HANDOVER spec: shaft 3.1 mm (sliding fit 1/8in holes), manifold, mm units
import manifold3d as m3, numpy as np, trimesh
def rev(profile, n=96):  # profile: list of (r,z) closed polygon in r>=0 half-plane
    return m3.Manifold.revolve(m3.CrossSection([profile]), n)
def tm(mf):
    me=mf.to_mesh(); return trimesh.Trimesh(np.array(me.vert_properties)[:,:3],np.array(me.tri_verts))
SH=1.55  # shaft radius (3.1 mm)
# peg_classic: 14 mm shaft, chamfered tip, collar, taper, 6 mm ball
classic=rev([(0,0),(SH-0.35,0),(SH,0.4),(SH,14),(2.6,14),(2.6,15.2),(1.9,15.6),(1.5,19.5),(0,19.5)]) + m3.Manifold.sphere(3.0,96).translate((0,0,21.6))
# peg_ball: shaft + collar + oversized 9 mm ball
ball=rev([(0,0),(SH-0.35,0),(SH,0.4),(SH,14),(2.4,14),(2.4,15),(1.8,15.4),(0,15.4)]) + m3.Manifold.sphere(4.5,128).translate((0,0,19.0))
# peg_topper_mount: shaft + collar + 10 mm OD cup (8.4 ID, 3 mm deep) for a mini bust topper
cup=rev([(0,0),(SH-0.35,0),(SH,0.4),(SH,14),(2.6,14),(2.6,14.8),(5.0,16.2),(5.0,19.6),(0,19.6)])
cup=cup-m3.Manifold.cylinder(3.2,4.2,4.2,96).translate((0,0,16.6))
for n,mf in [('peg_classic',classic),('peg_ball',ball),('peg_topper_mount',cup)]:
    t=tm(mf); t.export(f'{n}.stl'); print(n,t.is_watertight,t.extents.round(2),round(t.volume,1),'mm3')
