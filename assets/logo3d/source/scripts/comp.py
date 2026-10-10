import sys,glob,os
from PIL import Image, ImageFilter
os.chdir(os.path.dirname(os.path.abspath(__file__))+'/out/var')
for f in sorted(glob.glob('*_rgba.png')):
    v=f[:-9]; im=Image.open(f).convert('RGBA'); im=im.crop(im.getbbox())
    W=2000; s=1500/max(im.size); im=im.resize((int(im.width*s),int(im.height*s)),Image.LANCZOS)
    x=(W-im.width)//2; y=(W-im.height)//2-40; a=im.split()[3]
    sh=Image.new('L',(W,W),0); sh.paste(a.point(lambda q:q*0.55),(x+40,y+70)); sh=sh.filter(ImageFilter.GaussianBlur(45))
    t=Image.new('RGBA',(W,W),(0,0,0,0)); t.putalpha(sh); t.alpha_composite(im,(x,y)); t.save(f'oddhobb-{v}-transparent.png')
    bgc=(0xEE,0x74,0x10) if not v.endswith('orange') else (24,24,26)
    for n,c in [('white',(255,255,255)),('brand',bgc)]:
        b=Image.new('RGBA',(W,W),c+(255,)); b.alpha_composite(t); b.convert('RGB').save(f'oddhobb-{v}-{n}.png')
