"""Listing reference renders of the EXACT file going to print (reads the JLC zip contents).
blender -b --python bl_listing.py -- <unzipped_dir_with_obj> <outprefix> [res=1600] [samples=48] [views=hero,front,side,back,detail]
White cyclorama, soft 3-light studio, textured (map_Kd), 2000-ready PNGs."""
import bpy, sys, os, math, glob, mathutils
a = sys.argv[sys.argv.index('--') + 1:]
src, outp = a[0], a[1]; res = int(a[2]) if len(a) > 2 else 1600; spp = int(a[3]) if len(a) > 3 else 48
views = (a[4] if len(a) > 4 else 'hero,front,side,back,detail').split(',')
bpy.ops.wm.read_factory_settings(use_empty=True)
obj = glob.glob(src + '/*.obj')[0]
bpy.ops.wm.obj_import(filepath=obj, forward_axis='Y', up_axis='Z')
o = bpy.context.selected_objects[0]
bpy.context.view_layer.objects.active = o; bpy.ops.object.shade_smooth()
for m in o.data.materials:
    b = m.node_tree.nodes.get('Principled BSDF')
    if b: b.inputs['Roughness'].default_value = 0.35; b.inputs['Coat Weight'].default_value = 0.4  # WJP + oil spray
bb = [o.matrix_world @ mathutils.Vector(c) for c in o.bound_box]
mn = mathutils.Vector([min(p[i] for p in bb) for i in range(3)]); mx = mathutils.Vector([max(p[i] for p in bb) for i in range(3)])
H = mx.z - mn.z; ctr = (mn + mx) / 2
sc = bpy.context.scene
# sweep
bpy.ops.mesh.primitive_plane_add(size=H * 40, location=(0, 0, mn.z)); fl = bpy.context.object
bpy.ops.object.mode_set(mode='EDIT'); bpy.ops.mesh.select_all(action='SELECT'); bpy.ops.object.mode_set(mode='OBJECT')
fm = bpy.data.materials.new('floor'); fm.use_nodes = True; fb = fm.node_tree.nodes['Principled BSDF']; fb.inputs['Base Color'].default_value = (1, 1, 1, 1); fb.inputs['Roughness'].default_value = 0.9
fl.data.materials.append(fm)
w = bpy.data.worlds.new('w'); sc.world = w; w.use_nodes = True; w.node_tree.nodes['Background'].inputs[0].default_value = (1, 1, 1, 1); w.node_tree.nodes['Background'].inputs[1].default_value = 0.9
def area(loc, size, e):
    bpy.ops.object.light_add(type='AREA', location=loc); l = bpy.context.object; l.data.size = size; l.data.energy = e
    d = ctr - mathutils.Vector(loc); l.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler()
k = H / 80.0
area((-1.6 * H, -2.0 * H, 2.2 * H), 2.5 * H, 9e5 * k * k)
area((2.0 * H, -1.2 * H, 1.2 * H), 2.0 * H, 3.5e5 * k * k)
area((0, 2.0 * H, 2.4 * H), 2.0 * H, 4e5 * k * k)
sc.render.engine = 'CYCLES'; sc.cycles.device = 'CPU'; sc.cycles.samples = spp; sc.cycles.use_adaptive_sampling = True
sc.cycles.adaptive_threshold = 0.02; sc.cycles.use_denoising = False
sc.render.resolution_x = sc.render.resolution_y = res
sc.view_settings.view_transform = 'AgX'; sc.view_settings.look = 'AgX - Medium High Contrast'
cam = bpy.data.objects.new('cam', bpy.data.cameras.new('cam')); sc.collection.objects.link(cam); sc.camera = cam
cam.data.lens = 85; cam.data.clip_start = H * 0.01; cam.data.clip_end = H * 100
V = {'hero': (-35, 14, 1.0), 'front': (0, 6, 1.0), 'side': (90, 6, 1.0), 'back': (180, 6, 1.0), 'detail': (-20, 8, 0.45)}
for v in views:
    az, el, zoom = V[v]
    tgt = ctr.copy()
    if v == 'detail':
        # DETAIL_TARGET='fx,fy,fz' as fractions of the bbox (0..1); default = top-centre heads zone
        fx, fy, fz = [float(t) for t in os.environ.get('DETAIL_TARGET', '0.5,0.5,0.78').split(',')]
        tgt = mathutils.Vector((mn.x + fx * (mx.x - mn.x), mn.y + fy * (mx.y - mn.y), mn.z + fz * H))
        zoom = float(os.environ.get('DETAIL_ZOOM', zoom))
    dist = H * 3.3 * zoom
    A, E = math.radians(az), math.radians(el)
    cam.location = (tgt.x + dist * math.sin(A) * math.cos(E), tgt.y - dist * math.cos(A) * math.cos(E), tgt.z + dist * math.sin(E))
    cam.rotation_euler = (tgt - cam.location).to_track_quat('-Z', 'Y').to_euler()
    sc.render.filepath = f'{outp}_{v}.png'; bpy.ops.render.render(write_still=True); print('RENDERED', sc.render.filepath)
