# Merge colour islands too small to print (equiv. diameter < MIN mm) into the neighbour sharing the longest border.
import numpy as np,trimesh,sys
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components
sys.path.insert(0,'.'); from paint_map import PAL
MIN=float(sys.argv[1]) if len(sys.argv)>1 else 0.8
BLACK_MIN=0.35   # eyes/lash marks are kept smaller on purpose
def islands(m,lab):
    adj=m.face_adjacency; same=lab[adj[:,0]]==lab[adj[:,1]]; a=adj[same]
    n,cc=connected_components(coo_matrix((np.ones(len(a)),(a[:,0],a[:,1])),shape=(len(lab),)*2),directed=False)
    return n,cc
for k in ['pyjama','dress']:
    m=trimesh.load(f'prod/brick-figure-{k}-PLA-sub.stl',process=False); m.merge_vertices()
    lab=np.load(f'prod/paint_{k}.npy').copy(); A=m.area_faces; adj=m.face_adjacency
    tot=np.bincount(lab,A,len(PAL))
    for c in np.where((tot>0)&(tot<3.0))[0]: lab[lab==c]=0   # near-absent colour (e.g. dress lips, sub-nozzle) -> skin
    E=m.vertices[m.face_adjacency_edges]; elen=np.linalg.norm(E[:,0]-E[:,1],axis=1)
    for it in range(12):
        n,cc=islands(m,lab); ia=np.bincount(cc,A,n); d=2*np.sqrt(ia/np.pi)
        icol=np.zeros(n,int); icol[cc]=lab
        thr=np.where(icol==6,BLACK_MIN,MIN)
        tot=np.bincount(lab,A,len(PAL)); thr=np.where(tot[icol]<3.0,1e9,thr)   # drop a colour that is almost absent
        small=d<thr
        if not small.any(): break
        # border length between island i and colour c
        i0,i1=cc[adj[:,0]],cc[adj[:,1]]; diff=i0!=i1
        B=np.zeros((n,len(PAL)))
        np.add.at(B,(i0[diff],lab[adj[diff,1]]),elen[diff]); np.add.at(B,(i1[diff],lab[adj[diff,0]]),elen[diff])
        B[np.arange(n),icol]=-1
        # process smallest first: only islands whose best neighbour isn't itself small-and-merging this round is fine; simple full pass
        tgt=B.argmax(1); ch=small&(B.max(1)>0)
        lab=np.where(ch[cc],tgt[cc],lab)
    for it in range(20):   # leftover zero-area slivers / absent colours: take any non-small neighbour
        n,cc=islands(m,lab); ia=np.bincount(cc,A,n); icol=np.zeros(n,int); icol[cc]=lab
        tot=np.bincount(lab,A,len(PAL)); bad=(ia<0.05)|(tot[icol]<3.0)
        if not bad[cc].any(): break
        f0,f1=adj[:,0],adj[:,1]; b0,b1=bad[cc[f0]],bad[cc[f1]]
        new=lab.copy(); new[f0[b0&~b1]]=lab[f1[b0&~b1]]; new[f1[b1&~b0]]=lab[f0[b1&~b0]]; lab=new
    n,cc=islands(m,lab); np.save(f'prod/paint_{k}_clean.npy',lab)
    used=[c for c in range(len(PAL)) if A[lab==c].sum()>0]
    print(k,'islands ->',n,'| area mm2',{PAL[c][0]:round(A[lab==c].sum(),1) for c in used})
