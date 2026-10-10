import bpy, math, sys
from mathutils import Vector
D='/workspace/projects/791a7153-8d05-4c9b-b767-8f281ad46eb0/logo3d'
V=sys.argv[sys.argv.index('--')+1]; RES=int(sys.argv[sys.argv.index('--')+2]) if len(sys.argv)>sys.argv.index('--')+2 else 1400
bpy.ops.wm.read_factory_settings(use_empty=True); sc=bpy.context.scene
def mat(n,c,metal,rough,coat=0,aniso=0):
    m=bpy.data.materials.new(n); m.use_nodes=True; b=m.node_tree.nodes['Principled BSDF']
    b.inputs['Base Color'].default_value=(*c,1); b.inputs['Metallic'].default_value=metal; b.inputs['Roughness'].default_value=rough
    if coat: b.inputs['Coat Weight'].default_value=coat; b.inputs['Coat Roughness'].default_value=0.03
    if aniso: b.inputs['Anisotropic'].default_value=aniso
    return m
GOLD=(1.0,0.66,0.24); SILV=(0.92,0.92,0.93)
C={
 'gold':[('out/body.obj',mat('g1',GOLD,1,0.3,aniso=0.4)),('out/glyph_top.obj',mat('g2',(1.0,0.76,0.36),1,0.06)),('out/glyph_bot.obj',None)],
 'silver_engraved':[('out/var/eng_body.obj',mat('s1',SILV,1,0.18,aniso=0.3)),('out/var/eng_fill.obj',mat('s2',(0.01,0.01,0.012),0,0.35,coat=1))],
 'chunky_orange':[('out/var/chunky.obj',mat('o',(0.8,0.1,0.0),0,0.35,coat=1))],
 'chunky_chrome':[('out/var/chunky.obj',mat('c',(0.95,0.95,0.96),1,0.05))],
 'chunky_gold':[('out/var/chunky.obj',mat('cg',GOLD,1,0.12))],
 'chunky_matte':[('out/var/chunky.obj',mat('mb',(0.06,0.06,0.065),1,0.4,aniso=0.0))],
 'chunky_black':[('out/var/chunky.obj',mat('cb',(0.02,0.02,0.022),0,0.32,coat=1))],
}[V]
bpy.ops.object.empty_add(); piv=bpy.context.object; last=None
for p,m in C:
    m=m or last; last=m
    bpy.ops.wm.obj_import(filepath=f'{D}/{p}',forward_axis='Y',up_axis='Z'); o=bpy.context.selected_objects[0]
    o.data.materials.clear(); o.data.materials.append(m); bpy.context.view_layer.objects.active=o
    if V.startswith('chunky'):
        b=o.modifiers.new('bev','BEVEL'); b.width=0.45; b.segments=3; b.limit_method='ANGLE'; b.angle_limit=math.radians(50); b.harden_normals=True
        bpy.ops.object.shade_smooth_by_angle(angle=math.radians(40))
    else: bpy.ops.object.shade_smooth_by_angle(angle=math.radians(30))
    o.parent=piv
bpy.ops.object.empty_add(); spin=bpy.context.object; piv.parent=spin
chunky=V.startswith('chunky')
piv.rotation_euler=(math.radians(76 if chunky else 78),0,0); spin.rotation_euler=(0,0,math.radians(-34 if chunky else -28))
bpy.ops.object.camera_add(location=(0,-150,0)); cam=bpy.context.object
cam.rotation_euler=(math.radians(90),0,0); cam.data.type='ORTHO'; cam.data.ortho_scale=50 if chunky else 48; sc.camera=cam
def area(loc,size,en):
    bpy.ops.object.light_add(type='AREA',location=loc); L=bpy.context.object; L.data.size=size; L.data.energy=en
    L.rotation_euler=(Vector((0,0,0))-Vector(loc)).to_track_quat('-Z','Y').to_euler()
MATTE=V=='chunky_matte'
if MATTE:
    area((-90,-120,90),120,420000); area((110,-90,30),120,200000); area((0,40,130),140,160000); area((0,-150,-60),160,60000)
else:
  area((-60,-80,70),60,90000); area((10,-220,40),140,260000); area((80,-60,20),40,40000); area((0,60,90),70,50000); area((0,-90,-60),80,15000)
w=bpy.data.worlds.new('W'); sc.world=w; w.use_nodes=True; nt=w.node_tree; bg=nt.nodes['Background']
grad=nt.nodes.new('ShaderNodeTexGradient'); ramp=nt.nodes.new('ShaderNodeValToRGB'); tc=nt.nodes.new('ShaderNodeTexCoord'); mp=nt.nodes.new('ShaderNodeMapping')
mp.inputs['Rotation'].default_value=(0,math.radians(-90),0)
nt.links.new(tc.outputs['Generated'],mp.inputs['Vector']); nt.links.new(mp.outputs['Vector'],grad.inputs['Vector']); nt.links.new(grad.outputs['Fac'],ramp.inputs['Fac']); nt.links.new(ramp.outputs['Color'],bg.inputs['Color'])
ramp.color_ramp.elements[0].color=(0.12,0.12,0.13,1); ramp.color_ramp.elements[1].color=(1,1,1,1); ramp.color_ramp.elements.new(0.55).color=(0.35,0.35,0.37,1); bg.inputs['Strength'].default_value=1.6 if not MATTE else 2.2
sc.render.engine='CYCLES'; sc.cycles.device='CPU'; sc.cycles.samples=96; sc.cycles.use_adaptive_sampling=True; sc.cycles.adaptive_threshold=0.03; sc.cycles.max_bounces=6; sc.cycles.use_denoising=False
sc.render.film_transparent=True; sc.render.image_settings.color_mode='RGBA'
sc.view_settings.view_transform='AgX'; sc.view_settings.look='AgX - Punchy' if V=='chunky_orange' else 'AgX - Medium High Contrast'
sc.render.resolution_x=sc.render.resolution_y=RES
A=sys.argv[sys.argv.index('--')+1:]
if len(A)>2 and A[2]=='spin':
    import os; FR=int(A[3]); od=f'{D}/out/var/spin_{V}'; os.makedirs(od,exist_ok=True)
    sc.cycles.samples=40; base=spin.rotation_euler[2]
    for f in range(FR):
        spin.rotation_euler=(0,0,base+math.pi*f/FR); sc.render.filepath=f'{od}/f{f:03d}.png'; bpy.ops.render.render(write_still=True); print('FRAME',f,flush=True)
elif len(A)>2 and A[2]=='glb':
    for o in bpy.data.objects:
        if o.type=='MESH':
            bpy.context.view_layer.objects.active=o; o.select_set(True)
    bpy.ops.export_scene.gltf(filepath=f'{D}/out/var/oddhobb-{V}.glb',use_selection=True,export_apply=True)
else:
    sc.render.filepath=f'{D}/out/var/{V}_rgba.png'; bpy.ops.render.render(write_still=True)
