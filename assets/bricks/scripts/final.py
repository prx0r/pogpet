import numpy as np, json, struct, io, glb
from PIL import Image, ImageDraw
from analyse import F, normals
YEL=np.array([250,211,33.])
def lum(a): return a@np.array([.299,.587,.114])
def mask_for(p,sel,shape):
    h,w=shape[:2]; im=Image.new('L',(w,h),0); d=ImageDraw.Draw(im)
    uv=p['UV'][p['I'][sel]]
    for t in uv:
        pts=[(float(u%1*w) if u!=1 else w-1, float(v%1*h) if v!=1 else h-1) for u,v in t]
        d.polygon(pts,fill=255,outline=255)
    return np.asarray(im)>0
def blue2(tex,m,target):
    px=tex[m]; b=(px[:,2]-px[:,0])>25; px[b]=np.array(target)*np.clip(lum(px[b])/max(np.median(lum(px[b])),1),.9,1.05)[:,None] if b.any() else px[b]; tex[m]=px
def recolour(tex,m,target,lo=.9,hi=1.05):
    L=lum(tex[m]); ref=np.median(L); r=np.clip(L/ref,lo,hi)[:,None]
    tex[m]=np.clip(np.array(target)*r,0,255)
def clean(tex,m,target,thr=45):
    px=tex[m]; d=np.linalg.norm(px-np.array(target),axis=1); bad=d>thr
    px[bad]=np.array(target)*np.clip(lum(px[~bad]).mean()/lum(np.array(target)),0.85,1.1) if (~bad).any() else target
    tex[m]=px
def info(p):
    P,I=p['P'],p['I']; return P[I].mean(1), normals(P,I)
def run(key,ops,out):
    j,parts,texs=glb.load(F[key]); texs=[t.copy() for t in texs]
    cov=[np.zeros(t.shape[:2],bool) for t in texs]
    for q in parts: cov[q['tex']]|=mask_for(q,np.ones(len(q['I']),bool),texs[q['tex']].shape)
    for name,pred,op,arg in ops:
        p=[q for q in parts if q['name']==name][0]; C,n=info(p); sel=pred(C,n)
        m=mask_for(p,sel,texs[p['tex']].shape)
        m=dil(m,cov[p['tex']]); print(key,name,op,sel.sum(),'faces',m.sum(),'px')
        {'recolour':recolour,'clean':clean,'blue2':blue2}[op](texs[p['tex']],m,arg)
    write(F[key],texs,out)
    for i,t in enumerate(texs): Image.fromarray(t.astype(np.uint8)).save(f'new/{key}_final_tex{i}.png')
def write(src,texs,out):
    b=open(src,'rb').read(); n=struct.unpack('<I',b[12:16])[0]; j=json.loads(b[20:20+n]); o=20+n; bl=struct.unpack('<I',b[o:o+4])[0]; B=b[o+8:o+8+bl]
    rep={}
    for i,im in enumerate(j['images']):
        bio=io.BytesIO(); Image.fromarray(texs[i].astype(np.uint8)).save(bio,'PNG'); rep[im['bufferView']]=bio.getvalue(); im['mimeType']='image/png'
    nb=bytearray()
    for vi,bv in enumerate(j['bufferViews']):
        d=rep.get(vi, B[bv.get('byteOffset',0):bv.get('byteOffset',0)+bv['byteLength']])
        while len(nb)%4: nb+=b'\0'
        bv['byteOffset']=len(nb); bv['byteLength']=len(d); nb+=d
    while len(nb)%4: nb+=b'\0'
    j['buffers'][0]['byteLength']=len(nb)
    js=json.dumps(j,separators=(',',':')).encode();  js+=b' '*((4-len(js)%4)%4)
    tot=12+8+len(js)+8+len(nb)
    open(out,'wb').write(b'glTF'+struct.pack('<II',2,tot)+struct.pack('<I',len(js))+b'JSON'+js+struct.pack('<I',len(nb))+b'BIN\0'+nb)
from scipy.ndimage import binary_dilation
def dil(m,c): return m|(binary_dilation(m,iterations=4)&~c)
ALL=lambda C,n: np.ones(len(C),bool)
PINK=[244,182,200]; SHIRT=[160,192,239]; DRESS=[150,183,226]
BACK=lambda C,n:(C[:,2]<-0.01)
REC=lambda C,n:(C[:,2]<-0.01)&(np.abs(n[:,2])<0.6)
OUT=lambda C,n:(n[:,2]<-0.6)
TAN=[203,172,131]
INT=lambda C,n:((n[:,2]<-0.3)&(C[:,2]>-0.03))|((n[:,2]>0.3)&(C[:,2]<0.0))
pyj=[('rightArm',lambda C,n:(C[:,1]>-0.03)&(C[:,1]<0.19),'recolour',YEL),
     ('leftArm', lambda C,n:(C[:,1]>-0.03)&(C[:,1]<0.19),'recolour',YEL),
     ('torso',   lambda C,n:(C[:,2]<-0.02)&(n[:,2]<-0.2)&(C[:,1]<0.38),'clean',SHIRT),
     ('legs',    lambda C,n:C[:,1]>0.095,'recolour',PINK),
     ('legs',    lambda C,n:BACK(C,n)&(C[:,1]<0.09)&(C[:,1]>-0.41),'recolour',[150,182,230])]
drs=[('rightArm',lambda C,n:C[:,1]>-0.03,'recolour',YEL),
     ('leftArm', lambda C,n:C[:,1]>-0.03,'recolour',YEL),
     ('legs',    lambda C,n:C[:,1]>0.095,'recolour',DRESS),
     ('legs',    lambda C,n:(~BACK(C,n))&(C[:,1]<-0.09)&(C[:,1]>-0.19),'recolour',YEL),
     ('legs',    lambda C,n:(~BACK(C,n))&(C[:,1]<=-0.19)&(C[:,1]>-0.235),'blue2',YEL),
     ('legs',    lambda C,n:BACK(C,n)&(C[:,1]<0.09)&(C[:,1]>-0.09),'recolour',DRESS),
     ('legs',    lambda C,n:OUT(C,n)&(C[:,1]<=-0.09)&(C[:,1]>-0.19),'recolour',TAN),
     ('legs',    lambda C,n:REC(C,n)&(C[:,1]<=-0.09)&(C[:,1]>-0.15),'recolour',DRESS),
     ('legs',    lambda C,n:REC(C,n)&(C[:,1]<=-0.15)&(C[:,1]>-0.42),'recolour',TAN),
     ('legs',    lambda C,n:OUT(C,n)&(C[:,1]<=-0.19)&(C[:,1]>-0.42),'recolour',TAN),
     ('legs',    lambda C,n:INT(C,n)&(C[:,1]>-0.2)&(C[:,1]<0.095),'recolour',DRESS),
     ('legs',    lambda C,n:INT(C,n)&(C[:,1]<=-0.2),'recolour',TAN)]
import sys
if 'p' in sys.argv[1:]: run('1bf3',pyj,'prod/brick-figure-pyjama-final.glb')
if 'd' in sys.argv[1:]: run('5504',drs,'prod/brick-figure-dress-final.glb')
