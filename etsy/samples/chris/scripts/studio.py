# Shared Blender studio for OddHobb Etsy sample heroes. exec() this from a build script.
import bpy, bmesh, math, os, sys
from mathutils import Vector, Euler

ROOT = '/workspace/projects/791a7153-8d05-4c9b-b767-8f281ad46eb0'
FONTS = ROOT + '/pogpet/assets/fonts/'
OUT = ROOT + '/etsy_samples/out/'
os.makedirs(OUT, exist_ok=True)

def reset():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.unit_settings.system = 'METRIC'; sc.unit_settings.scale_length = 0.001  # 1 BU = 1 mm
    return sc

def apply(o, loc=True, rot=True, scale=True):
    bpy.ops.object.select_all(action='DESELECT'); o.select_set(True); bpy.context.view_layer.objects.active = o
    bpy.ops.object.transform_apply(location=loc, rotation=rot, scale=scale)

def active(o):
    bpy.ops.object.select_all(action='DESELECT'); o.select_set(True); bpy.context.view_layer.objects.active = o

def mod(o, kind, **kw):
    active(o); m = o.modifiers.new(kind.lower(), kind)
    for k, v in kw.items(): setattr(m, k, v)
    bpy.ops.object.modifier_apply(modifier=m.name); return o

def boolean(a, b, op='UNION', keep=False):
    active(a); m = a.modifiers.new('b', 'BOOLEAN'); m.operation = op; m.object = b; m.solver = 'EXACT'
    bpy.ops.object.modifier_apply(modifier='b')
    if not keep: bpy.data.objects.remove(b, do_unlink=True)
    return a

def cyl(r, h, x=0, y=0, z=0, v=128, r2=None, name='cyl'):
    if r2 is None:
        bpy.ops.mesh.primitive_cylinder_add(radius=r, depth=h, location=(x, y, z + h / 2), vertices=v)
    else:
        bpy.ops.mesh.primitive_cone_add(radius1=r, radius2=r2, depth=h, location=(x, y, z + h / 2), vertices=v)
    o = bpy.context.object; o.name = name; return o

def box(sx, sy, sz, x=0, y=0, z=0, name='box', bevel=0, seg=3):
    bpy.ops.mesh.primitive_cube_add(size=1, location=(x, y, z + sz / 2)); o = bpy.context.object
    o.scale = (sx, sy, sz); apply(o); o.name = name
    if bevel: mod(o, 'BEVEL', width=bevel, segments=seg, limit_method='ANGLE')
    return o

def sphere(r, x=0, y=0, z=0, seg=64, name='sph'):
    bpy.ops.mesh.primitive_uv_sphere_add(radius=r, location=(x, y, z), segments=seg, ring_count=seg // 2)
    o = bpy.context.object; o.name = name; bpy.ops.object.shade_smooth(); return o

def text(s, size, x=0, y=0, z=0, depth=1.0, font='Inter-Bold.ttf', maxw=None, align='CENTER', rot=(0, 0, 0), spacing=1.0, name='txt'):
    bpy.ops.object.text_add(location=(0, 0, 0)); t = bpy.context.object; t.name = name
    t.data.body = s; t.data.font = bpy.data.fonts.load(FONTS + font, check_existing=True)
    t.data.size = size; t.data.extrude = depth / 2; t.data.align_x = align; t.data.align_y = 'CENTER'
    t.data.space_character = spacing; t.data.resolution_u = 6
    bpy.ops.object.convert(target='MESH'); t = bpy.context.object
    apply(t)
    if maxw:
        w = t.dimensions.x
        if w > maxw:
            f = maxw / w; t.scale = (f, f, 1); apply(t)
    # text extrude is centred on z=0 -> shift so bottom at 0
    zmin = min(v.co.z for v in t.data.vertices); [setattr(v.co, 'z', v.co.z - zmin) for v in t.data.vertices]
    t.rotation_euler = rot; t.location = (x, y, z); apply(t)
    mod(t, 'WELD', merge_threshold=0.001)
    return t

def smooth(o, angle=35):
    active(o); bpy.ops.object.shade_smooth_by_angle(angle=math.radians(angle))

# ---------- materials ----------
def mat(name, color, rough=0.5, metal=0.0, coat=0.0, sss=0.0, spec=0.5, transm=0.0):
    m = bpy.data.materials.new(name); m.use_nodes = True
    b = m.node_tree.nodes['Principled BSDF']
    b.inputs['Base Color'].default_value = (*color, 1)
    b.inputs['Roughness'].default_value = rough; b.inputs['Metallic'].default_value = metal
    b.inputs['Coat Weight'].default_value = coat
    if sss:
        b.inputs['Subsurface Weight'].default_value = sss; b.inputs['Subsurface Radius'].default_value = (1, .5, .3)
        b.inputs['Subsurface Scale'].default_value = 0.6
    b.inputs['Specular IOR Level'].default_value = spec
    b.inputs['Transmission Weight'].default_value = transm
    return m

def noise_bump(m, scale=400, strength=0.08):
    nt = m.node_tree; b = nt.nodes['Principled BSDF']
    n = nt.nodes.new('ShaderNodeTexNoise'); n.inputs['Scale'].default_value = scale; n.inputs['Detail'].default_value = 8
    bp = nt.nodes.new('ShaderNodeBump'); bp.inputs['Strength'].default_value = strength; bp.inputs['Distance'].default_value = 0.05
    nt.links.new(n.outputs['Fac'], bp.inputs['Height']); nt.links.new(bp.outputs['Normal'], b.inputs['Normal'])
    return m

def layer_lines(m, pitch=0.12, strength=0.05, axis='Z'):
    """subtle FDM/SLA layer texture along world Z"""
    nt = m.node_tree; b = nt.nodes['Principled BSDF']
    tc = nt.nodes.new('ShaderNodeTexCoord'); sep = nt.nodes.new('ShaderNodeSeparateXYZ')
    w = nt.nodes.new('ShaderNodeTexWave'); w.wave_type = 'BANDS'; w.bands_direction = axis
    w.inputs['Scale'].default_value = 1.0 / pitch / 6.28 * 6.28; w.inputs['Distortion'].default_value = 0.4
    bp = nt.nodes.new('ShaderNodeBump'); bp.inputs['Strength'].default_value = strength; bp.inputs['Distance'].default_value = 0.02
    nt.links.new(tc.outputs['Object'], w.inputs['Vector']); nt.links.new(w.outputs['Fac'], bp.inputs['Height'])
    nt.links.new(bp.outputs['Normal'], b.inputs['Normal']); return m

def hexc(h):
    h = h.lstrip('#'); c = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    return tuple((x / 12.92) if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4 for x in c)

def setmat(o, m):
    o.data.materials.clear(); o.data.materials.append(m)

# JLC process looks
def mjf_pa12(color='#2b2b2e'):   # MJF nylon: fine matte grain
    return noise_bump(mat('MJF', hexc(color), rough=0.78, spec=0.35), scale=900, strength=0.12)
def sla_resin(color='#f4f1ea', rough=0.32):  # JLC 8001/9600 resin: smooth satin
    return mat('SLA', hexc(color), rough=rough, coat=0.15, sss=0.05)
def wjp_colour(color='#ffffff'):  # full colour resin + oil spray clear coat
    return mat('WJP', hexc(color), rough=0.28, coat=0.6)
def steel_316(polish=True):
    return mat('316L', hexc('#c9ccd1'), rough=0.12 if polish else 0.35, metal=1.0)
def brass():
    return mat('brass', hexc('#d4a64a'), rough=0.18, metal=1.0)

# ---------- scene ----------
def backdrop(color='#efe9df', size=2000, curve=400, rough=0.9):
    """infinite sweep (cyclorama)"""
    bpy.ops.mesh.primitive_plane_add(size=1); p = bpy.context.object; p.name = 'sweep'
    bm = bmesh.new(); bm.from_mesh(p.data); bm.clear()
    n = 32
    prof = [(0, -size, 0)]
    for i in range(n + 1):
        a = i / n * math.pi / 2
        prof.append((0, curve * math.sin(a), curve - curve * math.cos(a)))
    prof.append((0, curve, size))
    vs = []
    for x in (-size, size):
        row = [bm.verts.new((x, y, z)) for (_, y, z) in prof]; vs.append(row)
    for j in range(len(prof) - 1):
        bm.faces.new((vs[0][j], vs[1][j], vs[1][j + 1], vs[0][j + 1]))
    bm.to_mesh(p.data); bm.free(); bpy.ops.object.shade_smooth()
    m = mat('backdrop', hexc(color), rough=rough, spec=0.2); setmat(p, m)
    return p

def light_area(loc, target=(0, 0, 0), size=200, energy=200000, color=(1, 1, 1), shape='DISK'):
    bpy.ops.object.light_add(type='AREA', location=loc); l = bpy.context.object
    l.data.size = size; l.data.energy = energy; l.data.color = color; l.data.shape = shape
    d = Vector(target) - Vector(loc); l.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler(); return l

def world(strength=0.25, color='#ffffff'):
    w = bpy.data.worlds.new('w'); bpy.context.scene.world = w; w.use_nodes = True
    bg = w.node_tree.nodes['Background']; bg.inputs['Color'].default_value = (*hexc(color), 1); bg.inputs['Strength'].default_value = strength

def three_point(scale=1.0, warm=True, key_e=1.0):
    s = scale
    light_area((-260 * s, -300 * s, 360 * s), size=420 * s, energy=2.6e5 * s * s * key_e, color=(1, .96, .9) if warm else (1, 1, 1))
    light_area((330 * s, -180 * s, 200 * s), size=300 * s, energy=0.9e5 * s * s, color=(.92, .96, 1))
    light_area((120 * s, 380 * s, 300 * s), size=260 * s, energy=1.4e5 * s * s, color=(1, 1, 1))

def camera(loc, target, lens=85, fstop=None, focus=None):
    bpy.ops.object.camera_add(location=loc); c = bpy.context.object
    d = Vector(target) - Vector(loc); c.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler()
    c.data.lens = lens; c.data.clip_start = 1; c.data.clip_end = 20000
    if fstop:
        c.data.dof.use_dof = True; c.data.dof.aperture_fstop = fstop
        c.data.dof.focus_distance = focus if focus else d.length
    bpy.context.scene.camera = c; return c

def render(name, res=(2000, 2000), samples=256, final=1600):
    sc = bpy.context.scene; sc.render.engine = 'CYCLES'; sc.cycles.device = 'CPU'
    sc.cycles.samples = samples; sc.cycles.use_adaptive_sampling = True; sc.cycles.adaptive_threshold = 0.015
    sc.cycles.use_denoising = False; sc.cycles.max_bounces = 8; sc.cycles.caustics_reflective = False; sc.cycles.caustics_refractive = False
    sc.render.resolution_x, sc.render.resolution_y = res; sc.render.resolution_percentage = 100
    sc.view_settings.view_transform = 'AgX'; sc.view_settings.look = 'AgX - Medium High Contrast'
    sc.render.film_transparent = False
    raw = OUT + name + '_raw.png'; sc.render.filepath = raw
    sc.render.image_settings.file_format = 'PNG'
    bpy.ops.render.render(write_still=True)
    try:
        from PIL import Image, ImageFilter
        im = Image.open(raw).convert('RGB')
        im = im.filter(ImageFilter.MedianFilter(3)) if samples < 200 else im
        fx, fy = final, int(final * res[1] / res[0])
        im = im.resize((fx, fy), Image.LANCZOS); im.save(OUT + name + '.png', optimize=True)
    except Exception as e:
        print('PIL post failed', e)
    print('RENDERED', OUT + name)

def export_stl(objs, path):
    bpy.ops.object.select_all(action='DESELECT')
    for o in objs: o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]
    bpy.ops.wm.stl_export(filepath=path, export_selected_objects=True, apply_modifiers=True)
    print('STL', path)

def arc_text(s, size, radius, center_deg=90, depth=0.5, z=0, font='Inter-Bold.ttf', inward=False, spacing=1.0, track=1.0):
    """letters along a circle in XY; center_deg=90 -> top. returns joined mesh"""
    letters = []
    # measure widths
    widths = []
    for ch in s:
        if ch == ' ':
            widths.append(size * 0.32); continue
        t = text(ch, size, depth=depth, font=font); widths.append(t.dimensions.x); bpy.data.objects.remove(t)
    gap = size * 0.08 * track
    total = sum(widths) + gap * (len(s) - 1)
    ang_total = total / radius
    sign = -1 if not inward else 1
    a = math.radians(center_deg) - sign * ang_total / 2 * -1
    cur = -total / 2
    objs = []
    for ch, w in zip(s, widths):
        mid = cur + w / 2; cur += w + gap
        if ch == ' ': continue
        th = math.radians(center_deg) - mid / radius * (1 if not inward else -1)
        t = text(ch, size, depth=depth, font=font)
        # centre letter at origin
        bb = [Vector(c) for c in t.bound_box]; cx = (min(v.x for v in bb) + max(v.x for v in bb)) / 2; cy = (min(v.y for v in bb) + max(v.y for v in bb)) / 2
        for v in t.data.vertices: v.co.x -= cx; v.co.y -= cy
        rot = th - math.pi / 2 if not inward else th + math.pi / 2
        t.rotation_euler = (0, 0, rot); t.location = (radius * math.cos(th), radius * math.sin(th), z); apply(t)
        objs.append(t)
    active(objs[0])
    for o in objs: o.select_set(True)
    bpy.ops.object.join(); return bpy.context.object

def join(objs):
    bpy.ops.object.select_all(action='DESELECT')
    for o in objs: o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]; bpy.ops.object.join(); return bpy.context.object

def golf_ball(r=21.35, x=0, y=0, z=None, name='ball'):
    b = sphere(r, x, y, r if z is None else z, seg=128, name=name)
    m = mat('ballwhite', hexc('#f7f7f4'), rough=0.25, coat=0.5)
    nt = m.node_tree; bs = nt.nodes['Principled BSDF']
    v = nt.nodes.new('ShaderNodeTexVoronoi'); v.feature = 'F1'; v.inputs['Scale'].default_value = 0.42; v.inputs['Randomness'].default_value = 0.35
    tc = nt.nodes.new('ShaderNodeTexCoord'); nt.links.new(tc.outputs['Object'], v.inputs['Vector'])
    ramp = nt.nodes.new('ShaderNodeMapRange'); ramp.inputs['From Min'].default_value = 0.0; ramp.inputs['From Max'].default_value = 0.42; ramp.clamp = True; ramp.inputs['To Min'].default_value = 0.0; ramp.inputs['To Max'].default_value = 1.0
    nt.links.new(v.outputs['Distance'], ramp.inputs['Value'])
    bp = nt.nodes.new('ShaderNodeBump'); bp.inputs['Strength'].default_value = 0.5; bp.inputs['Distance'].default_value = 0.6
    nt.links.new(ramp.outputs['Result'], bp.inputs['Height']); nt.links.new(bp.outputs['Normal'], bs.inputs['Normal'])
    setmat(b, m); return b

def felt_green(size=3000, color='#3f7d3a', c1=None, c2=None):
    bpy.ops.mesh.primitive_plane_add(size=size); p = bpy.context.object; p.name = 'green'
    m = mat('green', hexc(color), rough=0.95, spec=0.2)
    nt = m.node_tree; bs = nt.nodes['Principled BSDF']
    n = nt.nodes.new('ShaderNodeTexNoise'); n.inputs['Scale'].default_value = 2.5; n.inputs['Detail'].default_value = 15; n.inputs['Roughness'].default_value = 0.75
    bp = nt.nodes.new('ShaderNodeBump'); bp.inputs['Strength'].default_value = 0.7; bp.inputs['Distance'].default_value = 0.6
    nt.links.new(n.outputs['Fac'], bp.inputs['Height']); nt.links.new(bp.outputs['Normal'], bs.inputs['Normal'])
    n2 = nt.nodes.new('ShaderNodeTexNoise'); n2.inputs['Scale'].default_value = 0.02
    r = nt.nodes.new('ShaderNodeValToRGB'); import colorsys
    base = hexc(color); r.color_ramp.elements[0].color = (*(c1 and hexc(c1) or tuple(x * 0.8 for x in base)), 1); r.color_ramp.elements[1].color = (*(c2 and hexc(c2) or tuple(min(1, x * 1.2) for x in base)), 1)
    nt.links.new(n2.outputs['Fac'], r.inputs['Fac']); nt.links.new(r.outputs['Color'], bs.inputs['Base Color'])
    setmat(p, m); return p

def remesh(o, voxel, smooth_shade=True):
    active(o); m = o.modifiers.new('rm', 'REMESH'); m.mode = 'VOXEL'; m.voxel_size = voxel; m.use_smooth_shade = smooth_shade
    bpy.ops.object.modifier_apply(modifier='rm')
    return o

def solid_text(*a, voxel=0.05, **k):
    t = text(*a, **k); return remesh(t, voxel)

def load_part(prod, part, material=None, angle=32, loc=(0, 0, 0), rot=(0, 0, 0)):
    bpy.ops.wm.obj_import(filepath=OUT + prod + '/' + part + '.obj', forward_axis='Y', up_axis='Z')
    o = bpy.context.selected_objects[0]; o.name = part
    active(o); bpy.ops.object.shade_smooth_by_angle(angle=math.radians(angle))
    if material: setmat(o, material)
    o.rotation_euler = rot; o.location = loc
    return o

def place(objs, loc=(0, 0, 0), rot=(0, 0, 0)):
    """parent-less group transform: create empty and parent"""
    bpy.ops.object.empty_add(location=(0, 0, 0)); e = bpy.context.object
    for o in objs: o.parent = e
    e.location = loc; e.rotation_euler = rot; return e

def is_fast(): return '--fast' in sys.argv
def go(name, samples=110, res=(1800, 1800)):
    if is_fast(): render(name + '_fast', res=(720, int(720 * res[1] / res[0])), samples=40, final=720)
    else:
        render(name, res=res, samples=samples, final=1600)
        import subprocess; subprocess.run(['python3', ROOT + '/etsy_samples/post.py', OUT + name + '_raw.png', OUT + name + '.png', '1600'])

def reflector(loc, target=(0, 0, 0), w=300, h=120, strength=3.0, color=(1, 1, 1)):
    bpy.ops.mesh.primitive_plane_add(size=1, location=loc); p = bpy.context.object; p.scale = (w, h, 1); apply(p, loc=False, rot=False)
    d = Vector(target) - Vector(loc); p.rotation_euler = d.to_track_quat('Z', 'Y').to_euler()
    m = bpy.data.materials.new('refl'); m.use_nodes = True; nt = m.node_tree; nt.nodes.clear()
    e = nt.nodes.new('ShaderNodeEmission'); e.inputs['Color'].default_value = (*color, 1); e.inputs['Strength'].default_value = strength
    o = nt.nodes.new('ShaderNodeOutputMaterial'); nt.links.new(e.outputs[0], o.inputs[0]); setmat(p, m)
    p.visible_camera = False; p.visible_shadow = False
    return p
def anodised(color='#17181b'): return mat('anod', hexc(color), rough=0.32, metal=0.75, coat=0.2)
def laser_mark(): return noise_bump(mat('laser', hexc('#e4e5e7'), rough=0.42, metal=1.0), scale=2000, strength=0.05)

PROPS = ROOT + '/etsy_samples/props/'
_tile_mats = {}
def img_mat(path, rough=0.4, coat=0.3, name=None):
    key = (path, rough)
    if key in _tile_mats: return _tile_mats[key]
    m = bpy.data.materials.new(name or os.path.basename(path)); m.use_nodes = True; nt = m.node_tree; b = nt.nodes['Principled BSDF']
    t = nt.nodes.new('ShaderNodeTexImage'); t.image = bpy.data.images.load(path, check_existing=True); t.interpolation = 'Cubic'
    nt.links.new(t.outputs['Color'], b.inputs['Base Color']); b.inputs['Roughness'].default_value = rough; b.inputs['Coat Weight'].default_value = coat
    _tile_mats[key] = m; return m

def decal(path, w, h, loc, rot=(0, 0, 0), rough=0.4, coat=0.3):
    bpy.ops.mesh.primitive_plane_add(size=1, location=(0, 0, 0)); p = bpy.context.object; p.scale = (w, h, 1); apply(p)
    p.rotation_euler = rot; p.location = loc; setmat(p, img_mat(path, rough, coat)); return p

def mj_tile(face, x=0, y=0, z=0, rz=0, standing=False, back='#1f6f5c', W=22, H=29, T=15):
    ivory = _tile_mats.get('ivory') or mat('ivory', hexc('#f3ecd9'), rough=0.3, coat=0.5, sss=0.08); _tile_mats['ivory'] = ivory
    bk = _tile_mats.get(back) or mat('tileback' + back, hexc(back), rough=0.28, coat=0.6); _tile_mats[back] = bk
    a = box(W, H, T * 0.62, 0, 0, T * 0.38, bevel=1.6, seg=4); setmat(a, ivory)
    b = box(W, H, T * 0.40, 0, 0, 0, bevel=1.6, seg=4); setmat(b, bk)
    d = decal(PROPS + face + '.png', W - 3.6, H - 3.6, (0, 0, T + 0.02))
    for o in (a, b, d): smooth(o, 40) if o is not d else None
    e = place([a, b, d], (x, y, z), (0, 0, rz))
    if standing: e.rotation_euler = (math.radians(90), 0, rz); e.location = (x, y, z + H / 2)
    return e

def wood(size=2000, color='#6b4429', scale=0.004):
    bpy.ops.mesh.primitive_plane_add(size=size); p = bpy.context.object; p.name = 'wood'
    m = mat('wood', hexc(color), rough=0.45, coat=0.25); nt = m.node_tree; b = nt.nodes['Principled BSDF']
    tc = nt.nodes.new('ShaderNodeTexCoord'); mp = nt.nodes.new('ShaderNodeMapping'); mp.inputs['Scale'].default_value = (scale * 1.0, scale * 18, scale)
    n = nt.nodes.new('ShaderNodeTexNoise'); n.inputs['Scale'].default_value = 6; n.inputs['Detail'].default_value = 12; n.inputs['Distortion'].default_value = 3
    w = nt.nodes.new('ShaderNodeTexWave'); w.inputs['Scale'].default_value = 3; w.inputs['Distortion'].default_value = 8; w.inputs['Detail'].default_value = 6
    nt.links.new(tc.outputs['Object'], mp.inputs['Vector']); nt.links.new(mp.outputs['Vector'], w.inputs['Vector'])
    r = nt.nodes.new('ShaderNodeValToRGB'); r.color_ramp.elements[0].color = (*hexc('#4a2c18'), 1); r.color_ramp.elements[1].color = (*hexc(color), 1)
    nt.links.new(w.outputs['Fac'], r.inputs['Fac']); nt.links.new(r.outputs['Color'], b.inputs['Base Color'])
    bp = nt.nodes.new('ShaderNodeBump'); bp.inputs['Strength'].default_value = 0.15; nt.links.new(w.outputs['Fac'], bp.inputs['Height']); nt.links.new(bp.outputs['Normal'], b.inputs['Normal'])
    setmat(p, m); return p

def clear_resin(tint='#eaf4f0', rough=0.06):
    m = mat('clear', hexc(tint), rough=rough, transm=1.0, spec=0.5); m.node_tree.nodes['Principled BSDF'].inputs['IOR'].default_value = 1.5
    return m

def play_card(face, x, y, z, lean=12, rz=0, w=63, h=88):
    """standing card, bottom edge at z, leaning back by lean deg, face toward -y"""
    bpy.ops.mesh.primitive_plane_add(size=1); p = bpy.context.object; p.scale = (w, h, 1); apply(p)
    for v in p.data.vertices: v.co.y += h / 2           # bottom edge at y=0 local
    mod(p, 'SOLIDIFY', thickness=0.3, offset=-1)
    setmat(p, img_mat(PROPS + face + '.png', 0.35, 0.4))
    # face (plane +Z) -> -Y : rotate X +90 then lean back
    p.rotation_euler = (math.radians(90 - lean), 0, rz); p.location = (x, y, z)
    return p

def dart(x, y, zbase, color='#c8242c', tilt=(0, 0), rz=0):
    """dart standing point-down; zbase = where the point tip sits"""
    parts = []
    st = mat('dsteel', hexc('#d0d3d8'), rough=0.2, metal=1.0)
    tung = mat('tung', hexc('#7d8189'), rough=0.3, metal=1.0); noise_bump(tung, 60, 0.4)
    shaft_m = mat('shaft', hexc('#16171a'), rough=0.3, coat=0.5)
    fl = mat('flight' + color, hexc(color), rough=0.35, coat=0.4)
    p = cyl(1.1, 32, 0, 0, 0, r2=1.2, v=24); setmat(p, st); parts.append(p)
    tip = cyl(0.05, 4, 0, 0, -3.9, r2=1.1, v=24); setmat(tip, st); parts.append(tip)
    b = cyl(3.3, 50, 0, 0, 32, v=48); setmat(b, tung); parts.append(b)
    for k in range(6):
        g = cyl(3.45, 1.2, 0, 0, 38 + k * 6.5, v=48); setmat(g, tung); parts.append(g)
    s = cyl(2.6, 36, 0, 0, 82, r2=2.2, v=32); setmat(s, shaft_m); parts.append(s)
    for k in range(4):
        bpy.ops.mesh.primitive_plane_add(size=1); w = bpy.context.object
        bm_ = bmesh.new(); bm_.from_mesh(w.data); bm_.clear()
        vs = [bm_.verts.new(v) for v in [(0, 0, 0), (0, 0, 38), (14, 0, 36), (16, 0, 20), (6, 0, 4)]]
        bm_.faces.new(vs); bm_.to_mesh(w.data); bm_.free()
        mod(w, 'SOLIDIFY', thickness=0.4)
        w.rotation_euler = (0, 0, math.radians(90 * k)); w.location = (0, 0, 98); setmat(w, fl); parts.append(w)
    for o in parts: active(o); bpy.ops.object.shade_smooth()
    e = place(parts, (x, y, zbase), (tilt[0], tilt[1], rz)); return e

def walnut(c1='#3a2215', c2='#6e4a2e', scale=0.16):
    m = mat('walnut', hexc(c2), rough=0.42, coat=0.35); nt = m.node_tree; b = nt.nodes['Principled BSDF']
    tc = nt.nodes.new('ShaderNodeTexCoord')
    w = nt.nodes.new('ShaderNodeTexWave'); w.wave_type = 'BANDS'; w.bands_direction = 'Y'
    w.inputs['Scale'].default_value = scale; w.inputs['Distortion'].default_value = 1.6; w.inputs['Detail'].default_value = 6; w.inputs['Detail Scale'].default_value = 0.6; w.inputs['Detail Roughness'].default_value = 0.7
    nt.links.new(tc.outputs['Object'], w.inputs['Vector'])
    n = nt.nodes.new('ShaderNodeTexNoise'); n.inputs['Scale'].default_value = 0.8; n.inputs['Detail'].default_value = 10
    nt.links.new(tc.outputs['Object'], n.inputs['Vector'])
    mx = nt.nodes.new('ShaderNodeMix'); mx.data_type = 'FLOAT'; mx.inputs['Factor'].default_value = 0.25
    nt.links.new(w.outputs['Fac'], mx.inputs['A']); nt.links.new(n.outputs['Fac'], mx.inputs['B'])
    r = nt.nodes.new('ShaderNodeValToRGB'); r.color_ramp.elements[0].color = (*hexc(c1), 1); r.color_ramp.elements[1].color = (*hexc(c2), 1)
    nt.links.new(mx.outputs['Result'], r.inputs['Fac']); nt.links.new(r.outputs['Color'], b.inputs['Base Color'])
    bp = nt.nodes.new('ShaderNodeBump'); bp.inputs['Strength'].default_value = 0.08
    nt.links.new(n.outputs['Fac'], bp.inputs['Height']); nt.links.new(bp.outputs['Normal'], b.inputs['Normal'])
    return m

def load_textured(prod, part='chris', rough=0.3, coat=0.6, loc=(0, 0, 0), rot=(0, 0, 0)):
    bpy.ops.wm.obj_import(filepath=OUT + prod + '/' + part + '.obj', forward_axis='Y', up_axis='Z')
    o = bpy.context.selected_objects[0]; active(o); bpy.ops.object.shade_smooth()
    for m in o.data.materials:
        b = m.node_tree.nodes.get('Principled BSDF')
        if b: b.inputs['Roughness'].default_value = rough; b.inputs['Coat Weight'].default_value = coat; b.inputs['Specular IOR Level'].default_value = 0.5
    o.location = loc; o.rotation_euler = rot; return o
