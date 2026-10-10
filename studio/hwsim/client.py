#!/usr/bin/env python3
"""Minimal MCP client for the hwsim server (stands in for Claude/Cursor/any agent).
  python3 client.py --http http://127.0.0.1:8765/mcp list
  python3 client.py --http http://127.0.0.1:8765/mcp call do_light_express '{"emotion":"joy"}'
  python3 client.py --stdio call sim_parts '{}'          (spawns a fresh server per run)
Images returned by tools are saved to out/<tool>_<n>.png."""
import asyncio, base64, json, os, sys
os.environ.setdefault("NO_PROXY", "127.0.0.1,localhost"); os.environ.setdefault("no_proxy", "127.0.0.1,localhost")
from mcp import Client, StdioServerParameters
H = os.path.dirname(os.path.abspath(__file__))

async def main(argv):
    target = StdioServerParameters(command=sys.executable, args=[f'{H}/mcp_server.py']) if argv[0] == '--stdio' else argv[1]
    rest = argv[1:] if argv[0] == '--stdio' else argv[2:]
    async with Client(target, mode='legacy') as c:
        if rest[0] == 'list':
            for t in (await c.list_tools()).tools: print(f'{t.name:22} {t.description[:95]}')
            return
        # call one or more: call name json [name json ...]
        rest = [x for x in rest if x != 'call']; i = 0; k = 0
        while i < len(rest):
            name, a = rest[i], json.loads(rest[i + 1]) if i + 1 < len(rest) else {}; i += 2
            r = await c.call_tool(name, a)
            for part in r.content:
                if part.type == 'text': print(f'{name} →', part.text)
                elif part.type == 'image':
                    k += 1; p = f'{H}/out/{name}_{k}.png'; open(p, 'wb').write(base64.b64decode(part.data)); print(f'{name} → image saved {os.path.relpath(p, H)}')
            if r.is_error: print(f'{name} !! is_error')

if __name__ == '__main__': asyncio.run(main(sys.argv[1:]))
