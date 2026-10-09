from glb import *
from PIL import Image
jb,pb,tb=load('../files/uploads/brick-figure-01a11eaa-518e-756f-87a6-1c77a706fadd.glb'); l=pb[4]; t=tb[1]; H,W=t.shape[:2]
Ymap=np.full((H,W),np.nan)
for f in l['I']:
    uv=l['UV'][f]%1*[W,H]; P=l['P'][f]
    x0,y0=np.floor(uv.min(0)).astype(int); x1,y1=np.ceil(uv.max(0)).astype(int)
    xs,ys=np.meshgrid(np.arange(x0,x1+1)+0.5,np.arange(y0,y1+1)+0.5)
    a,b,c=uv; den=(b[1]-c[1])*(a[0]-c[0])+(c[0]-b[0])*(a[1]-c[1])
    if abs(den)<1e-9: continue
    w0=((b[1]-c[1])*(xs-c[0])+(c[0]-b[0])*(ys-c[1]))/den; w1=((c[1]-a[1])*(xs-c[0])+(a[0]-c[0])*(ys-c[1]))/den; w2=1-w0-w1
    ins=(w0>=-0.02)&(w1>=-0.02)&(w2>=-0.02)
    yy=w0*P[0,1]+w1*P[1,1]+w2*P[2,1]
    X=(xs[ins]-0.5).astype(int).clip(0,W-1); Yp=(ys[ins]-0.5).astype(int).clip(0,H-1); Ymap[Yp,X]=yy[ins]
np.save('B_legs_ymap.npy',Ymap)
c=t/255; mx=c.max(-1); mn=c.min(-1); s=(mx-mn)/np.maximum(mx,1e-6)
band=(Ymap<-0.13)&(Ymap>-0.265)
warm=(t[...,0]>t[...,2]+30)
for v0 in [0.6,0.65,0.7,0.75,0.8]:
    m=band&warm&(mx>=v0)&(mx<v0+0.05); print(v0,m.sum(),t[m].mean(0).round() if m.sum() else '')
print('band warm',(band&warm).sum(),'below band warm',((Ymap<=-0.265)&warm).sum(), t[(Ymap<=-0.265)&warm].mean(0).round())
