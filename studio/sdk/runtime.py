"""Capability runtime: validate → permission → clamp → execute on a backend (SimDevice now, firmware later).
Every adapter calls invoke(); nothing else touches the device."""
import json, os, re, time
H = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
def load_manifest(id_): return json.load(open(f'{H}/devices/{id_}.device.json'))

def ok(payload): return {'ok': True, 'payload': payload}
def error(msg, hint=''): return {'ok': False, 'error': msg, 'hint': hint}

class Runtime:
    def __init__(self, manifest, backend):
        self.M = manifest; self.dev = backend; self.audit = []
    def invoke(self, command, params=None, caller='studio_sim'):
        params = dict(params or {}); spec = self.M['commands'].get(command)
        if not spec: r = error(f'unknown command {command}', 'supported: ' + ', '.join(self.M['commands']))
        elif caller not in spec['permissions']: r = error(f'{caller} may not call {command}', 'permission denied by device manifest')
        else:
            clean, clamped, err = {}, {}, None
            for k in params:
                if k not in spec['params']: err = error(f'unexpected param {k}', 'allowed: ' + (', '.join(spec['params']) or 'none'))
            for k, p in spec['params'].items():
                if err: break
                if k not in params:
                    if p.get('required'): err = error(f'missing {k}', json.dumps({x: p[x] for x in p if x in ('type', 'enum')})); break
                    if 'default' in p: clean[k] = p['default']
                    continue
                v = params[k]
                if p['type'] in ('number', 'integer'):
                    try: v = float(v) if p['type'] == 'number' else int(float(v))
                    except (TypeError, ValueError): err = error(f'{k} must be {p["type"]}'); break
                    lo, hi = p.get('min', -1e18), p.get('max', 1e18)
                    if not lo <= v <= hi:
                        if p.get('clamp'): clamped[k] = [params[k], min(hi, max(lo, v))]; v = min(hi, max(lo, v))
                        else: err = error(f'{k} out of range [{lo},{hi}]'); break
                if 'enum' in p and v not in p['enum']: err = error(f'{k}={v!r} not supported', 'choose one of: ' + ', '.join(p['enum'])); break
                if 'pattern' in p and not re.match(p['pattern'], str(v)): err = error(f'{k}={v!r} malformed', p['pattern']); break
                clean[k] = v
            if err: r = err
            else:
                name = command.replace('.', '_', 1)
                if command == 'device.health':
                    r = ok(dict(uptime_s=round(self.dev.t, 2), led_ma=round(self.dev.ring.ma(), 1), brightness_cap=round(self.dev.bri_cap(self.dev.sensor.read(self.dev.t)), 3), firmware='sim-0.1.0'))
                else:
                    out = self.dev.call(name, **clean)
                    r = ok({'lux': out} if command == 'sensor.lux' else {'applied': clean, **({'clamped': clamped} if clamped else {})})
        self.audit.append(dict(t=round(self.dev.t, 2), caller=caller, command=command, params=params, ok=r['ok']))
        return r
