# Emerge loader -> transparent WebP sprite sheet for the Pulse loader engine.
# obj pass (RGBA) over a soft shadow pass, same comp as emcomp.py but keyed to alpha
# so the loader sits on any background. usage: build_sprite.py <px> <out.webp>
import sys, glob, os, math, json
from PIL import Image, ImageFilter, ImageChops, ImageDraw
FALL=Image.new('L',(480,480),0); ImageDraw.Draw(FALL).ellipse((110,110,370,370),fill=255)
FALL=FALL.filter(ImageFilter.GaussianBlur(40))
B='/workspace/projects/791a7153-8d05-4c9b-b767-8f281ad46eb0/logo3d/out/var'
PX=int(sys.argv[1]); OUT=sys.argv[2]
def cl(x): return max(0.,min(1.,x))
def ss(x): x=cl(x); return x*x*(3-2*x)
def back(x): x=cl(x); return 1+2.7*(x-1)**3+1.7*(x-1)**2
def Sf(f): return 0.002+0.998*(back((f-12)/24) if f<110 else 1-ss((f-110)/18))
STEP=int(sys.argv[3]) if len(sys.argv)>3 else 1
Q=int(sys.argv[4]) if len(sys.argv)>4 else 88
objs=sorted(glob.glob(f'{B}/emerge_480_obj/f*.png'))[::STEP]; N=len(objs)
COLS=11; ROWS=math.ceil(N/COLS)
sheet=Image.new('RGBA',(COLS*PX,ROWS*PX),(0,0,0,0))
for k,p in enumerate(objs):
    f=int(os.path.basename(p)[1:4]); g=min(1.,max(0.,Sf(f))/0.35)
    o=Image.open(p).convert('RGBA'); sh=Image.open(p.replace('_obj','_sh')).convert('RGBA')
    a=sh.split()[3].filter(ImageFilter.GaussianBlur(8)).point(lambda v:int(v*0.45*g))
    a=ImageChops.multiply(a,FALL)                      # fade the catcher plane to 0 before the tile edge
    fr=Image.new('RGBA',o.size,(20,20,24,0)); fr.putalpha(a)
    fr.alpha_composite(o)
    fr=fr.crop((72,72,408,408)).resize((PX,PX),Image.LANCZOS)  # mark spans 97..383; keep shadow room
    sheet.paste(fr,((k%COLS)*PX,(k//COLS)*PX))
sheet.save(OUT,'WEBP',quality=Q,method=6)
json.dump({"frames":N,"cols":COLS,"rows":ROWS,"px":PX,"fps":30/STEP},open(OUT.replace('.webp','.json'),'w'))
print(N,sheet.size,os.path.getsize(OUT)//1024,'KB')
