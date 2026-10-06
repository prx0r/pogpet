from __future__ import annotations

import math

from .blender_utils import import_glb, join_meshes, shade_smooth


def _axis(v):
    from mathutils import Vector
    a=Vector(tuple(float(x) for x in v))
    return a.normalized() if a.length else Vector((0,0,1))


def fit_prop(spec, profile, *, socket_name=None):
    """Attach an arbitrary imported GLB to a semantic socket.

    `grip_normalized` is a point inside the prop bbox (0..1 on XYZ). This lets a
    raw Meshy GLB become reusable without editing it. For precision assets, author
    the same values once after using the fit editor.
    """
    path=spec.file_for(profile["body_class"])
    if not path or not path.exists():
        raise FileNotFoundError(f"{spec.id}: missing prop file {path}")
    socket_name=socket_name or str(spec.fit.get("socket") or (spec.sockets[0] if spec.sockets else "hand_right"))
    if socket_name not in profile["sockets"]:
        raise ValueError(f"target has no socket {socket_name}")
    ob=join_meshes(import_glb(path), f"prop_{spec.id}")
    verts=[v.co.copy() for v in ob.data.vertices]
    xs=[p.x for p in verts]; ys=[p.y for p in verts]; zs=[p.z for p in verts]
    mn=[min(xs),min(ys),min(zs)]; mx=[max(xs),max(ys),max(zs)]
    dims=[max(mx[i]-mn[i],1e-9) for i in range(3)]
    gripn=list(spec.fit.get("grip_normalized", [.5,.5,.5]))
    while len(gripn)<3: gripn.append(.5)
    from mathutils import Vector, Euler
    grip=Vector(tuple(mn[i]+float(gripn[i])*dims[i] for i in range(3)))
    size_ratio=float(spec.fit.get("size_ratio", .25))
    size_axis=int(spec.fit.get("size_axis", max(range(3),key=lambda i:dims[i])))
    scale=profile["height"]*size_ratio/dims[size_axis]

    # Orientation can be a fixed correction and/or an aim direction. Aim is very
    # useful for clubs/wands: define the prop's shaft axis once, then point it down.
    correction=list(spec.fit.get("rotation_euler_deg", [0,0,0]))
    R=Euler(tuple(math.radians(float(x)) for x in correction), "XYZ").to_matrix()
    aim=spec.fit.get("aim") or {}
    if aim:
        source=_axis(aim.get("axis", [0,0,-1]))
        mode=str(aim.get("mode","direction"))
        if mode=="socket" and aim.get("target_socket") in profile["sockets"]:
            a=Vector(profile["sockets"][socket_name]["position"])
            b=Vector(profile["sockets"][aim["target_socket"]]["position"])
            target=(b-a).normalized() if (b-a).length else Vector((0,0,-1))
        else:
            target=_axis(aim.get("direction", [0,0,-1]))
        R=source.rotation_difference(target).to_matrix() @ R

    mirror = bool(spec.fit.get("mirror_for_left", False) and socket_name.endswith("left"))
    sock=Vector(profile["sockets"][socket_name]["position"])
    off=Vector(tuple(float(x)*profile["height"] for x in spec.fit.get("socket_offset_ratio", [0,0,0])))
    for v in ob.data.vertices:
        q=(v.co-grip)*scale
        if mirror:
            q.x=-q.x
        v.co=sock+off+(R@q)
    ob.data.update(); shade_smooth(ob)
    ob["oddhobb_asset_id"]=spec.id; ob["oddhobb_kind"]="prop"; ob["oddhobb_socket"]=socket_name
    return ob,{"scale":scale,"socket":socket_name}
