import trimesh,numpy as np,sys
from shapely.ops import unary_union
scale=float(sys.argv[1]); nozzle=0.4; lh=0.2
for k in ['pyjama','dress']:
    m=trimesh.load(f'prod/brick-figure-{k}-PLA.stl'); m.apply_scale(scale)
    zs=np.arange(lh/2,m.bounds[1,2],lh); bad=0; lost=0; tot=0; worst=[]
    secs=m.section_multiplane(plane_origin=[0,0,0],plane_normal=[0,0,1],heights=list(zs))
    for z,s in zip(zs,secs):
        if s is None: bad+=1; continue
        polys=[p for p in s.polygons_full]
        if not polys: bad+=1; continue
        P=unary_union(polys); tot+=P.area
        # area that a 0.4mm nozzle can't fill with >=2 lines: opening by nozzle width
        kept=P.buffer(-nozzle).buffer(nozzle); l=P.area-kept.area; lost+=l
        if l>0.3: worst.append((round(z,1),round(l,2)))
    print(f'{k} x{scale}: height {m.extents[2]:.1f}mm layers {len(zs)} empty/open {bad} unprintable-at-0.8mm {100*lost/tot:.1f}% of layer area; worst z:',sorted(worst,key=lambda t:-t[1])[:5])
