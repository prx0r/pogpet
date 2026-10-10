"""oddhobb.device.v1 manifest → W3C WoT Thing Description 1.1 (the interop format: ThingWire, Azure, node-wot all read it)."""
import json, sys

READS = {'sensor.lux': ('ambientLux', 'number', 'lx'), 'device.health': ('deviceHealth', 'object', None)}

def _schema(p):
    s = {'type': p['type'], 'description': p.get('description', p['type'])}
    if 'enum' in p: s['enum'] = p['enum']; s['description'] = 'one of: ' + ', '.join(p['enum'])
    if 'min' in p: s['minimum'], s['maximum'] = p['min'], p['max']; s['description'] = f"{p['min']}..{p['max']}" + (' (device clamps)' if p.get('clamp') else '')
    if 'default' in p: s['default'] = p['default']
    if 'pattern' in p: s['pattern'] = p['pattern']; s['description'] = 'hex colour like #ff8800'
    return s

def manifest_to_td(M, node='sim-0001'):
    td = {'@context': 'https://www.w3.org/2019/wot/td/v1.1', '@type': 'Thing', 'id': f'urn:oddhobb:{M["device_type"]}:{node}',
          'title': M['display_name'], 'description': f'{M["device_type"]} v{M["version"]} (oddhobb.device.v1)',
          'securityDefinitions': {'nosec_sc': {'scheme': 'nosec'}}, 'security': ['nosec_sc'], 'properties': {}, 'actions': {}}
    form = [{'href': f'mqtt://broker/oddhobb/{node}/cmd', 'op': 'invokeaction'}]
    for name, c in M['commands'].items():
        if name in READS:
            key, typ, unit = READS[name]
            td['properties'][key] = {'type': typ, 'unit': unit, 'readOnly': True, 'description': c['description'].rstrip('.'),
                                     'forms': [{'href': f'mqtt://broker/oddhobb/{node}/{key}', 'op': 'readproperty'}]}
        else:
            key = ''.join(w.capitalize() if i else w for i, w in enumerate(name.replace('.', '_').split('_')))
            td['actions'][key] = {'title': name, 'description': c['description'], 'safe': False, 'idempotent': True, 'forms': form,
                                  'input': {'type': 'object', 'properties': {k: _schema(p) for k, p in c['params'].items()},
                                            'required': [k for k, p in c['params'].items() if p.get('required')]}}
    return td

def td_input_schema(td, action):
    i = td['actions'][action].get('input') or {'type': 'object', 'properties': {}}
    return {'type': 'object', 'properties': i['properties'], 'required': i.get('required', []), 'additionalProperties': False}

if __name__ == '__main__':
    print(json.dumps(manifest_to_td(json.load(open(sys.argv[1]))), indent=1))
