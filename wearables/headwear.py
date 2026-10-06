from __future__ import annotations

import math

from .blender_utils import import_glb, join_meshes, shade_smooth, add_subdivision


def _smoothstep(edge0, edge1, x):
    if edge1 <= edge0:
        return 1.0 if x <= edge0 else 0.0
    t = max(0.0, min(1.0, (edge1 - x) / (edge1 - edge0)))
    return t*t*(3.0 - 2.0*t)


def fit_headwear(spec, profile, *, socket_name="headwear"):
    """Fit one authored hat while preserving the crown silhouette.

    The whole hat receives a uniform scale. Only the lower fitting zone receives
    anisotropic X/Y correction, fading to zero above `preserve_from`. This gives
    dog/brick/round heads different brims without crushing the floppy crown.
    """
    path = spec.file_for(profile["body_class"])
    if not path or not path.exists():
        raise FileNotFoundError(f"{spec.id}: missing headwear file {path}")
    ob = join_meshes(import_glb(path), f"wearable_{spec.id}")
    verts = [v.co.copy() for v in ob.data.vertices]
    xs, ys, zs = [v.x for v in verts], [v.y for v in verts], [v.z for v in verts]
    xmin,xmax = min(xs),max(xs); ymin,ymax=min(ys),max(ys); zmin,zmax=min(zs),max(zs)
    hh = max(zmax-zmin, 1e-9)
    fit_fraction = float(spec.fit.get("fit_fraction", .24))
    preserve_from = float(spec.fit.get("preserve_from", .46))
    ease = float(spec.fit.get("ease", 1.08))
    lower = [v for v in verts if (v.z-zmin)/hh <= fit_fraction]
    if len(lower) < 8:
        lower = verts
    lx=[v.x for v in lower]; ly=[v.y for v in lower]
    native_w=max(max(lx)-min(lx),1e-8); native_d=max(max(ly)-min(ly),1e-8)
    native_cx=.5*(max(lx)+min(lx)); native_cy=.5*(max(ly)+min(ly))
    target = profile["head"]
    sx = target["width"] * ease / native_w
    sy = target["depth"] * ease / native_d
    # Uniform scale preserves the authored crown; brim-only deformation corrects
    # aspect ratio around that scale.
    s = math.sqrt(max(sx*sy, 1e-12))
    max_aniso = float(spec.fit.get("max_anisotropy", 1.65))
    ax=max(1/max_aniso,min(max_aniso,sx/s)); ay=max(1/max_aniso,min(max_aniso,sy/s))
    for v in ob.data.vertices:
        p=v.co
        t=(p.z-zmin)/hh
        w=_smoothstep(fit_fraction, preserve_from, t)
        x=native_cx + (p.x-native_cx)*(1+(ax-1)*w)
        y=native_cy + (p.y-native_cy)*(1+(ay-1)*w)
        p.x=x*s; p.y=y*s; p.z=(p.z-zmin)*s
    # Optional authored rotation after canonical Z-up fit.
    from mathutils import Euler, Vector
    rot = spec.fit.get("rotation_euler_deg", [0,0,0])
    R = Euler(tuple(math.radians(float(x)) for x in rot), "XYZ").to_matrix()
    # brim centre after deformation
    lower2=[v.co for v in ob.data.vertices if v.co.z <= fit_fraction*hh*s + 1e-9] or [v.co for v in ob.data.vertices]
    cx=sum(v.x for v in lower2)/len(lower2); cy=sum(v.y for v in lower2)/len(lower2); bz=min(v.z for v in lower2)
    sock=profile["sockets"][socket_name]["position"]
    T=Vector(sock)
    for v in ob.data.vertices:
        q=R @ Vector((v.co.x-cx,v.co.y-cy,v.co.z-bz))
        v.co=T+q
    ob.data.update()
    shade_smooth(ob)
    levels=int(spec.quality.get("subdivision", 1))
    max_faces=int(spec.quality.get("subdivision_face_limit", 180000))
    if levels>0 and len(ob.data.polygons)*(4**levels) <= max_faces:
        add_subdivision(ob, levels)
        shade_smooth(ob)
    ob["oddhobb_asset_id"]=spec.id
    ob["oddhobb_kind"]="headwear"
    return ob, {"scale":s,"brim_anisotropy":[ax,ay],"socket":socket_name}
