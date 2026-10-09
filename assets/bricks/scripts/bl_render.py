import bpy,sys,math,mathutils
argv=sys.argv[sys.argv.index('--')+1:]; glb,out=argv
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=glb)
objs=[o for o in bpy.context.scene.objects if o.type=='MESH']
pts=[o.matrix_world@mathutils.Vector(c) for o in objs for c in o.bound_box]
mn=mathutils.Vector([min(p[i] for p in pts) for i in range(3)]); mx=mathutils.Vector([max(p[i] for p in pts) for i in range(3)])
ctr=(mn+mx)/2; h=max(mx-mn)
sc=bpy.context.scene; sc.render.engine='CYCLES'; sc.cycles.device='CPU'; sc.cycles.samples=24; sc.cycles.use_denoising=False; sc.render.resolution_x=600; sc.render.resolution_y=900
w=bpy.data.worlds.new('w'); sc.world=w; w.use_nodes=True; w.node_tree.nodes['Background'].inputs[0].default_value=(0.92,0.92,0.92,1); w.node_tree.nodes['Background'].inputs[1].default_value=1.0
cam=bpy.data.objects.new('cam',bpy.data.cameras.new('cam')); sc.collection.objects.link(cam); sc.camera=cam
cam.data.type='ORTHO'; cam.data.ortho_scale=h*1.15
for nm,rot,e in [('k',(math.radians(50),0,math.radians(30)),3),('f',(math.radians(60),0,math.radians(-60)),1.5)]:
    l=bpy.data.objects.new(nm,bpy.data.lights.new(nm,'SUN')); l.data.energy=e; l.rotation_euler=rot; sc.collection.objects.link(l)
d=h*3
for name,ang in [('front',0),('side',90),('back',180),('three_q',35)]:
    a=math.radians(ang)
    # glTF imports Y-up as Z-up; front faces -Y
    cam.location=(ctr.x+d*math.sin(a), ctr.y-d*math.cos(a), ctr.z)
    cam.rotation_euler=(math.radians(90),0,a)
    sc.render.filepath=f'{out}_{name}.png'; bpy.ops.render.render(write_still=True)
