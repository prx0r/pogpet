import bpy,sys,math,mathutils
obj,out=sys.argv[sys.argv.index('--')+1:]
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.wm.obj_import(filepath=obj)
o=[o for o in bpy.context.scene.objects if o.type=='MESH'][0]
pts=[o.matrix_world@mathutils.Vector(c) for c in o.bound_box]
mn=mathutils.Vector([min(p[i] for p in pts) for i in range(3)]); mx=mathutils.Vector([max(p[i] for p in pts) for i in range(3)])
H=mx.z-mn.z; ctr=(mn+mx)/2
sc=bpy.context.scene; sc.render.engine='CYCLES'; sc.cycles.device='CPU'; sc.cycles.samples=48; sc.cycles.use_denoising=False; sc.render.resolution_x=900; sc.render.resolution_y=900
w=bpy.data.worlds.new('w'); sc.world=w; w.use_nodes=True; w.node_tree.nodes['Background'].inputs[0].default_value=(0.92,0.92,0.92,1)
cam=bpy.data.objects.new('cam',bpy.data.cameras.new('cam')); sc.collection.objects.link(cam); sc.camera=cam
cam.data.type='ORTHO'; cam.data.ortho_scale=H*0.36
for nm,rot,e in [('k',(math.radians(50),0,math.radians(30)),3),('f',(math.radians(60),0,math.radians(-60)),1.5)]:
    l=bpy.data.objects.new(nm,bpy.data.lights.new(nm,'SUN')); l.data.energy=e; l.rotation_euler=rot; sc.collection.objects.link(l)
zc=mx.z-H*0.17; d=H*3
cam.location=(ctr.x, ctr.y-d, zc); cam.rotation_euler=(math.radians(90),0,0)
sc.render.filepath=__import__('os').path.abspath(out); bpy.ops.render.render(write_still=True)
