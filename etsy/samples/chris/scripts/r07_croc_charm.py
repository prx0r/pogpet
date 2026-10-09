import sys; exec(open('/workspace/projects/791a7153-8d05-4c9b-b767-8f281ad46eb0/etsy_samples/studio.py').read())
reset()
P = 'p07_croc_charm'
foam = noise_bump(mat('foam', hexc('#1f3d6b'), rough=0.55, coat=0.15, spec=0.4), 300, 0.12)
clog = load_part('p07_clog', 'clog', foam, 30)
clog.location.z = -38
def charm():
    bpy.ops.wm.obj_import(filepath=OUT + P + '/jlc/croc-charm-chris.obj', forward_axis='Y', up_axis='Z')
    o = bpy.context.selected_objects[0]; active(o); bpy.ops.object.shade_smooth_by_angle(angle=math.radians(35))
    m = o.data.materials[0]; b = m.node_tree.nodes['Principled BSDF']
    b.inputs['Roughness'].default_value = 0.22; b.inputs['Coat Weight'].default_value = 0.7; b.inputs['Specular IOR Level'].default_value = 0.5
    for n in m.node_tree.nodes:
        if n.type == 'TEX_IMAGE': n.interpolation = 'Cubic'
    return o
ang = math.radians(-8)
c = charm(); c.rotation_euler = (-ang, 0, math.radians(4)); c.location = (0, 70 * math.sin(ang), 70 * math.cos(ang) - 38 + 0.05)
sw = backdrop('#f1ece4', size=2000, curve=320); sw.location = (0, 150, 0)
world(0.3, '#ffffff')
light_area((-220, -220, 300), size=260, energy=3.6e5, color=(1, .95, .88))
light_area((240, -60, 160), size=180, energy=1.2e5, color=(.88, .94, 1))
light_area((0, 240, 260), size=260, energy=1.6e5)
reflector((0, -140, 140), (0, 0, 30), 200, 90, 1.5)
cam = Vector((-22, -140, 118))
camera(cam, (-2, -6, 26), lens=95, fstop=5.6, focus=(cam - Vector((0, -10, 33))).length)
go(P)
