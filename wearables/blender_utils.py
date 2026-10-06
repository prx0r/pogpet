from __future__ import annotations

from pathlib import Path


def bpy_mod():
    try:
        import bpy
    except ImportError as e:
        raise RuntimeError("This operation must run inside Blender Python") from e
    return bpy


def mesh_objects(scene=None):
    bpy = bpy_mod()
    scene = scene or bpy.context.scene
    return [o for o in scene.objects if o.type == "MESH"]


def world_vertices(ob):
    return [ob.matrix_world @ v.co for v in ob.data.vertices]


def bbox_points(points):
    from mathutils import Vector
    pts = list(points)
    if not pts:
        z = Vector((0, 0, 0))
        return z.copy(), z.copy()
    mn = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
    mx = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
    return mn, mx


def bbox_objects(objects):
    return bbox_points(p for o in objects for p in world_vertices(o))


def import_glb(path: str | Path):
    bpy = bpy_mod()
    before = set(bpy.context.scene.objects)
    bpy.ops.import_scene.gltf(filepath=str(path))
    return [o for o in bpy.context.scene.objects if o not in before and o.type == "MESH"]


def bake_world(ob):
    from mathutils import Matrix
    mw = ob.matrix_world.copy()
    ob.data.transform(mw)
    ob.matrix_world = Matrix.Identity(4)
    ob.data.update()
    return ob


def join_meshes(objects, name="asset"):
    bpy = bpy_mod()
    objects = [o for o in objects if o and o.type == "MESH"]
    if not objects:
        raise ValueError("no mesh objects")
    for o in objects:
        bake_world(o)
    bpy.ops.object.select_all(action="DESELECT")
    for o in objects:
        o.select_set(True)
    bpy.context.view_layer.objects.active = objects[0]
    if len(objects) > 1:
        bpy.ops.object.join()
    ob = bpy.context.active_object
    ob.name = name
    return ob


def shade_smooth(ob):
    for p in ob.data.polygons:
        p.use_smooth = True


def apply_modifier(ob, mod):
    bpy = bpy_mod()
    bpy.ops.object.select_all(action="DESELECT")
    ob.select_set(True)
    bpy.context.view_layer.objects.active = ob
    bpy.ops.object.modifier_apply(modifier=mod.name)


def add_subdivision(ob, levels=1):
    if levels <= 0:
        return
    mod = ob.modifiers.new("OH_subdivision", "SUBSURF")
    mod.subdivision_type = "CATMULL_CLARK"
    mod.levels = int(levels)
    mod.render_levels = int(levels)
    apply_modifier(ob, mod)


def robust_extent(vals, lo=0.10, hi=0.90):
    xs = sorted(float(x) for x in vals)
    if not xs:
        return 0.0
    n = len(xs)
    a = xs[min(n - 1, max(0, int((n - 1) * lo)))]
    b = xs[min(n - 1, max(0, int((n - 1) * hi)))]
    return max(b - a, 0.0)


def robust_mid(vals, lo=0.10, hi=0.90):
    xs = sorted(float(x) for x in vals)
    if not xs:
        return 0.0
    n = len(xs)
    a = xs[min(n - 1, max(0, int((n - 1) * lo)))]
    b = xs[min(n - 1, max(0, int((n - 1) * hi)))]
    return 0.5 * (a + b)


def export_glb(path: str | Path, objects):
    bpy = bpy_mod()
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.object.select_all(action="DESELECT")
    objs = [o for o in objects if o and o.name in bpy.context.scene.objects]
    for o in objs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]
    bpy.ops.export_scene.gltf(
        filepath=str(out), export_format="GLB", use_selection=True,
        export_yup=True, export_apply=False,
    )
    return out


def rotation_matrix_from_euler_deg(deg):
    from mathutils import Euler
    import math
    d = list(deg or [0, 0, 0])
    while len(d) < 3:
        d.append(0)
    return Euler(tuple(math.radians(float(v)) for v in d[:3]), "XYZ").to_matrix()
