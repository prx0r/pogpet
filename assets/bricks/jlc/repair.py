import trimesh,numpy as np,sys
from trimesh.visual import TextureVisuals
def stats(g):
    e=np.sort(g.edges,axis=1); u,c=np.unique(e,axis=0,return_counts=True); return u,c
for n in sys.argv[1:]:
    m=trimesh.load(f'q_{n}/brick-figure-{n}.obj',process=False)
    V=np.asarray(m.vertices); F=np.asarray(m.faces); UV=np.asarray(m.visual.uv)
    # weld by position
    _,inv=np.unique(np.round(V,5),axis=0,return_inverse=True); inv=inv.ravel()
    Fw=inv[F]
    for it in range(6):
        g=trimesh.Trimesh(np.zeros((inv.max()+1,3)),Fw,process=False)
        u,c=stats(g); bad=u[c!=2]
        if len(bad)==0: break
        badset=set(map(tuple,bad))
        e=np.sort(np.stack([Fw[:,[0,1]],Fw[:,[1,2]],Fw[:,[2,0]]],1),axis=2)
        hit=np.array([any(tuple(x) in badset for x in fe) for fe in e])
        # also drop faces with repeated welded verts
        hit|= (Fw[:,0]==Fw[:,1])|(Fw[:,1]==Fw[:,2])|(Fw[:,0]==Fw[:,2])
        print(n,'iter',it,'bad edges',len(bad),'drop faces',hit.sum())
        F=F[~hit]; Fw=Fw[~hit]
        # fill holes on welded mesh
        rep=np.zeros(inv.max()+1,int); rep[inv]=np.arange(len(inv))
        Vw=np.zeros((inv.max()+1,3)); Vw[inv]=V
        g=trimesh.Trimesh(Vw,Fw,process=False)
        nf=len(g.faces); trimesh.repair.fill_holes(g)
        new=np.asarray(g.faces[nf:])
        if len(g.vertices)>len(Vw): print('  fill added verts',len(g.vertices)-len(Vw)); 
        new=new[(new<len(Vw)).all(1)]
        print('  filled faces',len(new))
        Fw=np.vstack([Fw,new]); F=np.vstack([F,rep[new]])
    g=trimesh.Trimesh(Vw,Fw,process=False); u,c=stats(g)
    print(n,'final open',(c==1).sum(),'nonman',(c>2).sum(),'faces',len(F))
    out=trimesh.Trimesh(V,F,visual=TextureVisuals(uv=UV,material=m.visual.material),process=False)
    out.remove_unreferenced_vertices()
    import os; d=f'r_{n}'; os.makedirs(d,exist_ok=True)
    out.export(f'{d}/brick-figure-{n}.obj')
