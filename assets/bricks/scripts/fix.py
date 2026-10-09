import bpy,bmesh,os,sys
D=os.getcwd(); U=D+'/../files/uploads/'
A=U+'brick-figure-01a11ea4-bb67-73c3-9c58-dd452e402f1a.glb'; B=U+'brick-figure-01a11eaa-518e-756f-87a6-1c77a706fadd.glb'
def fresh(): bpy.ops.wm.read_factory_settings(use_empty=True)
def export(p):
    bpy.ops.export_scene.gltf(filepath=p,export_format='GLB',export_image_format='AUTO',export_yup=True)
# ---- A: remove leg stubs
fresh(); bpy.ops.import_scene.gltf(filepath=A)
legs=[o for o in bpy.data.objects if o.type=='MESH' and o.data.materials and o.data.materials[0].name.startswith('legs')][0]
bm=bmesh.new(); bm.from_mesh(legs.data)
dead=[f for f in bm.faces if -0.376<f.calc_center_median().z<-0.283 and all(abs(v.co.x)<0.236 and abs(v.co.y)<0.112 for v in f.verts)]
print('A stub faces',len(dead))
bmesh.ops.delete(bm,geom=dead,context='FACES')
bmesh.ops.delete(bm,geom=[v for v in bm.verts if not v.link_faces],context='VERTS')
low=[v for v in bm.verts if v.co.z<-0.30]; print('moved verts',len(low))
for v in low: v.co.z+=0.092
# match B's lower-body length: squash everything below the torso
k=(0.75-0.15)/(0.86-0.15)
for v in bm.verts:
    if v.co.z<-0.15: v.co.z=-0.15+(v.co.z+0.15)*k
bm.to_mesh(legs.data); bm.free()
export(D+'/prod/brick-figure-2e402f1a-prod.glb')
# ---- B: yellow skin, face clean, consistent material
fresh(); bpy.ops.import_scene.gltf(filepath=B)
t0=bpy.data.images.load(D+'/B_tex0_yellow.png'); t0.pack(); t1=bpy.data.images.load(D+'/B_tex1_yellow.png'); t1.pack()
for m in bpy.data.materials:
    if not m.use_nodes: continue
    for n in m.node_tree.nodes:
        if n.type=='TEX_IMAGE': n.image=t1 if m.name.startswith('legs') else t0
        if n.type=='BSDF_PRINCIPLED': n.inputs['Metallic'].default_value=0.1; n.inputs['Roughness'].default_value=0.4
export(D+'/prod/brick-figure-a706fadd-prod.glb')
