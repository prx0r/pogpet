import numpy as np,trimesh,sys; sys.path.insert(0,'.')
from paint_map import *
cols=np.array([[int(PAL[i][1][j:j+2],16) for j in (1,3,5)]+[255] for i in range(len(PAL))],np.uint8)
for k in ['pyjama','dress']:
    p=trimesh.load(f'prod/brick-figure-{k}-PLA-sub.stl',process=False); rgb=np.load(f'/tmp/rgb_{k}.npy')
    assert len(p.faces)==len(rgb)
    lab_=assign(rgb,p,smooth=3,allowed=region_allowed(p,rgb)); np.save(f'prod/paint_{k}.npy',lab_)
    A=p.area_faces; print(k,{PAL[i][0]:round(A[lab_==i].sum()/A.sum()*100,1) for i in range(len(PAL))})
    V=p.vertices[p.faces].reshape(-1,3); F=np.arange(len(V)).reshape(-1,3)
    trimesh.Trimesh(V,F,vertex_colors=np.repeat(cols[lab_],3,0),process=False).export(f'/tmp/painted_{k}.ply')
