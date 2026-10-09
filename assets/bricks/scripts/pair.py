import bpy,sys,math,mathutils
argv=sys.argv[sys.argv.index('--')+1:]; fa,fb,out=argv
bpy.ops.wm.read_factory_settings(use_empty=True)
groups=[]
for f,dx in [(fa,-0.45),(fb,0.45)]:
    before=set(bpy.data.objects); bpy.ops.import_scene.gltf(filepath=f); new=[o for o in bpy.data.objects if o not in before]
    for o in new:
        if o.type=='MESH': o.data.transform(mathutils.Matrix.Translation(o.matrix_world.inverted().to_3x3()@mathutils.Vector((dx,0,0))))
    groups.append(new)
bpy.context.view_layer.update()
objs=[o for o in bpy.data.objects if o.type=='MESH']
pts=[o.matrix_world@mathutils.Vector(c) for o in objs for c in o.bound_box]
mn=mathutils.Vector([min(p[i] for p in pts) for i in range(3)]); mx=mathutils.Vector([max(p[i] for p in pts) for i in range(3)]); ctr=(mn+mx)/2
sc=bpy.context.scene; sc.render.engine='CYCLES'; sc.cycles.samples=32; sc.cycles.use_denoising=False; sc.render.resolution_x=1000; sc.render.resolution_y=1000
w=bpy.data.worlds.new('w'); sc.world=w; w.use_nodes=True; w.node_tree.nodes['Background'].inputs[0].default_value=(0.93,0.93,0.93,1)
cam=bpy.data.objects.new('cam',bpy.data.cameras.new('cam')); sc.collection.objects.link(cam); sc.camera=cam; cam.data.type='ORTHO'; cam.data.ortho_scale=max(mx.x-mn.x,mx.z-mn.z)*1.12
for nm,rot,e in [('k',(math.radians(50),0,math.radians(30)),3),('f',(math.radians(60),0,math.radians(-60)),1.5)]:
    l=bpy.data.objects.new(nm,bpy.data.lights.new(nm,'SUN')); l.data.energy=e; l.rotation_euler=rot; sc.collection.objects.link(l)
d=6
for name,ang in [('front',0),('back',180),('three_q',30)]:
    a=math.radians(ang); cam.location=(ctr.x+d*math.sin(a),ctr.y-d*math.cos(a),ctr.z); cam.rotation_euler=(math.radians(90),0,a)
    sc.render.filepath=f'{out}_{name}.png'; bpy.ops.render.render(write_still=True)
