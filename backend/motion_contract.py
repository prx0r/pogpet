"""Inspect authored GLB motion without Blender, cloud calls or asset uploads.

This is an authoring gate, not motion capture or automatic retargeting.
"""
from __future__ import annotations
import hashlib
import json
import math
import struct
from pathlib import Path


class MotionError(ValueError):
    pass


def read_glb(path):
    data=Path(path).read_bytes()
    if len(data)<20:
        raise MotionError('Truncated GLB')
    magic,version,size=struct.unpack_from('<III',data)
    if magic!=0x46546c67 or version!=2 or size!=len(data):
        raise MotionError('Expected a complete GLB version 2')
    doc=None;binary=None;offset=12
    while offset<size:
        if offset+8>size:
            raise MotionError('Truncated GLB chunk')
        length,kind=struct.unpack_from('<II',data,offset);offset+=8
        if length%4 or offset+length>size:
            raise MotionError('Invalid GLB chunk length')
        chunk=data[offset:offset+length];offset+=length
        if kind==0x4e4f534a:
            if doc is not None:
                raise MotionError('Duplicate GLB JSON chunk')
            try:doc=json.loads(chunk)
            except (ValueError,UnicodeError):raise MotionError('Invalid GLB JSON') from None
        elif kind==0x004e4942:
            if binary is not None:raise MotionError('Duplicate GLB binary chunk')
            binary=chunk
    if not isinstance(doc,dict):raise MotionError('Missing GLB JSON')
    return doc,binary or b'',hashlib.sha256(data).hexdigest()


def rig_signature(doc,binary):
    nodes=doc.get('nodes',[]);skins=doc.get('skins',[])
    if not skins or not nodes:raise MotionError('The asset needs a skinned skeleton; a static mesh cannot play body motion')
    # Rest transforms, inverse-bind accessors and the complete hierarchy matter.
    # Matching a bone-name list alone does not establish retarget compatibility.
    hierarchy=[]
    for n in nodes:
        hierarchy.append({k:n[k] for k in ('name','children','matrix','translation','rotation','scale') if k in n})
    for skin in skins:
        joints=skin.get('joints',[])
        if not joints or any(not isinstance(j,int) or isinstance(j,bool) or j<0 or j>=len(nodes) for j in joints):
            raise MotionError('Invalid skeleton joints')
    bindings=[]
    for skin in skins:
        entry={k:skin[k] for k in ('joints','skeleton') if k in skin}
        if 'inverseBindMatrices' in skin:
            try:
                a=doc['accessors'][skin['inverseBindMatrices']];v=doc['bufferViews'][a['bufferView']]
                offset=v.get('byteOffset',0)+a.get('byteOffset',0);stride=v.get('byteStride',64)
                if a['type']!='MAT4' or a['componentType']!=5126 or a['count']!=len(skin['joints']) or 'sparse' in a or v.get('buffer',0)!=0 or doc['buffers'][0].get('uri') or offset<0 or stride<64:
                    raise MotionError('Unsupported inverse bind matrices')
                if a.get('byteOffset',0)+(a['count']-1)*stride+64>v['byteLength'] or offset+(a['count']-1)*stride+64>len(binary):raise MotionError('Truncated inverse bind matrices')
                matrices=[struct.unpack_from('<16f',binary,offset+i*stride) for i in range(a['count'])]
                if any(not math.isfinite(x) for matrix in matrices for x in matrix):raise MotionError('Invalid inverse bind matrices')
                entry['inverse_bind_matrices']=matrices
            except (KeyError,IndexError,TypeError,struct.error):raise MotionError('Invalid inverse bind accessor') from None
        bindings.append(entry)
    signature={'nodes':hierarchy,'skins':bindings}
    return hashlib.sha256(json.dumps(signature,sort_keys=True,separators=(',',':')).encode()).hexdigest()


def times(doc,binary,index):
    try:
        a=doc['accessors'][index];view=doc['bufferViews'][a['bufferView']]
        if a['componentType']!=5126 or a['type']!='SCALAR' or 'sparse' in a or view.get('buffer',0)!=0:
            raise MotionError('Animation times need an embedded float32 SCALAR accessor')
        if doc['buffers'][0].get('uri'):raise MotionError('External animation buffers are not supported')
        count=a['count'];stride=view.get('byteStride',4);relative=a.get('byteOffset',0)
        start=view.get('byteOffset',0)+relative
        if not isinstance(count,int) or count<1 or stride<4 or relative<0 or start<0 or relative+(count-1)*stride+4>view['byteLength'] or start+(count-1)*stride+4>len(binary):
            raise MotionError('Animation timestamps are outside the buffer')
        values=[struct.unpack_from('<f',binary,start+i*stride)[0] for i in range(count)]
        if any(not math.isfinite(v) or v<0 for v in values) or any(b<=a for a,b in zip(values,values[1:])):
            raise MotionError('Animation timestamps must be finite, nonnegative and strictly increasing')
        return values
    except (KeyError,IndexError,TypeError,struct.error):
        raise MotionError('Invalid animation time accessor') from None


def _inspect(path):
    doc,binary,digest=read_glb(path);rig=rig_signature(doc,binary);clips=[]
    for i,animation in enumerate(doc.get('animations',[])):
        samplers=animation.get('samplers',[]);channels=animation.get('channels',[])
        if not samplers or not channels:raise MotionError('Animation has no playable channels')
        end=0;start=math.inf
        for channel in channels:
            try:
                target=channel['target'];node=target['node'];sampler=samplers[channel['sampler']]
                if not isinstance(node,int) or node<0 or node>=len(doc['nodes']) or target['path'] not in ('translation','rotation','scale','weights'):
                    raise MotionError('Invalid animation target')
                ts=times(doc,binary,sampler['input']);start=min(start,ts[0]);end=max(end,ts[-1])
            except (KeyError,IndexError,TypeError):raise MotionError('Invalid animation channel') from None
        if end<=0:raise MotionError('Animation has no positive duration')
        clips.append({'index':i,'name':animation.get('name') or f'clip_{i}','start_ms':round(start*1000),'duration_ms':round(end*1000)})
    if not clips:raise MotionError('No animation clips found; export the recorded action with the rig')
    return {'asset':Path(path).name,'asset_sha256':digest,'rig_signature':rig,'clips':clips}


def inspect(path):
    try:
        return _inspect(path)
    except (KeyError,IndexError,TypeError,struct.error,OverflowError):
        raise MotionError('Malformed GLB animation or skeleton metadata') from None


def author_manifest(path,clip_index,rig_id,poster_ms=0):
    if not isinstance(rig_id,str) or not rig_id.strip():raise MotionError('Name the authored rig version')
    report=inspect(path)
    if not isinstance(clip_index,int) or isinstance(clip_index,bool) or not 0<=clip_index<len(report['clips']):raise MotionError('Choose a valid clip index')
    clip=report['clips'][clip_index]
    if not isinstance(poster_ms,int) or isinstance(poster_ms,bool) or not clip['start_ms']<=poster_ms<=clip['duration_ms']:raise MotionError('Poster time is outside the animation')
    return {'version':'oddhobb.motion.v1','asset':report['asset'],'asset_sha256':report['asset_sha256'],
            'rig':{'id':rig_id.strip(),'signature':report['rig_signature']},'clip':clip,
            'poster_ms':poster_ms,'review':{'foot_contact':False,'prop_contact':False,'likeness':False},
            'runtime_ready':False}
