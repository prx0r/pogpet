"""MCP adapter: tools/list and tools/call (JSON-RPC 2.0) over the same runtime. Tool names use '_' (light_express)."""
import json
TYPES = {'string': 'string', 'number': 'number', 'integer': 'integer'}
def tools_list(manifest):
    tools = []
    for name, c in manifest['commands'].items():
        if 'mcp' not in c['permissions']: continue
        props = {}
        for k, p in c['params'].items():
            s = {'type': TYPES[p['type']]}
            for a in ('enum', 'default'): 
                if a in p: s[a] = p[a]
            if 'min' in p: s['minimum'], s['maximum'] = p['min'], p['max']
            props[k] = s
        tools.append({'name': name.replace('.', '_'), 'description': c['description'],
                      'inputSchema': {'type': 'object', 'properties': props, 'required': [k for k, p in c['params'].items() if p.get('required')]}})
    return tools
class MCPAdapter:
    def __init__(self, runtime): self.rt = runtime
    def handle(self, req):
        if req['method'] == 'tools/list': return {'jsonrpc': '2.0', 'id': req['id'], 'result': {'tools': tools_list(self.rt.M)}}
        if req['method'] == 'tools/call':
            p = req['params']; r = self.rt.invoke(p['name'].replace('_', '.', 1), p.get('arguments', {}), caller='mcp')
            return {'jsonrpc': '2.0', 'id': req['id'], 'result': {'content': [{'type': 'text', 'text': json.dumps(r)}], 'isError': not r['ok']}}
        return {'jsonrpc': '2.0', 'id': req['id'], 'error': {'code': -32601, 'message': 'method not found'}}
