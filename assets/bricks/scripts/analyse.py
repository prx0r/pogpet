import numpy as np, glb
F={'1bf3':'../files/uploads/brick-figure-01a11edc-a8a7-7034-9afe-07d9b1df1bf3.glb','5504':'../files/uploads/brick-figure-01a11ee0-5576-75b1-997b-64ea379f5504.glb'}
def normals(P,I):
    n=np.cross(P[I[:,1]]-P[I[:,0]],P[I[:,2]]-P[I[:,0]]); return n/(np.linalg.norm(n,axis=1,keepdims=True)+1e-12)
if __name__=='__main__':
  for k,f in F.items():
    j,parts,texs=glb.load(f)
    for p in parts:
        if p['name'] not in ('legs','rightArm','torso'): continue
        P=p['P'];I=p['I'];C=P[I].mean(1); col=glb.facecol(p,texs[p['tex']]); n=normals(P,I)
        print(k,p['name'])
        for side,m in ([('front',n[:,2]>0.5),('back',n[:,2]<-0.5)] if p['name']!='rightArm' else [('all',np.ones(len(C),bool))]):
            ys=np.linspace(C[:,1].min(),C[:,1].max(),14); row=[]
            for a,b in zip(ys[:-1],ys[1:]):
                s=m&(C[:,1]>=a)&(C[:,1]<b)
                if s.sum(): row.append(f"{a:.2f}:{tuple(int(x) for x in np.median(col[s],0))}")
            print('  ',side,' | '.join(row))
