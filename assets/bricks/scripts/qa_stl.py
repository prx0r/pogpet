import bpy,bmesh,sys
argv=sys.argv[sys.argv.index('--')+1:]; glb,stl=argv
bpy.ops.wm.read_factory_settings(use_empty=True); bpy.ops.import_scene.gltf(filepath=glb)
for o in bpy.context.scene.objects:
    if o.type!='MESH': continue
    bm=bmesh.new(); bm.from_mesh(o.data)
    nm=sum(1 for e in bm.edges if not e.is_manifold); bd=sum(1 for e in bm.edges if e.is_boundary)
    print('QA',o.name,len(bm.verts),len(bm.faces),'nonmanifold',nm,'boundary',bd); bm.free()
bpy.ops.object.select_all(action='SELECT')
bpy.ops.wm.stl_export(filepath=stl,export_selected_objects=True,apply_modifiers=True)
print('STL done')
