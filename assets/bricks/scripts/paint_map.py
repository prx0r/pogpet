import numpy as np, trimesh
PAL=[('Yellow','#F4D023'),('Light Blue','#9ABCE9'),('Brown','#6A351E'),('Pink','#E4A6BE'),('Tan','#C9AC85'),('White','#F2F0E8'),('Black','#1A1A1A'),('Dark Blue','#5975B1')]
ANCH={0:['F4D023','D4A80A','F0C71A','F9D10C','E0B30B','FAD422','E7BD17'],1:['9ABCE9','97B8E9','AAC6EF','86A5D6','87A7D3','91B1E1','829FD0','CCD8F1'],
      2:['6A351E','471E0A','68361E','9C594B','845B44','4B210F','6D3E2A','69423D'],3:['DDA0B2','EDC7E0','E4A6BE','D45A8C','D59FA8','FBBCD0','AB6D56','B9734D'],
      4:['C7A87F','D7B581','CDAA7D','C9AC85'],5:['EEF0E9','F2F0E8','FFFFFF','EBEEEB','C5BBB0'],6:['1B0F07','000000','333333','633409','5F3010','854823','A87508','8D591B'],7:['5975B1','446289','556B9D','3F5A8C']}
def lab(rgb):
    c=np.asarray(rgb,float)/255; c=np.where(c>0.04045,((c+0.055)/1.055)**2.4,c/12.92)
    M=np.array([[0.4124,0.3576,0.1805],[0.2126,0.7152,0.0722],[0.0193,0.1192,0.9505]]); xyz=c@M.T/np.array([0.9505,1,1.089])
    f=np.where(xyz>0.008856,np.cbrt(xyz),7.787*xyz+16/116)
    return np.stack([116*f[...,1]-16,500*(f[...,0]-f[...,1]),200*(f[...,1]-f[...,2])],-1)
def assign(rgb,mesh,smooth=1,allowed=None):
    a=[];l=[]
    for k,v in ANCH.items():
        for h in v: a.append([int(h[i:i+2],16) for i in (0,2,4)]); l.append(k)
    A=lab(np.array(a)); L=lab(rgb); d=((L[:,None,:]-A[None])**2).sum(-1)
    if allowed is not None:
        d=d+np.where(allowed[:,np.array(l)],0,1e9)
    lab_=np.array(l)[d.argmin(1)]
    adj=mesh.face_adjacency
    for _ in range(smooth):
        votes=np.zeros((len(lab_),len(PAL))); np.add.at(votes,(adj[:,0],lab_[adj[:,1]]),1); np.add.at(votes,(adj[:,1],lab_[adj[:,0]]),1)
        votes[np.arange(len(lab_)),lab_]+=1.5
        if allowed is not None: votes[~allowed]=-1
        lab_=votes.argmax(1)
    return lab_

def region_allowed(mesh,rgb=None):
    C=mesh.triangles_center; n=len(C); al=np.ones((n,len(PAL)),bool)
    zt=C[:,2]>32.3
    face=(C[:,2]>33.5)&(C[:,2]<39.8)&(np.abs(C[:,0])<5.2)&(C[:,1]<-2)
    al[:,6]=face&(np.abs(C[:,0])<3.9)&(C[:,2]<39.2)                          # black: face features only
    al[zt,7]=False                        # dark blue: clothing only
    al[zt,1]=False; al[zt,4]=False; al[zt&~face,5]=False   # head: no blue/tan; white only teeth/eyes
    feat=face&(np.abs(C[:,0])<3.9)&(C[:,2]<39.2)
    al[feat,2]=False                      # features box: darks go black, not hair brown
    edge=face&~feat; al[edge,3]=False; al[edge,5]=False   # fringe/temples: hair or skin only
    al[zt&~((np.abs(C[:,0])>4)&(C[:,2]>40.5))&~face,3]=False   # pink in head only at bows (and lips)
    al[(np.abs(C[:,0])>7.6)&(C[:,2]>24)&~zt,3]=False   # hanging hair over shoulders: no pink
    if rgb is not None:
        r,g,b=[rgb[:,i].astype(int) for i in range(3)]
        pinky=(r>190)&(b>140)&(r-g>35)
        al[zt&~face&~pinky,3]=False      # hair highlights aren't bows
        L=lab(rgb)[:,0]; al[L>58,7]=False  # dark blue only for genuinely dark seams/print
    return al
