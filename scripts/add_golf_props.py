#!/usr/bin/env python3
"""Add a golf club + glove to a brick/minifig GLB — free Blender, 0 credits.

    blender --background --python scripts/add_golf_props.py -- \
        --in data/uploads/brick-figure-....glb \
        --out data/uploads/brick-man-golf.glb \
        --preview data/marketing/golf

Critical frame note:
  glTF is Y-up; Blender import is Z-up and this Brick man sits under a
  ~29.8× root empty. World verts: head high-Z, feet low-Z, arms at ±X.
  Props are built in that world frame and parented to the root empty so
  they inherit the same scale. Never transform_apply the body (it scrambles
  axes). Stills render from the same scene — no re-import.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path


def parse_args(argv):
    p = argparse.ArgumentParser()
    p.add_argument("--in", dest="src", required=True)
    p.add_argument("--out", dest="out", required=True)
    p.add_argument("--preview", default="")
    p.add_argument("--size", type=int, default=1200)
    p.add_argument("--club-hand", choices=("right", "left"), default="right")
    p.add_argument("--glove-hand", choices=("right", "left", "none"), default="left")
    p.add_argument("--export-props", action="store_true")
    argv = argv[argv.index("--") + 1:] if "--" in argv else argv[1:]
    return p.parse_args(argv)


def _mat(name, color, metallic=0.0, rough=0.45):
    import bpy
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    bsdf = m.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = (*color, 1.0)
    bsdf.inputs["Metallic"].default_value = metallic
    bsdf.inputs["Roughness"].default_value = rough
    return m


def _body_meshes(scene):
    return [
        o for o in scene.objects
        if o.type == "MESH"
        and not any(k in (o.name or "").lower() for k in ("golf", "club", "glove"))
    ]


def _world_pts(ob):
    import mathutils
    mw = ob.matrix_world
    return [mw @ v.co for v in ob.data.vertices]


def _bbox(PTS):
    import mathutils
    mn = mathutils.Vector((
        min(p.x for p in PTS), min(p.y for p in PTS), min(p.z for p in PTS)))
    mx = mathutils.Vector((
        max(p.x for p in PTS), max(p.y for p in PTS), max(p.z for p in PTS)))
    return mn, mx


def _measure(body):
    """Hands + ground in Blender Z-up world.

    Right arm sits at negative X (import mirrors GLB +X → Blender -X for
    the node named Right Arm in this file). Hand = outer-X, low-Z of the arm.
    """
    import mathutils

    pts = []
    for ob in body:
        pts.extend(_world_pts(ob))
    fmn, fmx = _bbox(pts)
    fheight = fmx.z - fmn.z          # standing along Z
    fw = fmx.x - fmn.x
    ground_z = fmn.z + 0.01 * fheight

    def arm(key):
        for ob in body:
            n = (ob.name or "").lower()
            if key in n and "arm" in n:
                ap = _world_pts(ob)
                amn, amx = _bbox(ap)
                # hand zone: lower 35% of arm, outer X, mid Y (depth)
                hz0 = amn.z + 0.05 * (amx.z - amn.z)
                hz1 = amn.z + 0.40 * (amx.z - amn.z)
                xs = [p.x for p in ap if hz0 <= p.z <= hz1] or [p.x for p in ap]
                ys = [p.y for p in ap if hz0 <= p.z <= hz1] or [p.y for p in ap]
                # outer X = the X farther from centre
                cx = (fmn.x + fmx.x) / 2
                outer_x = max(xs, key=lambda x: abs(x - cx))
                return mathutils.Vector((
                    outer_x,
                    sum(ys) / len(ys),
                    (hz0 + hz1) / 2.0,
                ))
        return None

    right = arm("right")
    left = arm("left")
    third = fw / 3.0
    hip_z = fmn.z + 0.42 * fheight
    mid_y = (fmn.y + fmx.y) / 2
    if right is None:
        right = mathutils.Vector((fmn.x + third * 0.55, mid_y, hip_z))
    if left is None:
        left = mathutils.Vector((fmx.x - third * 0.55, mid_y, hip_z))

    def clamp(h):
        h = h.copy()
        h.x = max(fmn.x + 0.05 * fw, min(fmx.x - 0.05 * fw, h.x))
        h.y = max(fmn.y, min(fmx.y, h.y))
        h.z = max(fmn.z + 0.25 * fheight, min(fmn.z + 0.60 * fheight, h.z))
        return h

    return clamp(right), clamp(left), fmn, fmx, fheight, fw, ground_z


def build_golf_club(hand, ground_z, side=1, scale=1.0):
    """Iron: grip at hand, head on the floor (low Z), shaft along the slope."""
    import bpy
    import math
    from mathutils import Euler, Vector

    mat_shaft = _mat("club_shaft", (0.55, 0.56, 0.58), metallic=0.85, rough=0.28)
    mat_grip = _mat("club_grip", (0.08, 0.08, 0.09), metallic=0.0, rough=0.75)
    mat_head = _mat("club_head", (0.72, 0.73, 0.75), metallic=0.9, rough=0.22)
    mat_sole = _mat("club_sole", (0.25, 0.25, 0.27), metallic=0.4, rough=0.4)

    r_shaft = 0.020 * scale
    r_grip = 0.032 * scale
    r_hosel = 0.026 * scale
    head_s = (0.14 * scale, 0.05 * scale, 0.10 * scale)
    hosel_depth = 0.09 * scale
    lean = 0.40 * scale * side     # out to the side (±X)
    forward = 0.35 * scale         # toward camera (+Y)

    grip = Vector(hand)
    head = Vector((hand.x + lean, hand.y + forward, ground_z + 0.04 * scale))
    direction = (grip - head).normalized()
    length = (grip - head).length
    # Blender Z-up: cylinder default axis is Z — align to direction
    q = Vector((0, 0, 1)).rotation_difference(direction)

    objs = []

    bpy.ops.mesh.primitive_cylinder_add(vertices=16, radius=r_shaft, depth=length,
                                        location=tuple((head + grip) / 2))
    shaft = bpy.context.active_object
    shaft.name = "golf_shaft"
    shaft.rotation_mode = "QUATERNION"
    shaft.rotation_quaternion = q
    shaft.data.materials.append(mat_shaft)
    objs.append(shaft)

    grip_len = max(length * 0.20, 0.10 * scale)
    bpy.ops.mesh.primitive_cylinder_add(vertices=16, radius=r_grip, depth=grip_len,
                                        location=tuple(grip - direction * (grip_len / 2)))
    grip_ob = bpy.context.active_object
    grip_ob.name = "golf_grip"
    grip_ob.rotation_mode = "QUATERNION"
    grip_ob.rotation_quaternion = q
    grip_ob.data.materials.append(mat_grip)
    objs.append(grip_ob)

    # blade: long axis along Y (toe-to-heel), lofted face toward +Y
    bpy.ops.mesh.primitive_cube_add(
        size=1.0,
        location=tuple(head + Vector((0, 0.03 * scale, 0.04 * scale))),
    )
    head_ob = bpy.context.active_object
    head_ob.name = "golf_clubhead"
    head_ob.scale = (0.08 * scale, 0.16 * scale, 0.06 * scale)
    head_ob.rotation_euler = Euler((math.radians(15), 0, math.radians(-8 * side)), "XYZ")
    head_ob.data.materials.append(mat_head)
    objs.append(head_ob)

    bpy.ops.mesh.primitive_cylinder_add(
        vertices=12, radius=r_hosel, depth=hosel_depth,
        location=tuple(head + direction * (0.05 * scale)),
    )
    hosel = bpy.context.active_object
    hosel.name = "golf_hosel"
    hosel.rotation_mode = "QUATERNION"
    hosel.rotation_quaternion = q
    hosel.data.materials.append(mat_sole)
    objs.append(hosel)

    return objs


def build_glove(hand, side=1, scale=1.0):
    """Cream glove on the hand (outer X side of the figure)."""
    import bpy
    from mathutils import Vector

    mat = _mat("glove_cream", (0.93, 0.91, 0.87), metallic=0.0, rough=0.62)
    mat_cuff = _mat("glove_cuff", (0.78, 0.76, 0.70), metallic=0.0, rough=0.7)
    h = Vector(hand)
    objs = []

    bpy.ops.mesh.primitive_uv_sphere_add(
        segments=16, ring_count=12, radius=0.13 * scale,
        location=tuple(h + Vector((0.02 * scale * side, 0.02 * scale, 0.0))),
    )
    palm = bpy.context.active_object
    palm.name = "glove_palm"
    palm.scale = (0.9, 1.2, 1.1)
    palm.data.materials.append(mat)
    objs.append(palm)

    for i, dy in enumerate((-0.06, -0.02, 0.02, 0.06)):
        bpy.ops.mesh.primitive_cylinder_add(
            vertices=10, radius=0.022 * scale, depth=0.09 * scale,
            location=tuple(h + Vector((0.02 * scale * side, dy * scale, -0.06 * scale))),
        )
        f = bpy.context.active_object
        f.name = f"glove_finger_{i}"
        f.rotation_euler = (0, 0.35, 0)
        f.data.materials.append(mat)
        objs.append(f)

    bpy.ops.mesh.primitive_cylinder_add(
        vertices=10, radius=0.024 * scale, depth=0.07 * scale,
        location=tuple(h + Vector((0.02 * scale * side, 0.08 * scale, -0.02 * scale))),
    )
    thumb = bpy.context.active_object
    thumb.name = "glove_thumb"
    thumb.rotation_euler = (0, 0.3, 0.8 * side)
    thumb.data.materials.append(mat)
    objs.append(thumb)

    bpy.ops.mesh.primitive_cylinder_add(
        vertices=14, radius=0.07 * scale, depth=0.05 * scale,
        location=tuple(h + Vector((0, 0, 0.08 * scale))),
    )
    cuff = bpy.context.active_object
    cuff.name = "glove_cuff"
    cuff.data.materials.append(mat_cuff)
    objs.append(cuff)

    return objs


def join_named(objs, name):
    import bpy
    bpy.ops.object.select_all(action="DESELECT")
    for o in objs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]
    bpy.ops.object.join()
    ob = bpy.context.active_object
    ob.name = name
    return ob


def _parent_to_root(props, root):
    import bpy
    for ob in props:
        if root is None:
            continue
        mw = ob.matrix_world.copy()
        ob.parent = root
        ob.matrix_world = mw


def _tint_white_body(body):
    palette = {
        "head": (0.80, 0.58, 0.40),
        "torso": (0.16, 0.16, 0.18),
        "rightarm": (0.80, 0.58, 0.40),
        "leftarm": (0.80, 0.58, 0.40),
        "legs": (0.84, 0.80, 0.72),
        "mesh_0": (0.84, 0.80, 0.72),
    }
    for ob in body:
        n = (ob.name or "").lower()
        if not ob.data.materials:
            continue
        mat = ob.data.materials[0]
        if not mat or not mat.use_nodes:
            continue
        bsdf = mat.node_tree.nodes.get("Principled BSDF")
        if not bsdf:
            continue
        if any(node.type == "TEX_IMAGE" for node in mat.node_tree.nodes):
            continue
        base = bsdf.inputs["Base Color"].default_value
        if base[0] > 0.88 and base[1] > 0.88 and base[2] > 0.88:
            for key, rgb in palette.items():
                if key in n:
                    bsdf.inputs["Base Color"].default_value = (*rgb, 1.0)
                    print(f"tinted {ob.name} -> {rgb}")
                    break


def render_from_scene(objs, outdir, size=1200):
    import bpy
    from mathutils import Vector

    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    body = [o for o in objs if o.type == "MESH"]
    _tint_white_body(body)

    pts = []
    for o in body:
        pts.extend(_world_pts(o))
    mn, mx = _bbox(pts)
    centre = (mn + mx) / 2
    height = max(mx.z - mn.z, 0.1)          # Z-up height
    span = max(mx.x - mn.x, mx.y - mn.y, height)
    # feet on z=0, centre XY
    for o in body:
        o.location -= Vector((centre.x, centre.y, mn.z))
    bpy.context.view_layer.update()
    print(f"render frame height={height:.2f} span={span:.2f}")

    def area(name, loc, energy, size_m):
        bpy.ops.object.light_add(type="AREA", location=loc)
        L = bpy.context.active_object
        L.name = name
        L.data.energy = energy
        L.data.size = size_m
        # point light at origin
        d = Vector((0, 0, height * 0.45)) - Vector(loc)
        L.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()
        return L

    s = span
    area("key", (1.6 * s, -2.0 * s, 2.2 * s), 900 * s, 2.4 * s)
    area("fill", (-1.8 * s, -1.5 * s, 1.3 * s), 400 * s, 2.6 * s)
    area("rim", (0.2 * s, 2.0 * s, 1.8 * s), 450 * s, 2.0 * s)

    world = bpy.data.worlds.new("W")
    bpy.context.scene.world = world
    world.use_nodes = True
    bg = world.node_tree.nodes["Background"]
    bg.inputs[0].default_value = (0.45, 0.47, 0.50, 1)
    bg.inputs[1].default_value = 1.0

    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    scene.cycles.samples = 48
    scene.cycles.use_denoising = True
    scene.render.resolution_x = size
    scene.render.resolution_y = size
    scene.render.film_transparent = False
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGB"
    try:
        scene.view_settings.view_transform = "AgX"
        scene.view_settings.look = "AgX - Punchy"
    except Exception:
        pass

    target = Vector((0, 0, height * 0.48))
    # front = camera on -Y looking +Y (Blender front)
    shots = {
        "hero":  Vector((1.6 * s, -2.0 * s, 1.4 * s)),
        "front": Vector((0.0, -2.6 * s, height * 0.45)),
        "side":  Vector((2.4 * s, -0.3 * s, height * 0.40)),
    }
    for name, loc in shots.items():
        bpy.ops.object.camera_add(location=loc)
        cam = bpy.context.active_object
        cam.name = f"cam_{name}"
        direction = target - loc
        cam.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()
        scene.camera = cam
        bpy.context.view_layer.update()
        scene.render.filepath = str(outdir / f"golf-{name}.png")
        bpy.ops.render.render(write_still=True)
        print(f"rendered {scene.render.filepath}")
        bpy.data.objects.remove(cam, do_unlink=True)


def main() -> int:
    args = parse_args(sys.argv)
    import bpy
    from mathutils import Vector

    src = Path(args.src)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)

    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=str(src))
    body = _body_meshes(bpy.context.scene)
    if not body:
        raise SystemExit("no mesh in source GLB")

    right, left, fmn, fmx, fheight, fw, ground_z = _measure(body)
    print(
        f"figure Z-up bbox min={tuple(round(c,2) for c in fmn)} "
        f"max={tuple(round(c,2) for c in fmx)} h={fheight:.2f} w={fw:.2f}"
    )
    print(f"hands right={tuple(round(c,2) for c in right)} left={tuple(round(c,2) for c in left)}")
    print(f"ground_z={ground_z:.2f}")

    # scale relative to a 1.4-unit design figure; Blender world is ~30× GLB
    prop_scale = max(fheight / 1.4, 0.05)
    print(f"prop_scale={prop_scale:.3f}")

    club_hand = right if args.club_hand == "right" else left
    glove_hand = None
    if args.glove_hand != "none":
        glove_hand = left if args.glove_hand == "left" else right
        if glove_hand is club_hand:
            glove_hand = left if club_hand is right else right

    # side sign: right hand is at negative X in this import
    side = -1 if args.club_hand == "right" else 1
    club = join_named(
        build_golf_club(club_hand, ground_z, side=side, scale=prop_scale),
        "golf_club",
    )
    print(f"club grip={tuple(round(c,2) for c in club_hand)} ground_z={ground_z:.2f}")

    glove = None
    if glove_hand is not None:
        gside = 1 if glove_hand.x >= 0 else -1
        glove = join_named(
            build_glove(glove_hand, side=gside, scale=prop_scale),
            "golf_glove",
        )
        print(f"glove at {tuple(round(c,2) for c in glove_hand)}")

    # parent props to the root empty so export keeps them locked to the body
    root = bpy.data.objects.get("Node_11") or bpy.data.objects.get("Node_1")
    props = [club] + ([glove] if glove else [])
    _parent_to_root(props, root)
    print(f"parented props to {root.name if root else None}")

    all_objs = body + props
    bpy.ops.object.select_all(action="DESELECT")
    for o in all_objs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = all_objs[0]
    bpy.ops.export_scene.gltf(
        filepath=str(out),
        export_format="GLB",
        use_selection=True,
        export_yup=True,
        export_apply=False,
    )
    print(f"wrote {out} ({out.stat().st_size} bytes)")

    if args.export_props:
        props_out = out.with_name(out.stem + "-props.glb")
        bpy.ops.object.select_all(action="DESELECT")
        for o in props:
            o.select_set(True)
        bpy.context.view_layer.objects.active = props[0]
        bpy.ops.export_scene.gltf(
            filepath=str(props_out),
            export_format="GLB",
            use_selection=True,
            export_yup=True,
            export_apply=False,
        )
        print(f"wrote props {props_out}")

    if args.preview:
        render_from_scene(all_objs, args.preview, size=args.size)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
