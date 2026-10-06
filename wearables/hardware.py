from __future__ import annotations


def _material(name, rgb=(0.85,0.85,0.85), rough=.6):
    import bpy
    m=bpy.data.materials.new(name); m.use_nodes=True
    b=m.node_tree.nodes.get("Principled BSDF")
    if b:
        b.inputs["Base Color"].default_value=(*rgb,1)
        b.inputs["Roughness"].default_value=rough
    return m


def cake_topper_spikes(profile, spec=None):
    """Two tapered printable spikes, slightly embedded into the feet/base."""
    import bpy
    h=profile["height"]
    b=profile["bbox"]
    width=b["width"]
    ground=profile["sockets"]["ground"]["position"]
    depth=float((spec.fit if spec else {}).get("depth_ratio", .34))*h
    radius=max(.018*h, .003)
    embed=max(.012*h, .001)
    spread=min(.22*width, .12*h)
    mat=_material("cake_topper_hardware",(.72,.72,.72),.72)
    out=[]
    for i,xoff in enumerate((-spread,spread)):
        ztop=ground[2]+embed
        zbot=ground[2]-depth
        bpy.ops.mesh.primitive_cone_add(vertices=28, radius1=radius*.18, radius2=radius,
                                        depth=ztop-zbot,
                                        location=(ground[0]+xoff,ground[1],.5*(ztop+zbot)))
        ob=bpy.context.active_object; ob.name=f"hardware_cake_spike_{i}"
        ob.data.materials.append(mat); out.append(ob)
    return out,{"generator":"cake_topper_spikes","depth":depth}


def ornament_loop(profile, spec=None):
    """Printable torus loop above top mass, centred over the model."""
    import bpy, math
    h=profile["height"]
    p=profile["sockets"]["head_top"]["position"]
    fit=(spec.fit if spec else {})
    hole=max(float(fit.get("hole_ratio",.055))*h,.004)
    wire=max(float(fit.get("wire_ratio",.026))*h,.002)
    major=hole*.5+wire*.5
    # torus default axis Z; rotate 90deg so hole is vertical.
    bpy.ops.mesh.primitive_torus_add(major_radius=major,minor_radius=wire*.5,
                                    major_segments=40,minor_segments=12,
                                    location=(p[0],p[1],p[2]+major*.82),
                                    rotation=(math.pi/2,0,0))
    ob=bpy.context.active_object; ob.name="hardware_ornament_loop"
    ob.data.materials.append(_material("ornament_loop",(.78,.78,.78),.65))
    return [ob],{"generator":"ornament_loop","hole":hole,"wire":wire}


def static_master(profile, spec=None):
    """Place a pre-authored static master (e.g. cribbage pegs) at a socket.

    No generation, no deformation: exact print dimensions preserved.
    fit: {socket, scale, rotation_euler_deg}.
    """
    import bpy
    from mathutils import Vector
    from .blender_utils import import_glb, join_meshes, rotation_matrix_from_euler_deg
    fit = spec.fit if spec else {}
    sock = str(fit.get("socket", "ground"))
    pos = profile["sockets"].get(sock, profile["sockets"]["ground"])["position"]
    obs = import_glb(spec.file_for(profile["body_class"]))
    ob = join_meshes(obs, f"hardware_{spec.id}")
    s = float(fit.get("scale", 1.0))
    R = rotation_matrix_from_euler_deg(fit.get("rotation_euler_deg", [0, 0, 0]))
    for v in ob.data.vertices:
        v.co = Vector(pos) + R @ (v.co * s)
    ob.data.update()
    ob["oddhobb_asset_id"] = spec.id
    return [ob], {"generator": "static_master", "socket": sock, "scale": s}


GENERATORS={"cake_topper_spikes":cake_topper_spikes,"ornament_loop":ornament_loop,"static_master":static_master}


def build_hardware(spec, profile):
    if spec.generator not in GENERATORS:
        raise ValueError(f"unknown hardware generator {spec.generator!r}")
    return GENERATORS[spec.generator](profile,spec)
