#!/usr/bin/env python3
"""Generate tiny DEMO assets to verify sockets. Replace with production Meshy assets."""
from __future__ import annotations
from pathlib import Path
import json, sys
import bpy

root=Path(sys.argv[sys.argv.index("--")+1] if "--" in sys.argv else "data/assets/wearables")

def mat(name,c):
    m=bpy.data.materials.new(name);m.use_nodes=True;m.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value=(*c,1);return m

def export(asset_id,build,manifest):
    bpy.ops.wm.read_factory_settings(use_empty=True); objs=build(); d=root/asset_id; d.mkdir(parents=True,exist_ok=True)
    bpy.ops.object.select_all(action="DESELECT")
    for o in objs:o.select_set(True)
    bpy.context.view_layer.objects.active=objs[0]
    bpy.ops.export_scene.gltf(filepath=str(d/"master.glb"),export_format="GLB",use_selection=True,export_yup=True)
    manifest.update({"id":asset_id,"file":"master.glb","source":{"name":"procedural demo","production":False}})
    (d/"asset.json").write_text(json.dumps(manifest,indent=2)+"\n")

def candle():
    bpy.ops.mesh.primitive_cylinder_add(vertices=32,radius=.12,depth=1.0,location=(0,0,.5));b=bpy.context.object;b.data.materials.append(mat("wax",(.9,.78,.56)))
    bpy.ops.mesh.primitive_uv_sphere_add(segments=24,ring_count=12,radius=.10,location=(0,0,1.08));f=bpy.context.object;f.scale=(.6,.6,1.4);f.data.materials.append(mat("flame",(1,.35,.05)))
    return [b,f]

def golf():
    bpy.ops.mesh.primitive_cylinder_add(vertices=16,radius=.025,depth=1.4,location=(0,0,-.55));s=bpy.context.object;s.data.materials.append(mat("metal",(.5,.5,.5)))
    bpy.ops.mesh.primitive_cube_add(size=1,location=(0,.11,-1.25));h=bpy.context.object;h.scale=(.18,.08,.06);h.data.materials.append(mat("head",(.3,.3,.3)))
    return [s,h]

export("demo_candle",candle,{"kind":"prop","sockets":["hand_left","hand_right"],"fit":{"socket":"hand_right","grip_normalized":[.5,.5,.12],"size_ratio":.24,"size_axis":2,"rotation_euler_deg":[0,0,0]}})
export("demo_golf_club",golf,{"kind":"prop","sockets":["hand_left","hand_right"],"fit":{"socket":"hand_right","grip_normalized":[.5,.5,.93],"size_ratio":.58,"size_axis":2,"aim":{"axis":[0,0,-1],"mode":"direction","direction":[.22,.08,-1]}}})
print(f"demo assets -> {root}")
