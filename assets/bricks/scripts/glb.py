import json,struct,io,numpy as np
from PIL import Image
CT={5126:np.float32,5123:np.uint16,5125:np.uint32,5121:np.uint8}; NC={'SCALAR':1,'VEC2':2,'VEC3':3,'VEC4':4}
def load(f):
    b=open(f,'rb').read(); n=struct.unpack('<I',b[12:16])[0]; j=json.loads(b[20:20+n]); o=20+n; bl=struct.unpack('<I',b[o:o+4])[0]; B=b[o+8:o+8+bl]
    def acc(i):
        a=j['accessors'][i]; bv=j['bufferViews'][a['bufferView']]; st=bv.get('byteOffset',0)+a.get('byteOffset',0)
        k=NC[a['type']]; return np.frombuffer(B,np.dtype(CT[a['componentType']]),a['count']*k,st).reshape(a['count'],k)
    texs=[]
    for im in j['images']:
        bv=j['bufferViews'][im['bufferView']]; texs.append(np.asarray(Image.open(io.BytesIO(B[bv.get('byteOffset',0):bv.get('byteOffset',0)+bv['byteLength']])).convert('RGB')).astype(float))
    parts=[]
    for mi,m in enumerate(j['meshes']):
        for p in m['primitives']:
            mat=j['materials'][p['material']]
            parts.append(dict(name=mat['name'],P=acc(p['attributes']['POSITION']).astype(float),UV=acc(p['attributes']['TEXCOORD_0']).astype(float),I=acc(p['indices']).reshape(-1,3).astype(int),tex=mat['pbrMetallicRoughness']['baseColorTexture']['index']))
    return j,parts,texs
def facecol(part,tex):
    uv=part['UV'][part['I']].mean(1); h,w,_=tex.shape
    return tex[np.clip((uv[:,1]%1)*h,0,h-1).astype(int),np.clip((uv[:,0]%1)*w,0,w-1).astype(int)]
def components(I,nv):
    par=np.arange(nv)
    def find(x):
        while par[x]!=x: par[x]=par[par[x]]; x=par[x]
        return x
    for a,b,c in I:
        ra,rb,rc=find(a),find(b),find(c); par[rb]=ra; par[find(c)]=ra
    roots=np.array([find(i) for i in range(nv)]); return roots
