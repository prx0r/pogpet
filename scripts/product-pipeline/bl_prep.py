"""Blender prep for JLC full-colour (WJP) figures from Meshy/any textured GLB.
blender -b --python bl_prep.py -- <in.glb> <height_mm> <target_faces> <outdir>
Steps: import -> scale to height (1 BU = 1 mm, feet on z=0, centred) -> merge by distance -> drop loose debris ->
decimate (UV-preserving collapse) -> print3d make-manifold -> print3d checks (thin 0.8 mm) -> export OBJ (v/vt only)."""
import bpy, sys, json, math, os, importlib, addon_utils, bmesh
a = sys.argv[sys.argv.index('--') + 1:]
src, H, TF, out = a[0], float(a[1]), int(a[2]), a[3]
os.makedirs(out, exist_ok=True)
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=src)
objs = [o for o in bpy.context.scene.objects if o.type == 'MESH']
bpy.ops.object.select_all(action='DESELECT')
for o in objs: o.select_set(True)
bpy.context.view_layer.objects.active = objs[0]
if len(objs) > 1: bpy.ops.object.join()
o = bpy.context.view_layer.objects.active
for p in [x for x in bpy.context.scene.objects if x.type != 'MESH']: bpy.data.objects.remove(p)
o.parent = None
bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
rep = {'source': os.path.basename(src), 'faces_in': len(o.data.polygons)}
import mathutils
bb = [o.matrix_world @ mathutils.Vector(c) for c in o.bound_box]
zmin = min(p.z for p in bb); zmax = max(p.z for p in bb)
k = H / (zmax - zmin); rep['native_height'] = round(zmax - zmin, 5); rep['scale'] = round(k, 4)
o.scale = (k, k, k); bpy.ops.object.transform_apply(scale=True)
bb = [mathutils.Vector(c) for c in o.bound_box]
cx = (min(p.x for p in bb) + max(p.x for p in bb)) / 2; cy = (min(p.y for p in bb) + max(p.y for p in bb)) / 2
o.location = (-cx, -cy, -min(p.z for p in bb)); bpy.ops.object.transform_apply(location=True)
# merge + debris
bpy.ops.object.mode_set(mode='EDIT'); bpy.ops.mesh.select_all(action='SELECT')
bpy.ops.mesh.remove_doubles(threshold=0.001)
bpy.ops.mesh.select_all(action='DESELECT'); bpy.ops.object.mode_set(mode='OBJECT')
bm = bmesh.new(); bm.from_mesh(o.data); bm.faces.ensure_lookup_table()
seen = set(); islands = []
for f in bm.faces:
    if f.index in seen: continue
    st = [f]; isl = []; seen.add(f.index)
    while st:
        g = st.pop(); isl.append(g)
        for e in g.edges:
            for h in e.link_faces:
                if h.index not in seen: seen.add(h.index); st.append(h)
    islands.append(isl)
islands.sort(key=len, reverse=True)
rep['shells_in'] = len(islands)
debris = [f for isl in islands if len(isl) < 0.002 * len(bm.faces) for f in isl]
rep['debris_faces_removed'] = len(debris); rep['debris_shells_removed'] = sum(1 for isl in islands if len(isl) < 0.002 * len(bm.faces))
bmesh.ops.delete(bm, geom=debris, context='FACES'); bm.to_mesh(o.data); bm.free()
# decimate
if len(o.data.polygons) > TF:
    m = o.modifiers.new('dec', 'DECIMATE'); m.ratio = TF / len(o.data.polygons); m.use_collapse_triangulate = True
    bpy.ops.object.modifier_apply(modifier='dec')
rep['faces_out'] = len(o.data.polygons)
# 3D print toolbox
mod = [m for m in addon_utils.modules() if 'print3d' in m.__name__][0].__name__
addon_utils.enable(mod, default_set=True); R = importlib.import_module(mod + '.report')
p = bpy.context.scene.print3d_toolbox; p.thickness_min = float(os.environ.get('THIN_MM', 0.8)); p.angle_overhang = math.radians(45)
def check(tag):
    bpy.ops.mesh.print3d_check_all(); d = {i.name: i.value for i in R._data}
    rep[tag] = {k: v for k, v in d.items()}; print('P3D', tag, d)
check('before_fix')
bpy.ops.object.mode_set(mode='EDIT'); bpy.ops.mesh.select_all(action='SELECT')
try:
    bpy.ops.mesh.print3d_clean_non_manifold()
except Exception as e: rep['clean_err'] = str(e)
bpy.ops.mesh.select_all(action='SELECT'); bpy.ops.mesh.normals_make_consistent(inside=False)
bpy.ops.object.mode_set(mode='OBJECT')
check('after_fix')
bpy.ops.mesh.print3d_info_volume(); rep['volume_info'] = [(i.name, i.value) for i in R._data]
bb = [mathutils.Vector(c) for c in o.bound_box]
rep['dims_mm'] = [round(max(p[i] for p in bb) - min(p[i] for p in bb), 2) for i in range(3)]
bpy.ops.object.select_all(action='DESELECT'); o.select_set(True)
bpy.ops.wm.obj_export(filepath=out + '/model.obj', export_selected_objects=True, export_normals=False, export_materials=True,
                      export_uv=True, path_mode='STRIP', forward_axis='Y', up_axis='Z')
bpy.ops.wm.save_as_mainfile(filepath=out + '/prepped.blend')
json.dump(rep, open(out + '/prep_report.json', 'w'), indent=1); print('PREP_DONE', json.dumps(rep))
