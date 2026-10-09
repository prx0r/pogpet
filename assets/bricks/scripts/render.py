import json,struct,glob,io,numpy as np,sys
from PIL import Image
import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
from matplotlib.collections import PolyCollection
CT={5126:np.float32,5123:np.uint16,5125:np.uint32,5121:np.uint8}; NC={'SCALAR':1,'VEC2':2,'VEC3':3,'VEC4':4}
def load(f):
    b=open(f,'rb').read(); n=struct.unpack('<I',b[12:16])[0]; j=json.loads(b[20:20+n]); o=20+n; bl=struct.unpack('<I',b[o:o+4])[0]; B=b[o+8:o+8+bl]
    def acc(i):
        a=j['accessors'][i]; bv=j['bufferViews'][a['bufferView']]; st=bv.get('byteOffset',0)+a.get('byteOffset',0)
        dt=np.dtype(CT[a['componentType']]); k=NC[a['type']]
        return np.frombuffer(B,dt,a['count']*k,st).reshape(a['count'],k)
    texs=[]
    for im in j['images']:
        bv=j['bufferViews'][im['bufferView']]; texs.append(np.asarray(Image.open(io.BytesIO(B[bv.get('byteOffset',0):bv.get('byteOffset',0)+bv['byteLength']])).convert('RGB'))/255)
    parts=[]
    for m in j['meshes']:
        for p in m['primitives']:
            P=acc(p['attributes']['POSITION']).astype(float); UV=acc(p['attributes']['TEXCOORD_0']).astype(float); I=acc(p['indices']).reshape(-1,3)
            mat=j['materials'][p['material']]; t=texs[mat['pbrMetallicRoughness']['baseColorTexture']['index']]
            parts.append((mat.get('name'),P,UV,I,t))
    return parts
def render(f,out):
    parts=load(f); fig,axs=plt.subplots(1,3,figsize=(12,6),dpi=110)
    for ax,yaw,title in zip(axs,[0,90,180],['front','side','back']):
        polys=[];cols=[];depth=[]
        c,s=np.cos(np.radians(yaw)),np.sin(np.radians(yaw))
        for name,P,UV,I,t in parts:
            X=P[:,0]*c+P[:,2]*s; Z=-P[:,0]*s+P[:,2]*c
            tri=I; uv=UV[tri].mean(1); h,w,_=t.shape
            col=t[np.clip((uv[:,1]%1)*h,0,h-1).astype(int),np.clip((uv[:,0]%1)*w,0,w-1).astype(int)]
            v=np.stack([X,P[:,1]],1)[tri]; e1=np.stack([X,P[:,1],Z],1)[tri]
            nrm=np.cross(e1[:,1]-e1[:,0],e1[:,2]-e1[:,0]); nz=nrm[:,2]/ (np.linalg.norm(nrm,axis=1)+1e-12)
            keep=nz>0; shade=(0.45+0.55*nz[keep])[:,None]
            polys.append(v[keep]); cols.append(np.clip(col[keep]*shade,0,1)); depth.append(Z[tri][keep].mean(1))
        V=np.concatenate(polys);C=np.concatenate(cols);D=np.concatenate(depth);o=np.argsort(D)
        ax.add_collection(PolyCollection(V[o],facecolors=C[o],edgecolors='none',antialiased=False))
        ax.set_xlim(-0.7,0.7);ax.set_ylim(-1.0,1.0);ax.set_aspect('equal');ax.axis('off');ax.set_title(title)
    fig.suptitle(f.split('/')[-1][-12:-4]); fig.tight_layout(); fig.savefig(out); print(out)
for f in sorted(glob.glob('../files/uploads/brick-figure-*.glb')): render(f,f[-12:-4]+'_views.png')
