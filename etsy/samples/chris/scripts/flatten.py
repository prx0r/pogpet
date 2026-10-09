import sys, os, subprocess
from PIL import Image
raw, out = sys.argv[1], sys.argv[2]
im = Image.open(raw).convert('RGBA'); base = Image.new('RGBA', im.size, (245, 245, 243, 255)); base.alpha_composite(im)
flat = out.replace('.png', '_flat.png'); base.convert('RGB').save(flat)
subprocess.run([sys.executable, os.path.dirname(__file__) + '/post.py', flat, out, '1200']); os.remove(flat)
