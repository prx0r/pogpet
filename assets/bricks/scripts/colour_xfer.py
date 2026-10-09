import trimesh,numpy as np,sys
from trimesh.triangles import points_to_barycentric
def sample(k):
    s=trimesh.load(f'prod/brick-figure-{k}-production.glb')
    meshes=[];cols=[]
    for n,g in s.geometry.items():
        T=s.graph.get(s.graph.geometry_nodes[n][0])[0]
        g=g.copy(); g.apply_transform(T); meshes.append(g)
    allm=trimesh.util.concatenate([trimesh.Trimesh(g.vertices,g.faces,process=False) for g in meshes])
    R=np.array([[1,0,0],[0,0,-1],[0,1,0]])
    allm.vertices=allm.vertices@R.T
    p=trimesh.load(f'prod/brick-figure-{k}-PLA.stl')
    v,f=trimesh.remesh.subdivide_to_size(p.vertices,p.faces,max_edge=0.3); p=trimesh.Trimesh(v,f)
    off=np.array([allm.bounds[:,0].mean(),allm.bounds[:,1].mean(),allm.bounds[0,2]])
    allm.vertices-=off
    print(k,'bounds glb',allm.bounds.round(2).tolist(),'pla',p.bounds.round(2).tolist())
    C=p.triangles_center
    out=[trimesh.proximity.closest_point(allm,C[i:i+20000]) for i in range(0,len(C),20000)]
    cp=np.vstack([o[0] for o in out]); dist=np.concatenate([o[1] for o in out]); fid=np.concatenate([o[2] for o in out])
    print(' dist mean %.4f p99 %.4f max %.3f'%(dist.mean(),np.percentile(dist,99),dist.max()))
    # map face id -> (mesh idx, local face)
    sizes=np.cumsum([0]+[len(g.faces) for g in meshes])
    rgb=np.zeros((len(C),3))
    for i,g in enumerate(meshes):
        sel=(fid>=sizes[i])&(fid<sizes[i+1]); lf=fid[sel]-sizes[i]
        tri=allm.vertices[g.faces[lf]+0]  # careful: use allm verts for this mesh
        vo=sizes  # unused
        tri=allm.triangles[fid[sel]]
        bc=points_to_barycentric(tri,cp[sel])
        uv=(g.visual.uv[g.faces[lf]]*bc[:,:,None]).sum(1)
        img=g.visual.material.baseColorTexture.convert('RGB'); W,H=img.size; a=np.asarray(img)
        x=np.clip((uv[:,0]%1)*W,0,W-1).astype(int); y=np.clip((1-(uv[:,1]%1))*H,0,H-1).astype(int)
        rgb[sel]=a[y,x]
    return p,rgb
if __name__=='__main__':
    for k in ['pyjama','dress']:
        p,rgb=sample(k); np.save(f'/tmp/rgb_{k}.npy',rgb); p.export(f'prod/brick-figure-{k}-PLA-sub.stl')
