import bpy,bmesh,sys
argv=sys.argv[sys.argv.index('--')+1:]; glb=argv[0]
bpy.ops.wm.read_factory_settings(use_empty=True); bpy.ops.import_scene.gltf(filepath=glb)
for o in bpy.context.scene.objects:
    if o.type!='MESH': continue
    bm=bmesh.new(); bm.from_mesh(o.data)
    bmesh.ops.remove_doubles(bm,verts=bm.verts,dist=1e-4)
    bd=sum(1 for e in bm.edges if e.is_boundary); nm=sum(1 for e in bm.edges if not e.is_manifold)
    print('W',o.name,len(bm.faces),'boundary',bd,'nonmanifold',nm); bm.free()
