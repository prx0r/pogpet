"""Authoring checks against a small, actual GLB binary."""
import json
import struct
import tempfile
import unittest
from pathlib import Path
from backend.motion_contract import MotionError,inspect,author_manifest


def write_glb(path,animated=True,timestamps=(0.,1.,2.),rest=0):
    binary=struct.pack('<3f',*timestamps)+struct.pack('<9f',*(0.,)*9)
    doc={'asset':{'version':'2.0'},'nodes':[{'name':'Root','children':[1]},{'name':'Spine','translation':[0,rest,0]}],
         'skins':[{'joints':[0,1]}], 'buffers':[{'byteLength':len(binary)}],
         'bufferViews':[{'buffer':0,'byteOffset':0,'byteLength':12},{'buffer':0,'byteOffset':12,'byteLength':36}],
         'accessors':[{'bufferView':0,'componentType':5126,'count':3,'type':'SCALAR'},
                      {'bufferView':1,'componentType':5126,'count':3,'type':'VEC3'}]}
    if animated:doc['animations']=[{'name':'winning_putt','samplers':[{'input':0,'output':1}],'channels':[{'sampler':0,'target':{'node':1,'path':'translation'}}]}]
    text=json.dumps(doc).encode();text+=b' '*((-len(text))%4)
    data=struct.pack('<III',0x46546c67,2,12+8+len(text)+8+len(binary))+struct.pack('<II',len(text),0x4e4f534a)+text+struct.pack('<II',len(binary),0x004e4942)+binary
    path.write_bytes(data)


class MotionAuthoring(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.path=Path(self.tmp.name)/'putt.glb';write_glb(self.path)
    def tearDown(self):self.tmp.cleanup()
    def test_draft_carries_real_duration_identity_and_poster(self):
        m=author_manifest(self.path,0,'oddhobb-humanoid-v1',1800)
        self.assertEqual(m['clip']['duration_ms'],2000)
        self.assertEqual(m['poster_ms'],1800)
        self.assertEqual(len(m['asset_sha256']),64)
        self.assertFalse(m['runtime_ready'])
        self.assertFalse(m['review']['prop_contact'])
    def test_static_mesh_and_invalid_time_or_poster_rejected(self):
        with self.assertRaises(MotionError):author_manifest(self.path,0,'rig-v1',3000)
        write_glb(self.path,animated=False)
        with self.assertRaisesRegex(MotionError,'No animation'):inspect(self.path)
        write_glb(self.path,timestamps=(0.,1.,float('nan')))
        with self.assertRaisesRegex(MotionError,'finite'):inspect(self.path)
    def test_rig_rest_change_invalidates_signature(self):
        a=inspect(self.path);write_glb(self.path,rest=1);b=inspect(self.path)
        self.assertNotEqual(a['rig_signature'],b['rig_signature'])
        self.assertNotEqual(a['asset_sha256'],b['asset_sha256'])
    def test_truncated_glb_rejected(self):
        self.path.write_bytes(self.path.read_bytes()[:-4])
        with self.assertRaisesRegex(MotionError,'complete'):inspect(self.path)

if __name__=='__main__':unittest.main()
