"""Muse Gadgets adapter (protocol per facebookincubator/muse-gadget-sdk linux/src/musegadget/link_client.py, Apache-2.0).
Control stream messages are JSON, each prefixed with a little-endian u32 length.
  device → VM: {"type":"req","id":..,"method":"link.register","params":{node_id, display_name, platform, version, device_family, model_id, is_wakeup_supported, commands_v2}}
  VM → device: {"method":"link.invoke","id":..,"command":..,"params":{..},"timeout_ms":..}
  device → VM: {"method":"link.result","id":..,"ok":true,"payload":{..}} | {"ok":false,"error":".."}
commands_v2 entries use the SDK's COMMAND_SPECS shape: {description, required:{p:{type,description}}, optional:{..}, timeout_ms?}.
Transport (Noise XX over wss, BLE pairing, per-VM bearer) is NOT reimplemented here: production uses the SDK's own
link client / ESP32 firmware and plugs this adapter's to_commands_v2() + handle_invoke() into it.
Not tested against a live Muse VM (pairing needs a Muse account; out of scope for this studio)."""
import json, struct

def _desc(p):
    d = p.get('type', 'string')
    if 'enum' in p: d += ', one of: ' + ', '.join(p['enum'])
    if 'min' in p: d += f', {p["min"]}..{p["max"]}' + (' (clamped)' if p.get('clamp') else '')
    if 'default' in p: d += f', default {p["default"]}'
    return d

def to_commands_v2(manifest):
    out = {}
    for name, c in manifest['commands'].items():
        if 'muse' not in c['permissions']: continue
        req = {k: {'type': p['type'], 'description': _desc(p)} for k, p in c['params'].items() if p.get('required')}
        opt = {k: {'type': p['type'], 'description': _desc(p)} for k, p in c['params'].items() if not p.get('required')}
        out[name] = {'description': c['description'], 'required': req, 'optional': opt}
    return out

def register_message(manifest, node_id, req_id='reg-1'):
    return {'type': 'req', 'id': req_id, 'method': 'link.register', 'params': {
        'node_id': node_id, 'display_name': manifest['display_name'], 'platform': 'linux', 'version': manifest['version'],
        'device_family': 'homehub', 'model_id': manifest['device_type'], 'is_wakeup_supported': False,
        'commands_v2': to_commands_v2(manifest)}}

def encode(obj):
    b = json.dumps(obj, separators=(',', ':')).encode(); return struct.pack('<I', len(b)) + b
def decode(buf):
    out = []
    while len(buf) >= 4:
        n = struct.unpack('<I', buf[:4])[0]
        if len(buf) < 4 + n: break
        out.append(json.loads(buf[4:4 + n])); buf = buf[4 + n:]
    return out, buf

class MuseAdapter:
    def __init__(self, runtime): self.rt = runtime
    def handle_frame(self, frame: bytes) -> bytes:
        out = b''
        for m in decode(frame)[0]:
            if m.get('method') == 'link.invoke':
                r = self.rt.invoke(m.get('command', ''), m.get('params') or {}, caller='muse')
                out += encode({'method': 'link.result', 'id': m['id'], **r})
        return out

class LoopbackVM:
    """Stands in for the Muse VM: sends link.invoke frames, reads link.result frames. Local only."""
    def __init__(self, adapter): self.a = adapter; self.n = 0
    def invoke(self, command, params):
        self.n += 1
        res = decode(self.a.handle_frame(encode({'method': 'link.invoke', 'id': f'inv-{self.n}', 'command': command, 'params': params, 'timeout_ms': 30000})))[0][0]
        return {k: v for k, v in res.items() if k not in ('method', 'id')}
