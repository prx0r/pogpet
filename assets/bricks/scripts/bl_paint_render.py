import bpy,sys,math,mathutils
a=sys.argv[sys.argv.index('--')+1:]; ply,out=a[0],a[1]
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.wm.ply_import(filepath=ply)
o=bpy.context.selected_objects[0]
attr=o.data.color_attributes[0].name if o.data.color_attributes else None
mat=bpy.data.materials.new('m'); mat.use_nodes=True; nt=mat.node_tree; b=nt.nodes['Principled BSDF']; b.inputs['Roughness'].default_value=0.5
if attr:
    c=nt.nodes.new('ShaderNodeVertexColor'); c.layer_name=attr; nt.links.new(c.outputs[0],b.inputs['Base Color'])
o.data.materials.append(mat)
for pl in o.data.polygons: pl.use_smooth=False
sc=bpy.context.scene; sc.render.engine='CYCLES'; sc.cycles.samples=24; sc.cycles.device='CPU'; sc.cycles.use_denoising=False
sc.render.resolution_x=600; sc.render.resolution_y=800
w=bpy.data.worlds.new('w'); sc.world=w; w.use_nodes=True; w.node_tree.nodes['Background'].inputs[0].default_value=(0.8,0.8,0.8,1); w.node_tree.nodes['Background'].inputs[1].default_value=1.0
cam=bpy.data.objects.new('c',bpy.data.cameras.new('c')); sc.collection.objects.link(cam); sc.camera=cam
cam.data.type='ORTHO'; cam.data.ortho_scale=50
L=bpy.data.objects.new('l',bpy.data.lights.new('l','SUN')); L.data.energy=3; sc.collection.objects.link(L)
for name,ang in [('front',0),('back',180)]:
    r=math.radians(ang); cam.location=(100*math.sin(r),-100*math.cos(r),22.6)
    cam.rotation_euler=(math.radians(90),0,r); L.rotation_euler=(math.radians(50),0,r+math.radians(20))
    sc.render.filepath=f'{out}_{name}.png'; bpy.ops.render.render(write_still=True)
