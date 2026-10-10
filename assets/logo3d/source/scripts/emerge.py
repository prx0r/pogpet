import bpy, math, sys, os
from mathutils import Vector
D='/workspace/projects/791a7153-8d05-4c9b-b767-8f281ad46eb0/logo3d'
A=sys.argv[sys.argv.index('--')+1:]; RES=int(A[0]); FRAMES=[int(x) for x in A[1].split(',')] if len(A)>1 and A[1]!='all' else None
SAMP=int(A[2]) if len(A)>2 else 32
MODE=A[3] if len(A)>3 else 'obj'
bpy.ops.wm.read_factory_settings(use_empty=True); sc=bpy.context.scene
m=bpy.data.materials.new('m'); m.use_nodes=True; B=m.node_tree.nodes['Principled BSDF']
bpy.ops.wm.obj_import(filepath=f'{D}/out/var/chunky.obj',forward_axis='Y',up_axis='Z'); o=bpy.context.selected_objects[0]
o.data.materials.clear(); o.data.materials.append(m); bpy.context.view_layer.objects.active=o
b=o.modifiers.new('bev','BEVEL'); b.width=0.45; b.segments=3; b.limit_method='ANGLE'; b.angle_limit=math.radians(50); b.harden_normals=True
bpy.ops.object.shade_smooth_by_angle(angle=math.radians(40))
o.rotation_euler=(math.radians(90),0,0)
bpy.ops.object.empty_add(); spinE=bpy.context.object
bpy.ops.object.empty_add(); popE=bpy.context.object; popE.parent=spinE; popE.location=(0,5,0)
o.parent=popE; o.location=(0,-5,0)
bpy.ops.mesh.primitive_plane_add(size=400,location=(0,0.02,0),rotation=(math.radians(90),0,0)); pl=bpy.context.object; pl.is_shadow_catcher=True
if MODE=='obj': pl.hide_render=True
else: o.visible_camera=False
bpy.ops.object.camera_add(location=(0,-260,0),rotation=(math.radians(90),0,0)); cam=bpy.context.object; cam.data.lens=135; sc.camera=cam
def area(loc,size,en):
    bpy.ops.object.light_add(type='AREA',location=loc); L=bpy.context.object; L.data.size=size; L.data.energy=en
    L.rotation_euler=(Vector((0,0,0))-Vector(loc)).to_track_quat('-Z','Y').to_euler()
area((-70,-110,90),90,380000); area((110,-90,30),120,160000); area((0,-150,-60),160,50000); area((0,-40,130),140,90000)
w=bpy.data.worlds.new('W'); sc.world=w; w.use_nodes=True; w.node_tree.nodes['Background'].inputs['Color'].default_value=(1,1,1,1); w.node_tree.nodes['Background'].inputs['Strength'].default_value=0.35
sc.render.engine='CYCLES'; sc.cycles.device='CPU'; sc.cycles.samples=SAMP; sc.cycles.use_denoising=False; sc.cycles.max_bounces=5
sc.render.film_transparent=True; sc.render.image_settings.color_mode='RGBA'
sc.view_settings.view_transform='AgX'; sc.view_settings.look='AgX - Medium High Contrast'
sc.render.resolution_x=sc.render.resolution_y=RES
def cl(x): return max(0.,min(1.,x))
def ss(x): x=cl(x); return x*x*(3-2*x)
def back(x):
    x=cl(x); c1=1.7; c3=c1+1; return 1+c3*(x-1)**3+c1*(x-1)**2
def seg(f,a,b_): return (f-a)/(b_-a)
N=132; LIFT=16
def pose(f):
    # 0-12 flat white | 12-36 extrude | 22-44 white->black | 36-50 lift | 50-96 spin 360 | 96-110 lower | 104-124 black->white | 110-128 retract | 128-132 flat
    S=0.002+0.998*(back(seg(f,12,36)) if f<110 else 1-ss(seg(f,110,128)))
    k=ss(seg(f,22,44)) if f<104 else 1-ss(seg(f,104,124))
    L=LIFT*(ss(seg(f,36,50)) if f<96 else 1-ss(seg(f,96,110)))
    R=2*math.pi*ss(seg(f,50,96))
    T=math.radians(12)*math.sin(math.pi*cl(seg(f,50,96)))
    return S,k,L,R,T
def apply(f):
    S,k,L,R,T=pose(f)
    popE.scale=(1,max(S,0.002),1); spinE.location=(0,-5-L,0); spinE.rotation_euler=(T,0,R)
    o.hide_render=(S<0.01 and MODE=='obj')
    c=0.95*(1-k)+0.06*k
    B.inputs['Base Color'].default_value=(c,c,c*1.02 if k>0.5 else c,1); B.inputs['Metallic'].default_value=k; B.inputs['Roughness'].default_value=0.5-0.1*k
od=f'{D}/out/var/emerge_{RES}_{MODE}'; os.makedirs(od,exist_ok=True)
for f in (FRAMES or range(N)):
    apply(f); sc.render.filepath=f'{od}/f{f:03d}.png'; bpy.ops.render.render(write_still=True); print('FRAME',f,flush=True)
