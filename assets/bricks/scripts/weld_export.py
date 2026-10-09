import bpy,bmesh,sys
argv=sys.argv[sys.argv.index('--')+1:]; glb,out=argv
bpy.ops.wm.read_factory_settings(use_empty=True); bpy.ops.import_scene.gltf(filepath=glb)
for o in bpy.context.scene.objects:
    if o.type!='MESH': continue
    bm=bmesh.new(); bm.from_mesh(o.data); bmesh.ops.remove_doubles(bm,verts=bm.verts,dist=1e-4)
    bmesh.ops.recalc_face_normals(bm,faces=bm.faces)
    bm.to_mesh(o.data); bm.free()
bpy.ops.export_scene.gltf(filepath=out+'.glb',export_format='GLB')
bpy.ops.object.select_all(action='SELECT'); bpy.ops.wm.stl_export(filepath=out+'.stl',export_selected_objects=True)
