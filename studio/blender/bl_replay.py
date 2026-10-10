"""Layer C: play the recorded light trace through a physical lamp model in Blender (Cycles CPU).
  blender -b -P studio/blender/bl_replay.py -- <trace_keys.json> <outdir> [glb]
12 LED emitters at the PCB ring under a frosted diffuser dome; room light follows the trace's lux.
With a GLB (e.g. the fairy house), the emitters are placed at its window empties named LED_* instead (TODO when the GLB exists)."""
import bpy, sys, json, math, os
argv = sys.argv[sys.argv.index('--') + 1:]; keys = json.load(open(argv[0])); out = argv[1]; os.makedirs(out, exist_ok=True)
bpy.ops.wm.read_factory_settings(use_empty=True); sc = bpy.context.scene
sc.render.engine = 'CYCLES'; sc.cycles.device = 'CPU'; sc.cycles.samples = 64; sc.cycles.use_denoising = False
sc.render.resolution_x = sc.render.resolution_y = 480; sc.unit_settings.scale_length = 0.001
sc.view_settings.view_transform = 'AgX'

def mat(name, **k):
    m = bpy.data.materials.new(name); m.use_nodes = True; b = m.node_tree.nodes['Principled BSDF']
    for kk, v in k.items(): b.inputs[kk].default_value = v
    return m
base_m = mat('base', **{'Base Color': (0.05, 0.05, 0.06, 1), 'Roughness': 0.5})
dome_m = mat('diffuser', **{'Base Color': (0.95, 0.95, 0.95, 1), 'Roughness': 0.6, 'Transmission Weight': 0.85, 'IOR': 1.5,
                            'Subsurface Weight': 0.3, 'Subsurface Radius': (4, 4, 4)})
desk_m = mat('desk', **{'Base Color': (0.35, 0.25, 0.18, 1), 'Roughness': 0.7})

bpy.ops.mesh.primitive_plane_add(size=600); bpy.context.object.data.materials.append(desk_m)
bpy.ops.mesh.primitive_cylinder_add(radius=34, depth=18, location=(0, 0, 9), vertices=96); bpy.context.object.data.materials.append(base_m)
bpy.ops.mesh.primitive_uv_sphere_add(radius=32, location=(0, 0, 18), segments=96, ring_count=48)
dome = bpy.context.object; dome.data.materials.append(dome_m)
bpy.ops.object.mode_set(mode='EDIT'); import bmesh
bm = bmesh.from_edit_mesh(dome.data); [bm.verts.remove(v) for v in [v for v in bm.verts if v.co.z < -0.01]]; bmesh.update_edit_mesh(dome.data)
bpy.ops.object.mode_set(mode='OBJECT'); mod = dome.modifiers.new('s', 'SOLIDIFY'); mod.thickness = 2.0

leds = []
for i in range(12):
    a = 2 * math.pi * i / 12 - math.pi / 2; x, y = 26 * math.cos(a), 26 * math.sin(a)
    bpy.ops.mesh.primitive_cube_add(size=5, location=(x, y, 19.5)); o = bpy.context.object
    m = bpy.data.materials.new(f'led{i}'); m.use_nodes = True; nt = m.node_tree; nt.nodes.clear()
    em = nt.nodes.new('ShaderNodeEmission'); outn = nt.nodes.new('ShaderNodeOutputMaterial'); nt.links.new(em.outputs[0], outn.inputs[0])
    o.data.materials.append(m)
    bpy.ops.object.light_add(type='POINT', location=(x, y, 23)); L = bpy.context.object; L.data.shadow_soft_size = 2
    leds.append((em, L))

w = bpy.data.worlds.new('room'); sc.world = w; w.use_nodes = True; bg = w.node_tree.nodes['Background']
bpy.ops.object.light_add(type='AREA', location=(-150, -120, 260)); room = bpy.context.object; room.data.size = 300
room.rotation_euler = (math.radians(35), 0, math.radians(-40))
bpy.ops.object.camera_add(location=(0, -150, 88)); cam = bpy.context.object; sc.camera = cam
cam.data.lens = 50; cam.rotation_euler = (math.radians(66), 0, 0)

for k in keys:
    lv = max(0.0, math.log10(max(k['lux'], 1)) / 3)  # 1 lx→0, 1000 lx→1
    bg.inputs['Strength'].default_value = 0.02 + 0.4 * lv; room.data.energy = 1e3 + 4e6 * lv ** 2
    for (em, L), (r, g, b) in zip(leds, k['leds']):
        c = (r / 255, g / 255, b / 255); s = max(c)
        em.inputs['Color'].default_value = (*c, 1); em.inputs['Strength'].default_value = 40 * s
        L.data.color = c if s > 0 else (1, 1, 1); L.data.energy = 900 * s
    sc.render.filepath = f'{out}/c_{k["t"]:05.1f}.png'; bpy.ops.render.render(write_still=True)
print('LAYER_C_DONE', len(keys))
