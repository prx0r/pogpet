import trimesh,numpy as np,os
from collections import defaultdict
from trimesh.visual import TextureVisuals
def emap(Fw):
    d=defaultdict(list)
    for fi,f in enumerate(Fw):
        for a,b in ((f[0],f[1]),(f[1],f[2]),(f[2],f[0])): d[(min(a,b),max(a,b))].append(fi)
    return d
for n in ['pyjama','dress']:
    m=trimesh.load(f'q_{n}/brick-figure-{n}.obj',process=False)
    V=np.asarray(m.vertices);F=np.asarray(m.faces);UV=np.asarray(m.visual.uv)
    _,inv=np.unique(np.round(V,5),axis=0,return_inverse=True);inv=inv.ravel();Fw=inv[F]
    d=emap(Fw); bad={k for k,v in d.items() if len(v)!=2}
    drop=[]
    for k in bad:
        for fi in d[k]:
            f=Fw[fi]; es=[(min(a,b),max(a,b)) for a,b in ((f[0],f[1]),(f[1],f[2]),(f[2],f[0]))]
            if all(e in bad for e in es): drop.append(fi)
    drop=sorted(set(drop)); print(n,'drop',drop)
    keep=np.ones(len(F),bool); keep[drop]=False; F=F[keep]; Fw=Fw[keep]
    d=emap(Fw); rem={k:len(v) for k,v in d.items() if len(v)!=2}; print(' remaining',rem)
    # split 4-face edges between touching shells: duplicate verts per-shell handled by orig (unwelded) mesh check
    g=trimesh.Trimesh(V,F,process=False); g.merge_vertices(merge_tex=True,merge_norm=True)
    e=np.sort(g.edges,axis=1);u,c=np.unique(e,axis=0,return_counts=True)
    print(' merged check open',(c==1).sum(),'nonman',(c>2).sum())
    out=trimesh.Trimesh(V,F,visual=TextureVisuals(uv=UV,material=m.visual.material),process=False); out.remove_unreferenced_vertices()
    dd=f'r_{n}';os.makedirs(dd,exist_ok=True); out.export(f'{dd}/brick-figure-{n}.obj')
