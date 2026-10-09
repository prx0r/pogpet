exec(open('/workspace/projects/791a7153-8d05-4c9b-b767-8f281ad46eb0/etsy_samples/geo.py').read())
# Croc charm - JLC WJP Full Colour resin, 26 mm domed badge, Jibbitz-style stem 4.2 mm + 6.8 mm stopper.
R = 13.0
disc = chamfered(circle(R, n=200), 3.0, ch=0.5, top=False)
Rs = 30.0; dome = M.sphere(Rs, 240).translate((0, 0, 3.0 + 1.6 - Rs)) ^ cyl(R - 0.6, 6, 0, 0, 2.9, n=200)
face = disc + dome
stem = cyl(2.1, 5.3, 0, 0, -5.0, n=64)
stop = cyl(2.1, 1.7, 0, 0, -6.5, r2=3.4, n=64) .mirror((0, 0, 1)).translate((0, 0, -13.0)) if False else cyl(3.4, 1.7, 0, 0, -6.5, r2=2.1, n=64)
charm = union([face, stem, stop])
# planar UV over the face (art maps to the full 26 mm disc), export textured OBJ package for JLC full colour
t = to_tm(charm)
uv = np.stack([(t.vertices[:, 0] / (2 * R)) + 0.5, (t.vertices[:, 1] / (2 * R)) + 0.5], 1)
import shutil
d = OUT + 'p07_croc_charm/'; os.makedirs(d, exist_ok=True)
from PIL import Image
img = Image.open('/workspace/projects/791a7153-8d05-4c9b-b767-8f281ad46eb0/etsy_samples/props/chris_charm_art.png').convert('RGB')
vis = trimesh.visual.TextureVisuals(uv=uv, image=img)
tt = trimesh.Trimesh(t.vertices, t.faces, visual=vis, process=False)
pk = d + 'jlc/'; os.makedirs(pk, exist_ok=True)
tt.export(pk + 'croc-charm-chris.obj')
for f in os.listdir(pk):
    if f.endswith('.mtl'):
        s = open(pk + f).read().replace('Kd 0.40000000 0.40000000 0.40000000', 'Kd 1.0 1.0 1.0'); open(pk + f, 'w').write(s)
save({'charm': charm}, 'p07_croc_charm')
print(os.listdir(pk))
