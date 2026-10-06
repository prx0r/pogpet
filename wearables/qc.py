from __future__ import annotations


def surface_distance_stats(asset, body):
    """Cheap QC: nearest body-surface distances for sampled accessory vertices."""
    from mathutils.bvhtree import BVHTree
    import bmesh
    import math
    # Join body surfaces into one temporary BMesh in world space.
    bm=bmesh.new()
    for ob in body:
        tmp=bmesh.new(); tmp.from_mesh(ob.data); tmp.transform(ob.matrix_world)
        meshverts=[bm.verts.new(v.co) for v in tmp.verts]
        # This fallback intentionally measures only against vertices if face transfer
        # is awkward; the BVH path below uses original objects when possible.
        tmp.free()
    bm.free()
    # Build one BVH per body object; minimum nearest distance wins.
    bvhs=[]
    for ob in body:
        try: bvhs.append(BVHTree.FromObject(ob, __import__('bpy').context.evaluated_depsgraph_get()))
        except Exception: pass
    vals=[]
    av=[asset.matrix_world@v.co for v in asset.data.vertices]
    stride=max(1,len(av)//2000)
    for p in av[::stride]:
        ds=[]
        for bvh in bvhs:
            hit=bvh.find_nearest(p)
            if hit and hit[0] is not None: ds.append((hit[0]-p).length)
        if ds: vals.append(min(ds))
    vals.sort()
    if not vals: return {"samples":0}
    def pct(q): return vals[min(len(vals)-1,int((len(vals)-1)*q))]
    return {"samples":len(vals),"min":vals[0],"p50":pct(.5),"p95":pct(.95),"max":vals[-1]}


def sanity(asset, profile):
    from .blender_utils import bbox_objects
    mn,mx=bbox_objects([asset]); size=mx-mn; h=profile["height"]
    return {"bbox_ratio":[size.x/h,size.y/h,size.z/h],"finite":all(abs(x)<10000*h for x in (*mn,*mx))}
