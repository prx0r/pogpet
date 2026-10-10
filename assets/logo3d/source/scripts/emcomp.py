import sys,os,glob
from PIL import Image, ImageFilter, ImageChops
R=sys.argv[1]; B='/workspace/projects/791a7153-8d05-4c9b-b767-8f281ad46eb0/logo3d/out/var'
od=f'{B}/emerge_{R}_final'; os.makedirs(od,exist_ok=True)
fs=sys.argv[2].split(',') if len(sys.argv)>2 else [os.path.basename(p)[1:4] for p in sorted(glob.glob(f'{B}/emerge_{R}_obj/f*.png'))]
import math
def cl(x): return max(0.,min(1.,x))
def ss(x): x=cl(x); return x*x*(3-2*x)
def back(x):
    x=cl(x); return 1+2.7*(x-1)**3+1.7*(x-1)**2
def Sf(f): return 0.002+0.998*(back((f-12)/24) if f<110 else 1-ss((f-110)/18))
for f in fs:
    g=min(1.,max(0.,Sf(int(f)))/0.35)
    f='%03d'%int(f); o=Image.open(f'{B}/emerge_{R}_obj/f{f}.png').convert('RGBA'); sh=Image.open(f'{B}/emerge_{R}_sh/f{f}.png').convert('RGBA')
    a=sh.split()[3].filter(ImageFilter.GaussianBlur(int(R)/60)).point(lambda v:int(v*0.45*g))
    bg=Image.new('RGBA',o.size,(255,255,255,255)); dark=Image.new('RGBA',o.size,(20,20,24,255)); bg.paste(dark,(0,0),a)
    bg.alpha_composite(o); bg.convert('RGB').save(f'{od}/f{f}.png')
