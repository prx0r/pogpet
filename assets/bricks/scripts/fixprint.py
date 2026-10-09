import trimesh, numpy as np, manifold3d as mf, sys
for k in ['pyjama','dress']:
    m=trimesh.load(f'prod/brick-figure-{k}-production.stl')
    bodies=[b for b in m.split(only_watertight=False) if len(b.faces)>20]
    fixed=[]
    for b in bodies:
        if not b.is_watertight:
            import pymeshfix
            v,f=pymeshfix.clean_from_arrays(np.ascontiguousarray(b.vertices,dtype=np.float64),np.ascontiguousarray(b.faces,dtype=np.int32))
            b=trimesh.Trimesh(v,f); print('  meshfix',b.is_watertight,round(b.volume,2))
        print(k,len(b.faces),b.is_watertight)
        fixed.append(b)
    ms=[mf.Manifold(mf.Mesh(vert_properties=np.asarray(b.vertices,np.float32),tri_verts=np.asarray(b.faces,np.uint32))) for b in fixed]
    print([x.status() for x in ms])
    u=ms[0]
    for x in ms[1:]: u=u+x
    o=u.to_mesh(); out=trimesh.Trimesh(o.vert_properties[:,:3],o.tri_verts)
    # put feet on z=0 (STL is Z-up from Blender)
    out.apply_translation([-out.bounds[:,0].mean(),-out.bounds[:,1].mean(),-out.bounds[0,2]])
    print(k,'union faces',len(out.faces),'watertight',out.is_watertight,'bodies',len(out.split()),'vol',round(out.volume,1),'extent',out.extents.round(2))
    out.export(f'prod/brick-figure-{k}-PLA.stl')
