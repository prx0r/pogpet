from glb import *
from PIL import Image,ImageDraw,ImageFilter
import colorsys
A='../files/uploads/brick-figure-01a11ea4-bb67-73c3-9c58-dd452e402f1a.glb'
B='../files/uploads/brick-figure-01a11eaa-518e-756f-87a6-1c77a706fadd.glb'
# reference yellow from A's face
ja,pa,ta=load(A); h=pa[0]; C=h['P'][h['I']].mean(1); fc=facecol(h,ta[0])
r=np.hypot(C[:,0]+0.01,C[:,2]); m=(r<0.14)&(C[:,1]>0.47)&(C[:,1]<0.62)&(fc[:,0]>180)&(fc[:,2]<100)
Y=np.median(fc[m],0); print('A yellow',Y.round())
jb,pb,tb=load(B)
def hsvv(c):
    c=c/255.; mx=c.max(-1); mn=c.min(-1); s=np.where(mx>0,(mx-mn)/np.maximum(mx,1e-6),0); return s,mx
masks=[Image.new('L',(t.shape[1],t.shape[0]),0) for t in tb]
forcem=Image.new('L',(tb[0].shape[1],tb[0].shape[0]),0)
facem=Image.new('L',(tb[0].shape[1],tb[0].shape[0]),0)
for p in pb:
    t=tb[p['tex']]; fc=facecol(p,t); C=p['P'][p['I']].mean(1); s,v=hsvv(fc)
    warm=(fc[:,0]>fc[:,2]+25)
    if p['name']=='head':
        rr=np.hypot(C[:,0]+0.013,C[:,2]-0.016); sel=(rr<0.175)&(C[:,1]<0.80)
        force=((rr<0.21)&(C[:,1]<0.60)&(C[:,2]>0.03))|((rr<0.195)&(C[:,1]<0.62)&(C[:,2]>0.0))|((rr<0.20)&(C[:,1]<0.72)&(C[:,2]<=0.0))|((rr<0.188)&(C[:,1]<0.72)&(C[:,2]>-0.05))|((rr<0.23)&(C[:,1]<0.47))
        fo=ImageDraw.Draw(forcem)
        for tri in p['UV'][p['I'][force]]: fo.polygon([(u%1*t.shape[1],vv%1*t.shape[0]) for u,vv in tri],fill=255)
        sel=sel|force
        fsel=sel&(C[:,2]>0.03)&(C[:,1]>0.525)&(C[:,1]<0.76)&(np.abs(C[:,0]+0.013)<0.092)
        fd=ImageDraw.Draw(facem); Hh,Ww=t.shape[:2]
        for tri in p['UV'][p['I'][fsel]]: fd.polygon([(u%1*Ww,vv%1*Hh) for u,vv in tri],fill=255)
    elif p['name']=='legs':
        sel=warm&(C[:,1]<-0.15)&(C[:,1]>-0.33)&(s<0.5)&(v>0.72)
    else:
        sel=warm
    print(p['name'],sel.sum(),'/',len(sel))
    H,W=t.shape[:2]; d=ImageDraw.Draw(masks[p['tex']])
    for tri in p['UV'][p['I'][sel]]:
        d.polygon([(u%1*W,vv%1*H) for u,vv in tri],fill=255)
for i,(t,mk) in enumerate(zip(tb,masks)):
    mk=mk.filter(ImageFilter.MaxFilter(5)); M=np.asarray(mk)>0
    px=t.copy(); s,v=hsvv(px); L=px@[0.299,0.587,0.114]
    skin=M&(px[...,0]>px[...,2]+12)&(s>0.12)
    if i==0: skin=skin|(np.asarray(forcem)>0)
    if i==1:
        Ym=np.load('B_legs_ymap.npy'); skin=(Ym<-0.13)&(Ym>-0.265)&(px[...,0]>px[...,2]+30)&(v>=0.68)&(s<0.5)
        skin=np.asarray(Image.fromarray((skin*255).astype(np.uint8)).filter(ImageFilter.MaxFilter(3)))>0; skin&=(px[...,0]>px[...,2]+30)&(v>=0.62)
    if not skin.any(): continue
    L0=np.percentile(L[skin],70); ratio=L/L0
    FM=(np.asarray(facem)>0) if i==0 else np.zeros_like(M)
    from scipy import ndimage
    cand=(ratio<0.72)&FM
    lab,n=ndimage.label(cand); sizes=ndimage.sum(cand,lab,range(1,n+1))
    keep=np.zeros(n+1,bool); keep[1:]=sizes<2500
    feat=keep[lab]&cand   # eyes, brows, mouth line only on the face front
    tgt=skin&~feat
    k=np.where(FM,np.clip(ratio,0.95,1.08),np.clip(ratio,0.85,1.08))[...,None]*1.02
    px[tgt]=np.clip(Y*k[tgt],0,255)
    # darken kept features to neutral dark brown so they read on yellow
    fm=skin&feat; px[fm]=np.clip(px[fm]*0.6,0,255)
    Image.fromarray(px.astype(np.uint8)).save(f'B_tex{i}_yellow.png'); Image.fromarray((skin*255).astype(np.uint8)).save(f'B_tex{i}_mask.png'); print('tex',i,'skin px',skin.sum(),'L0',round(L0))
