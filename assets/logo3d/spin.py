import bpy, math, sys, os
from mathutils import Vector
D=os.path.dirname(os.path.abspath(__file__)) if '__file__' in dir() else '/workspace/projects/791a7153-8d05-4c9b-b767-8f281ad46eb0/logo3d'
D='/workspace/projects/791a7153-8d05-4c9b-b767-8f281ad46eb0/logo3d'
argv=sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else []
MODE=argv[0] if argv else 'spin'   # spin | still
FR=int(argv[1]) if len(argv)>1 else 32
S0=int(argv[2]) if len(argv)>2 else 1; S1=int(argv[3]) if len(argv)>3 else FR
bpy.ops.wm.read_factory_settings(use_empty=True)
sc=bpy.context.scene
def mat(n,c,metal,rough,aniso=0):
    m=bpy.data.materials.new(n); m.use_nodes=True; b=m.node_tree.nodes['Principled BSDF']
    b.inputs['Base Color'].default_value=(*c,1); b.inputs['Metallic'].default_value=metal; b.inputs['Roughness'].default_value=rough
    if aniso: b.inputs['Anisotropic'].default_value=aniso
    return m
BODY=mat('body',(0.018,0.018,0.02),1.0,0.32,0.4); SIL=mat('sil',(0.92,0.92,0.93),1.0,0.12)
bpy.ops.object.empty_add(); piv=bpy.context.object
for p,m in [('body',BODY),('glyph_top',SIL),('glyph_bot',SIL)]:
    bpy.ops.wm.obj_import(filepath=f'{D}/out/{p}.obj',forward_axis='Y',up_axis='Z')
    o=bpy.context.selected_objects[0]; o.data.materials.clear(); o.data.materials.append(m)
    bpy.context.view_layer.objects.active=o; bpy.ops.object.shade_smooth_by_angle(angle=math.radians(30))
    o.parent=piv
piv.rotation_mode='XYZ'
# coin upright facing -Y camera: rotate 90 about X; spin about world Z
piv.rotation_euler=(math.radians(80),0,0)
bpy.ops.object.empty_add(); spin=bpy.context.object; piv.parent=spin
bpy.ops.object.camera_add(location=(0,-150,0)); cam=bpy.context.object
cam.rotation_euler=(math.radians(90),0,0); cam.data.lens=85; cam.data.type='ORTHO'; cam.data.ortho_scale=48; sc.camera=cam
def area(loc,size,en,col=(1,1,1)):
    bpy.ops.object.light_add(type='AREA',location=loc); L=bpy.context.object; L.data.size=size; L.data.energy=en; L.data.color=col
    L.rotation_euler=(Vector((0,0,0))-Vector(loc)).to_track_quat('-Z','Y').to_euler()
area((-60,-80,70),60,90000); area((10,-220,40),140,260000); area((80,-60,20),40,40000); area((0,60,90),70,50000); area((0,-90,-60),80,15000)
w=bpy.data.worlds.new('W'); sc.world=w; w.use_nodes=True
nt=w.node_tree; bg=nt.nodes['Background']; grad=nt.nodes.new('ShaderNodeTexGradient'); ramp=nt.nodes.new('ShaderNodeValToRGB'); tc=nt.nodes.new('ShaderNodeTexCoord'); mp=nt.nodes.new('ShaderNodeMapping')
mp.inputs['Rotation'].default_value=(0,math.radians(-90),0)
nt.links.new(tc.outputs['Generated'],mp.inputs['Vector']); nt.links.new(mp.outputs['Vector'],grad.inputs['Vector']); nt.links.new(grad.outputs['Fac'],ramp.inputs['Fac']); nt.links.new(ramp.outputs['Color'],bg.inputs['Color'])
ramp.color_ramp.elements[0].color=(0.12,0.12,0.13,1); ramp.color_ramp.elements[1].color=(1,1,1,1); ramp.color_ramp.elements.new(0.55).color=(0.35,0.35,0.37,1); bg.inputs['Strength'].default_value=1.6
sc.render.engine='CYCLES'; sc.cycles.device='CPU'; sc.cycles.samples=40; sc.cycles.use_adaptive_sampling=True; sc.cycles.adaptive_threshold=0.03; sc.cycles.use_denoising=False
sc.cycles.max_bounces=6
sc.render.film_transparent=True; sc.render.image_settings.file_format='PNG'; sc.render.image_settings.color_mode='RGBA'
sc.view_settings.view_transform='AgX'; sc.view_settings.look='AgX - Medium High Contrast'
os.makedirs(f'{D}/out/spin',exist_ok=True)
if MODE=='still':
    sc.render.resolution_x=sc.render.resolution_y=1400; sc.cycles.samples=96
    spin.rotation_euler=(0,0,math.radians(-28)); piv.rotation_euler=(math.radians(78),0,0)
    sc.render.filepath=f'{D}/out/coin_still_rgba.png'; bpy.ops.render.render(write_still=True)
else:
    sc.render.resolution_x=sc.render.resolution_y=480
    for f in range(S0,S1+1):
        spin.rotation_euler=(0,0,math.pi*(f-1)/FR)   # 180deg loop: both faces identical
        sc.render.filepath=f'{D}/out/spin/f{f:03d}.png'; bpy.ops.render.render(write_still=True); print('FRAME',f,flush=True)
