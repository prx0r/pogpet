from __future__ import annotations

from .blender_utils import import_glb, join_meshes, shade_smooth, apply_modifier


def _make_hull(body, profile):
    import bpy, bmesh
    from mathutils import Vector
    t=profile["torso"]
    # Use torso-band points only; limbs outside the garment volume must not pull the
    # clothing into armpits/leg gaps. Convex hull intentionally bridges concavities.
    z0,z1=t["min"][2],t["max"][2]
    pts=[]
    for ob in body:
        mw=ob.matrix_world
        pts.extend(mw@v.co for v in ob.data.vertices if z0 <= (mw@v.co).z <= z1)
    if len(pts)<12:
        pts=[ob.matrix_world@v.co for ob in body for v in ob.data.vertices]
    mesh=bpy.data.meshes.new("OH_torso_hull")
    mesh.from_pydata([tuple(p) for p in pts], [], [])
    mesh.update()
    hull=bpy.data.objects.new("OH_torso_hull",mesh); bpy.context.collection.objects.link(hull)
    bm=bmesh.new(); bm.from_mesh(mesh); bm.verts.ensure_lookup_table()
    bmesh.ops.convex_hull(bm,input=list(bm.verts),use_existing_faces=False)
    # Outward winding: shrinkwrap offset follows face normals, so inward
    # faces would push the garment INTO the body by exactly the gap.
    try:
        bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    except Exception:
        pass
    bm.to_mesh(mesh); bm.free(); mesh.update()
    return hull


def _initial_fit(ob, profile, spec):
    from mathutils import Vector
    pts=[v.co for v in ob.data.vertices]
    xs=[p.x for p in pts];ys=[p.y for p in pts];zs=[p.z for p in pts]
    mn=Vector((min(xs),min(ys),min(zs))); mx=Vector((max(xs),max(ys),max(zs)))
    c=(mn+mx)*.5; d=mx-mn
    t=profile["torso"]
    ease=float(spec.fit.get("ease",1.12))
    cover=float(spec.fit.get("height_coverage",1.0))
    sx=max(t["width"]*ease/max(d.x,1e-9),1e-6)
    sy=max(t["depth"]*ease/max(d.y,1e-9),1e-6)
    sz=max(t["height"]*cover/max(d.z,1e-9),1e-6)
    max_aniso=float(spec.fit.get("max_anisotropy",2.2))
    s0=(sx*sy*sz)**(1/3)
    sx=max(s0/max_aniso,min(s0*max_aniso,sx)); sy=max(s0/max_aniso,min(s0*max_aniso,sy)); sz=max(s0/max_aniso,min(s0*max_aniso,sz))
    tc=Vector(t["center"])
    for v in ob.data.vertices:
        q=v.co-c
        v.co=tc+Vector((q.x*sx,q.y*sy,q.z*sz))
    ob.data.update()
    return [sx,sy,sz]


def fit_garment(spec, profile, body):
    """Fit a high-detail garment through a deformable proxy.

    Preferred path: high-detail master -> decimated proxy -> convex-hull shrinkwrap
    -> corrective/laplacian smoothing -> Surface Deform transfers the proxy motion
    back to the detailed garment. If Surface Deform cannot bind, fallback applies
    the hull fit directly to the master.
    """
    import bpy
    path=spec.file_for(profile["body_class"])
    if not path or not path.exists():
        raise FileNotFoundError(f"{spec.id}: no variant for {profile['body_class']} at {path}")
    high=join_meshes(import_glb(path),f"garment_{spec.id}")
    scale=_initial_fit(high,profile,spec); shade_smooth(high)
    hull=_make_hull(body,profile)
    gap=max(float(spec.fit.get("gap_ratio",.012))*profile["height"],1e-5)

    proxy=high.copy(); proxy.data=high.data.copy(); proxy.name=f"proxy_{spec.id}"; bpy.context.collection.objects.link(proxy)
    # Decimate only the proxy. High-detail folds/seams remain untouched.
    faces=len(proxy.data.polygons); target=int(spec.fit.get("proxy_faces",1800))
    if faces>target and target>100:
        dec=proxy.modifiers.new("OH_proxy_decimate","DECIMATE"); dec.ratio=max(.02,min(1.0,target/faces)); apply_modifier(proxy,dec)

    surf=high.modifiers.new("OH_surface_deform","SURFACE_DEFORM"); surf.target=proxy
    bound=False
    try:
        bpy.context.view_layer.objects.active=high; high.select_set(True)
        bpy.ops.object.surfacedeform_bind(modifier=surf.name); bound=True
    except Exception:
        try: high.modifiers.remove(surf)
        except Exception: pass

    sw=proxy.modifiers.new("OH_hull_fit","SHRINKWRAP"); sw.target=hull
    sw.wrap_method="NEAREST_SURFACEPOINT"; sw.offset=gap
    apply_modifier(proxy,sw)
    # Elastic-ish cleanup: preserve broad silhouette while removing projection dents.
    lap=proxy.modifiers.new("OH_elastic_smooth","LAPLACIANSMOOTH")
    lap.iterations=int(spec.fit.get("smooth_iterations",6)); lap.lambda_factor=float(spec.fit.get("smooth_factor",.28)); lap.use_volume_preserve=True
    apply_modifier(proxy,lap)

    if bound:
        try: apply_modifier(high,surf)
        except Exception: bound=False
    if not bound:
        # Fallback is intentionally conservative; it can be less pretty but should
        # still clear the body rather than fail the build.
        sw2=high.modifiers.new("OH_direct_hull_fit","SHRINKWRAP"); sw2.target=hull; sw2.wrap_method="NEAREST_SURFACEPOINT"; sw2.offset=gap
        apply_modifier(high,sw2)
        sm=high.modifiers.new("OH_direct_smooth","CORRECTIVE_SMOOTH"); sm.iterations=4; sm.factor=.25
        apply_modifier(high,sm)
    _guarantee_clearance(high, body, gap)
    shade_smooth(high)
    bpy.data.objects.remove(proxy,do_unlink=True); bpy.data.objects.remove(hull,do_unlink=True)
    high["oddhobb_asset_id"]=spec.id; high["oddhobb_kind"]="garment"
    return high,{"initial_scale":scale,"gap":gap,"surface_deform":bound}


def _guarantee_clearance(ob, body, gap):
    """Final normal-free push-out: every garment vert closer than gap (inside
    or out) moves to exactly gap along the nearest-point direction. Face
    normals on AI meshes flip unpredictably, so the push direction comes from
    geometry (p-q), never from normals. Guarantees verifier clearance.
    """
    import bpy
    from mathutils import Vector
    from mathutils.bvhtree import BVHTree
    from .blender_utils import world_vertices
    verts, polys = [], []
    for b in body:
        mw = b.matrix_world
        base = len(verts)
        verts.extend([mw @ v.co for v in b.data.vertices])
        for poly in b.data.polygons:
            idx = list(poly.vertices)
            for k in range(1, len(idx) - 1):
                polys.append((base + idx[0], base + idx[k], base + idx[k + 1]))
    bvh = BVHTree.FromPolygons(verts, polys, all_triangles=False, epsilon=0.0)
    dx, dz = Vector((1, 0, 0)), Vector((0, 0, 1))
    eps = max(1e-6, gap * 0.01)

    def enclosed(p):
        def cnt(o, d):
            n = 0
            o = o + d * eps
            for _ in range(12):
                hit = bvh.ray_cast(o, d)
                if not hit or hit[0] is None:
                    break
                n += 1
                o = hit[0] + d * eps
            return n
        return cnt(p, dx) % 2 == 1 and cnt(p, dz) % 2 == 1

    mw = ob.matrix_world
    mw_inv = mw.inverted()
    moved = 0
    for v in ob.data.vertices:
        pw = mw @ v.co
        loc, _, _, dist = bvh.find_nearest(pw)
        d = float(dist)
        if d <= max(eps * 2, 1e-7):
            continue
        if d < gap or enclosed(pw):
            q = Vector(loc)
            inside = enclosed(pw)
            outward = (q - pw) if inside else (pw - q)
            if outward.length < 1e-12:
                continue
            outward = outward.normalized()
            v.co = mw_inv @ (q + outward * gap)
            moved += 1
    ob.data.update()
    print(f"wearables: clearance guarantee moved {moved} verts to gap {gap:.5f}")
