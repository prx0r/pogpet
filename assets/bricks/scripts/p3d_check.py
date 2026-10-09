import bpy,sys,importlib,addon_utils
argv=sys.argv[sys.argv.index('--')+1:]
bpy.ops.wm.read_factory_settings(use_empty=True)
mod=[m for m in addon_utils.modules() if 'print3d' in m.__name__][0].__name__
addon_utils.enable(mod,default_set=True)
rep=importlib.import_module(mod+'.report')
for f in argv:
    for o in list(bpy.data.objects): bpy.data.objects.remove(o)
    bpy.ops.wm.stl_import(filepath=f)
    o=bpy.context.selected_objects[0]; bpy.context.view_layer.objects.active=o
    p=bpy.context.scene.print3d_toolbox; p.thickness_min=0.8; p.angle_overhang=0.7854; p.angle_sharp=2.792
    bpy.ops.mesh.print3d_info_volume(); 
    bpy.ops.mesh.print3d_check_all()
    print('P3D',f.split('/')[-1],[(i.name,i.value) for i in rep._data])
    import numpy as np
    me=o.data; C=np.array([pl.center[:] for pl in me.polygons]); A=np.array([pl.area for pl in me.polygons])
    for it in rep._data:
        if it.name in ('Thin Faces','Intersect Faces') and it.indices:
            idx=np.array(it.indices); c=C[idx]; a=A[idx].sum()
            regions={'head/hair z>32':c[:,2]>32,'torso 21-32':(c[:,2]>21)&(c[:,2]<=32),'arms/hands |x|>8,z<=32':(np.abs(c[:,0])>8)&(c[:,2]<=32),'hips/legs z<=21':(c[:,2]<=21)&(np.abs(c[:,0])<=8)}
            print('LOC',it.name,'area mm2 %.1f of %.1f'%(a,A.sum()),{k:int(v.sum()) for k,v in regions.items()})
