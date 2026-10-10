"""Pack a prepped OBJ + the source GLB's texture into a JLC full-colour zip (OBJ + MTL + PNG, flat).
python3 pack_jlc.py <prepped_dir> <source.glb> <name> [tex_px=4096]
Writes <prepped_dir>/<name>-jlc.zip. Applies the guide's fixes: Kd/Ka 1.0, v/vt only, 4/5 dp, RGB PNG."""
import sys, os, re, zipfile, io
import trimesh
from PIL import Image
Image.MAX_IMAGE_PIXELS = None
d, glb, name = sys.argv[1], sys.argv[2], sys.argv[3]
px = int(sys.argv[4]) if len(sys.argv) > 4 else 4096
s = trimesh.load(glb)
g = list(s.geometry.values())[0]
tex = g.visual.material.baseColorTexture.convert('RGB')
if max(tex.size) > px: tex = tex.resize((px, px * tex.size[1] // tex.size[0]), Image.LANCZOS)
tname = f'{name}.png'
buf = io.BytesIO(); tex.save(buf, 'PNG', optimize=True); png = buf.getvalue()
if len(png) > 7e6:  # keep zip uploadable: try 3072 then 2048
    for p2 in (3072, 2048):
        t2 = tex.resize((p2, p2 * tex.size[1] // tex.size[0]), Image.LANCZOS); buf = io.BytesIO(); t2.save(buf, 'PNG', optimize=True); png = buf.getvalue()
        if len(png) <= 7e6: tex = t2; break
mtl = f"newmtl {name}\nKa 1.0 1.0 1.0\nKd 1.0 1.0 1.0\nKs 0.0 0.0 0.0\nd 1.0\nillum 1\nmap_Kd {tname}\n"
out = []
with open(os.path.join(d, 'model.obj')) as f:
    for line in f:
        if line.startswith('v '):
            x, y, z = line.split()[1:4]; out.append(f'v {float(x):.4f} {float(y):.4f} {float(z):.4f}\n')
        elif line.startswith('vt '):
            u, v = line.split()[1:3]; out.append(f'vt {float(u):.5f} {float(v):.5f}\n')
        elif line.startswith('f '):
            out.append('f ' + ' '.join('/'.join(p.split('/')[:2]) for p in line.split()[1:]) + '\n')
        elif line.startswith(('vn ', 'mtllib', 'usemtl', 's ', 'o ', 'g ', '#')):
            continue
obj = f'mtllib {name}.mtl\no {name}\nusemtl {name}\n' + ''.join(out)
zp = os.path.join(d, f'{name}-jlc.zip')
with zipfile.ZipFile(zp, 'w', zipfile.ZIP_DEFLATED, compresslevel=9) as z:
    z.writestr(f'{name}.obj', obj); z.writestr(f'{name}.mtl', mtl); z.writestr(tname, png)
print('PACKED', zp, round(os.path.getsize(zp) / 1e6, 2), 'MB', 'tex', tex.size)
