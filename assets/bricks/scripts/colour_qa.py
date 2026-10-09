import numpy as np,trimesh,sys
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components
sys.path.insert(0,'.'); from paint_map import PAL
lh=0.2
for k in ['pyjama','dress']:
    m=trimesh.load(f'prod/brick-figure-{k}-PLA-sub.stl',process=False); m.merge_vertices(); lab=np.load(f'prod/paint_{k}'+(sys.argv[1] if len(sys.argv)>1 else '')+'.npy')
    print(k,'watertight',m.is_watertight,'winding',m.is_winding_consistent,'bodies',m.body_count,'vol %.0f mm3 (~%.1f g PLA)'%(m.volume,m.volume*1.24/1000),'extent',m.extents.round(1))
    adj=m.face_adjacency; same=lab[adj[:,0]]==lab[adj[:,1]]; a=adj[same]
    G=coo_matrix((np.ones(len(a)),(a[:,0],a[:,1])),shape=(len(lab),)*2)
    n,cc=connected_components(G,directed=False)
    A=m.area_faces; ia=np.bincount(cc,A); icol=np.zeros(n,int); icol[cc]=lab
    # island size as equivalent diameter
    d=2*np.sqrt(ia/np.pi)
    print('  colour islands',n)
    for c in range(len(PAL)):
        s=icol==c
        if not s.any(): continue
        tiny=s&(d<0.4); small=s&(d>=0.4)&(d<0.8)
        print(f'   {PAL[c][0]:10s} area {A[lab==c].sum():7.1f} mm2  islands {s.sum():5d}  <0.4mm {tiny.sum():5d} ({ia[tiny].sum():.1f} mm2)  0.4-0.8mm {small.sum():4d} ({ia[small].sum():.1f} mm2)')
    # colour changes per layer
    C=m.triangles_center; L=(C[:,2]//lh).astype(int); nl=L.max()+1
    cols=[set(lab[L==i]) for i in range(nl)]
    nc=np.array([len(c) for c in cols]); swaps=sum(max(len(c)-1,0) for c in cols)
    print(f'  layers {nl}, colours/layer max {nc.max()} mean {nc.mean():.1f}, ~filament swaps {swaps} (purge ~{swaps*0.14:.0f} g at ~140 mm3/swap... est)')
