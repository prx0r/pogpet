#!/usr/bin/env python3
"""Add a thread hole / hanging loop to a mesh — CoM-anchored so it hangs level.

    blender --background --python scripts/add_hook.py -- \\
        --in data/uploads/chibi-figure.glb --out data/uploads

Why centre-of-mass: a hung object rotates until its CoM sits directly below
the pivot. Anchoring the loop on the vertical line through the CoM (default
`--anchor com`) means no tilt; `--anchor x,y,z` puts the loop anywhere else
and the hang tilt is measured and printed so you can decide if it's worth it.

Print notes: loop wire >= 1.6 mm (2-3 perimeters at a 0.4 nozzle), inner hole
>= 4 mm for a jump ring or thread. Output STL is scaled to millimetres
(Blender units are metres; slicers assume mm).
"""
from __future__ import annotations

import argparse
import math
import sys

import bmesh
import bpy
from mathutils import Vector


def parse_args(argv):
    p = argparse.ArgumentParser()
    p.add_argument("--in", dest="src", required=True)
    p.add_argument("--out", dest="outdir", required=True)
    p.add_argument("--anchor", default="com",
                   help="'com' (default: above the centre of mass) or 'x,y,z'")
    # Standards (docs/balance.md): 4-6 mm hole clears jump rings, ribbon and tree
    # S-hooks (>=2.5 mm needed); 2.4 mm wire gives >=1.5 mm load-bearing wall
    # with O.D. 9.8 mm (print wisdom: hole 4-6, ring O.D. 7-10).
    p.add_argument("--inner", type=float, default=5.0, help="hole diameter, mm")
    p.add_argument("--wire", type=float, default=2.4, help="loop wire, mm")
    p.add_argument("--embed", type=float, default=2.0,
                   help="how deep the loop sinks into the body, mm")
    p.add_argument("--voxel", type=float, default=0.6,
                   help="voxel remesh size after the boolean, mm (0 = skip)")
    p.add_argument("--export", default="stl,glb", help="comma list: stl,glb")
    p.add_argument("--ballast", action="store_true",
                   help="cut an internal ballast slot for steel-shot trim "
                        "(fill through a pause-at-height, then glue)")
    p.add_argument("--ballast-d", type=float, default=8.0,
                   help="ballast slot diameter, mm")
    p.add_argument("--ballast-len", type=float, default=48.0,
                   help="ballast slot length across the body, mm")
    p.add_argument("--ballast-depth", type=float, default=10.0,
                   help="slot centre below the surface, mm (roof = depth - r)")
    p.add_argument("--preview", default="",
                   help="render a preview PNG to this path")
    argv = argv[argv.index("--") + 1:] if "--" in argv else argv[1:]
    return p.parse_args(argv)


def import_model(path: str):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    # factory settings drop user add-ons; re-enable the Meshy plugin so the
    # print checks (solid / thickness / overhang) are available headless
    try:
        bpy.ops.preferences.addon_enable(module="bl_ext.user_default.meshy")
    except Exception:                          # noqa: BLE001
        pass
    bpy.ops.import_scene.gltf(filepath=path)
    meshes = [o for o in bpy.context.scene.objects if o.type == "MESH"]
    if not meshes:
        raise SystemExit("no mesh in file")
    if len(meshes) > 1:                       # one object is easier to reason about
        bpy.ops.object.select_all(action="DESELECT")
        for o in meshes:
            o.select_set(True)
        bpy.context.view_layer.objects.active = meshes[0]
        bpy.ops.object.join()
        meshes = [bpy.context.view_layer.objects.active]
    obj = meshes[0]
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)
    return obj


def measure(obj):
    """World bbox, volume centre of mass, and the top surface above a point."""
    deps = bpy.context.evaluated_depsgraph_get()
    ev = obj.evaluated_get(deps)
    me = ev.to_mesh()
    mw = obj.matrix_world
    mn = Vector((1e9,) * 3)
    mx = Vector((-1e9,) * 3)
    vol = 0.0
    com = Vector((0, 0, 0))
    bm = bmesh.new()
    bm.from_mesh(me)
    bmesh.ops.triangulate(bm, faces=bm.faces)   # tet volume math needs tris
    for f in bm.faces:
        v0, v1, v2 = (mw @ v.co for v in f.verts)
        # signed volume of the tetrahedron with the origin
        tet = v0.dot(v1.cross(v2)) / 6.0
        vol += tet
        com += (v0 + v1 + v2) / 4.0 * tet
    bm.free()
    ev.to_mesh_clear()
    for ob in bpy.context.scene.objects:      # bbox from bound boxes (cheap, world)
        if ob.type != "MESH":
            continue
        for c in ob.bound_box:
            w = ob.matrix_world @ Vector(c)
            mn = Vector(map(min, mn, w))
            mx = Vector(map(max, mx, w))
    com = com / vol if abs(vol) > 1e-12 else (mn + mx) / 2
    return mn, mx, com, abs(vol)


def top_surface_z(obj, x, y, from_z):
    """Ray cast straight down; returns the first surface z, or None."""
    hit, loc, *_ = obj.ray_cast(
        obj.matrix_world.inverted() @ Vector((x, y, from_z)),
        Vector((0, 0, -1)))
    return obj.matrix_world @ loc if hit else None


def add_loop(obj, anchor: Vector, inner_mm, wire_mm, embed_mm):
    r = (wire_mm / 2) / 1000.0                 # Blender units are metres
    R = (inner_mm / 2 + wire_mm / 2) / 1000.0
    surf = top_surface_z(obj, anchor.x, anchor.y, anchor.z + 10)
    if surf is None:
        raise SystemExit("no surface above the anchor point")
    cz = surf.z + (R + r) - (embed_mm / 1000.0)
    bpy.ops.mesh.primitive_torus_add(
        major_radius=R, minor_radius=r,
        major_segments=48, minor_segments=16,
        location=(anchor.x, anchor.y, cz),
        rotation=(0, math.radians(90), 0))     # hole axis along +Y (body length)
    loop = bpy.context.active_object
    loop.name = "thread_loop"
    return loop, surf


def boolean_union(obj, cutter):
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    mod = obj.modifiers.new("hook", "BOOLEAN")
    mod.operation = "UNION"
    mod.solver = "EXACT"
    mod.object = cutter
    bpy.ops.object.modifier_apply(modifier=mod.name)
    bpy.data.objects.remove(cutter, do_unlink=True)


def is_manifold(obj) -> tuple[bool, int]:
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bad = sum(1 for e in bm.edges if not e.is_manifold)
    bm.free()
    return bad == 0, bad


def run_checks(obj) -> list[str]:
    """Use the Meshy plugin's print checks when they're available."""
    out = []
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    for op in ("mesh.meshy_check_solid", "mesh.meshy_check_all"):
        try:
            getattr(bpy.ops, op.split(".")[0], None)
            res = getattr(getattr(bpy.ops, op.split(".")[0]), op.split(".")[1])()
            out.append(f"{op}: {res}")
        except Exception as e:                 # noqa: BLE001
            out.append(f"{op}: unavailable ({type(e).__name__}: {e})")
    return out


def main() -> int:
    args = parse_args(sys.argv)
    obj = import_model(args.src)
    mn, mx, com, volume = measure(obj)
    print(f"bbox mm: {(mx - mn) * 1000}")
    print(f"CoM: {tuple(round(v, 4) for v in com)}  volume: {volume * 1e6:.1f} cm3")

    if args.anchor == "com":
        anchor = Vector((com.x, com.y, mx.z))
    else:
        anchor = Vector(tuple(float(v) / 1000 for v in args.anchor.split(",")))
        anchor.z = mx.z
    print(f"anchor: {tuple(round(v, 4) for v in anchor)}")

    loop, surf = add_loop(obj, anchor, args.inner, args.wire, args.embed)
    print(f"loop placed: hole {args.inner} mm, wire {args.wire} mm, "
          f"surface z {surf.z:.4f}, embedded {args.embed} mm")

    # hang tilt: angle the body will rotate through so CoM is under the pivot
    pivot = Vector((anchor.x, anchor.y, surf.z))
    drop = pivot - com
    horiz = math.hypot(drop.x, drop.y)
    tilt = math.degrees(math.atan2(horiz, drop.z)) if drop.z > 0 else 0.0
    print(f"HANG TILT: {tilt:.1f} deg (pivot is {horiz * 1000:.1f} mm "
          f"off the CoM column)")

    boolean_union(obj, loop)

    ballast = None
    if args.ballast:
        r = (args.ballast_d / 2) / 1000.0
        length = args.ballast_len / 1000.0
        cz = surf.z - (args.ballast_depth / 1000.0)
        # axis along X (side to side) so fill can be biased left/right to
        # trim a tilt; fully enclosed: top of the bore sits at
        # surf - (depth - r) => roof thickness = depth - r
        bpy.ops.mesh.primitive_cylinder_add(
            radius=r, depth=length, vertices=48,
            location=(anchor.x, anchor.y, cz),
            rotation=(0, math.radians(90), 0))
        ballast = bpy.context.active_object
        ballast.name = "ballast_slot"
        bpy.ops.object.select_all(action="DESELECT")
        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj
        mod = obj.modifiers.new("ballast", "BOOLEAN")
        mod.operation = "DIFFERENCE"
        mod.solver = "EXACT"
        mod.object = ballast
        bpy.ops.object.modifier_apply(modifier=mod.name)
        bpy.data.objects.remove(ballast, do_unlink=True)
        roof = (args.ballast_depth - args.ballast_d / 2)
        pause_z_mm = (surf.z * 1000) - roof
        vol_cm3 = math.pi * (args.ballast_d / 2) ** 2 * args.ballast_len / 1000.0
        cap_g = vol_cm3 * 7.8                      # steel, ~7.8 g/cm3
        moment = cap_g * (args.ballast_len / 2)    # g.mm at the slot end
        print(f"BALLAST slot: dia {args.ballast_d} mm x {args.ballast_len} mm "
              f"across, centre {args.ballast_depth} mm below the back "
              f"(z={cz*1000:.1f} mm)")
        print(f"BALLAST roof: {roof:.1f} mm -> PAUSE AT HEIGHT z={pause_z_mm:.1f} mm "
              f"(layer {pause_z_mm/0.2:.0f} at 0.2 mm) and fill")
        h_mm = (surf.z - com.z) * 1000.0          # pivot -> CoM, vertical
        trim_mm = moment / 100.0                  # CoM trim on a 100 g print
        print(f"BALLAST capacity: {vol_cm3:.2f} cm3 -> up to {cap_g:.1f} g steel "
              f"shot ({moment:.0f} g.mm correcting moment = {trim_mm:.1f} mm "
              f"of CoM trim on a 100 g print ~ "
              f"{math.degrees(math.atan(trim_mm / h_mm)):.1f} deg of tilt, "
              f"h={h_mm:.1f} mm)")

    ok, bad = is_manifold(obj)
    print(f"after boolean: manifold={ok} bad_edges={bad}")

    from pathlib import Path
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    stem = Path(args.src).stem + "-hook"
    made = []

    # GLB first, straight off the boolean: UVs and texture still intact.
    # (Voxel remeshing — needed to seal the boolean seams — discards them.)
    if "glb" in args.export:
        g = outdir / f"{stem}.glb"
        bpy.ops.export_scene.gltf(filepath=str(g), export_format="GLB")
        made.append(g)

    if args.voxel > 0 and not ok:
        obj.data.remesh_voxel_size = args.voxel / 1000.0
        bpy.ops.object.voxel_remesh()
        ok, bad = is_manifold(obj)
        print(f"after voxel {args.voxel} mm: manifold={ok} bad_edges={bad}")

    for line in run_checks(obj):
        print("check:", line)

    if "stl" in args.export:
        # slicers read STL in millimetres; Blender units here are metres
        obj.scale = (1000, 1000, 1000)
        bpy.ops.object.transform_apply(scale=True)
        p = outdir / f"{stem}.stl"
        bpy.ops.wm.stl_export(filepath=str(p), export_selected_objects=True)
        made.append(p)
    for p in made:
        print(f"wrote {p} ({p.stat().st_size:,} bytes)")

    if args.preview:
        render(obj, args.preview)
    return 0


def render(obj, path: str) -> None:
    mn, mx, *_ = measure(obj)
    ctr = (mn + mx) / 2
    size = max(mx - mn)
    cam_d = bpy.data.cameras.new("cam")
    cam = bpy.data.objects.new("cam", cam_d)
    bpy.context.collection.objects.link(cam)
    cam.location = ctr + Vector((size * 1.5, -size * 1.7, size * 0.9))
    d = cam.location - ctr
    cam.rotation_euler = (math.atan2(math.hypot(d.x, d.y), d.z), 0,
                          math.atan2(d.y, d.x) + math.pi / 2)
    cam_d.lens = 50
    bpy.context.scene.camera = cam
    ld = bpy.data.lights.new("key", "AREA")
    ld.energy = 500
    ld.size = size * 2
    lo = bpy.data.objects.new("key", ld)
    bpy.context.collection.objects.link(lo)
    lo.location = ctr + Vector((size * 2, -size * 2, size * 3))
    dd = ctr - lo.location
    lo.rotation_euler = (math.atan2(math.hypot(dd.x, dd.y), dd.z), 0,
                         math.atan2(dd.y, dd.x) + math.pi / 2)
    scn = bpy.context.scene
    scn.render.engine = "BLENDER_EEVEE_NEXT"
    scn.render.resolution_x = 820
    scn.render.resolution_y = 820
    scn.world = bpy.data.worlds.new("w")
    scn.world.use_nodes = True
    scn.world.node_tree.nodes["Background"].inputs[0].default_value = (
        0.93, 0.93, 0.95, 1)
    scn.render.filepath = path
    bpy.ops.render.render(write_still=True)
    print(f"preview: {path}")


if __name__ == "__main__":
    raise SystemExit(main())
