#!/usr/bin/env python3
"""OddHobb hardware-sim MCP server: connect any MCP agent to a simulated board built from supplier part cards.
  stdio:  python3 studio/hwsim/mcp_server.py --board mood_lamp
  http:   python3 studio/hwsim/mcp_server.py --board mood_lamp --http 8765     (→ http://127.0.0.1:8765/mcp)
Device tools come from the board's W3C WoT Thing Description, compiled to tools by the vendored thingwire compiler
(read_* / do_*, same names a real ThingWire gateway would expose for the physical lamp). sim_* tools control the world."""
import argparse, asyncio, base64, json, os, sys
H = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, os.path.dirname(H))
import mcp_types as types
from mcp.server.lowlevel import Server
from hwsim.sim import Board
from hwsim import design as D
from hwsim.td import manifest_to_td, td_input_schema
from hwsim.vendor.thingwire.td_loader import parse_thing_description_dict
from hwsim.vendor.thingwire.tool_compiler import compile_tools

A = argparse.ArgumentParser(); A.add_argument('--board', default='mood_lamp'); A.add_argument('--http', type=int); A.add_argument('--seed', type=int, default=7)
args = A.parse_args()
S = {'board': Board.load(args.board, args.seed), 'design': args.board}
TD = manifest_to_td(S['board'].manifest); TOOLS = compile_tools(parse_thing_description_dict(TD))
ROUTE = {t.name: (t.tool_type, t.source_name) for t in TOOLS}
CMD = {'ambientLux': 'sensor.lux', 'deviceHealth': 'device.health', 'lightExpress': 'light.express', 'lightSet': 'light.set'}

def obj(props=None, req=()): return {'type': 'object', 'properties': props or {}, 'required': list(req)}
SIM = {
 'sim_parts': ('List the simulated board: parts, their supplier part cards (MPN, LCSC, datasheet), verification status, buses and rails.', obj()),
 'sim_state': ('Current simulated time and device state: ambient lux, what firmware measured, LED current, rail peak, faults.', obj()),
 'sim_advance': ('Let simulated time pass so the firmware runs (sensor reads, fades, breathing). Device commands only take visible effect after time passes. Max 120 s per call.',
                 obj({'seconds': {'type': 'number', 'minimum': 0.01, 'maximum': 120}}, ['seconds'])),
 'sim_set_ambient': ('Change the room light the BH1750 sees, optionally ramping over ramp_s seconds (1 lx = dark bedroom, 300-500 = office, 10000+ = daylight).',
                     obj({'lux': {'type': 'number', 'minimum': 0, 'maximum': 100000}, 'ramp_s': {'type': 'number', 'minimum': 0, 'maximum': 600}}, ['lux'])),
 'sim_inject_fault': ('Inject a hardware fault to test how the device and agent cope. ref=U2 (BH1750) faults: nack (sensor off the bus), stuck (frozen reading), none (clear).',
                      obj({'ref': {'type': 'string', 'enum': ['U2']}, 'fault': {'type': 'string', 'enum': ['nack', 'stuck', 'none']}}, ['ref', 'fault'])),
 'sim_snapshot': ('Picture of the lamp right now (LED ring as rendered from the actual WS2812B data stream) plus the last few seconds of colour.', obj({'seconds': {'type': 'number', 'minimum': 1, 'maximum': 60}})),
 'sim_bus_log': ('Last N I2C transactions between the ESP32 firmware and the sensor (addr, data, ACK/NACK).', obj({'last': {'type': 'integer', 'minimum': 1, 'maximum': 200}})),
 'sim_checks': ('Run the safety and hardware acceptance checks over everything simulated so far (LED current, flash rate, night cap, rail limit, bus health, card verification).', obj()),
 'sim_reset': ('Fresh board, time zero. Pass design=<name> to load a design made with design_create (or mood_lamp for the stock board).', obj({'design': {'type': 'string'}, 'seed': {'type': 'integer'}})),
 'design_options': ('What you can design: base templates, parameters with limits, supplies, design rules.', obj()),
 'design_create': ('Create or overwrite a design variant from a base template. Runs design-rule checks; returns errors (must fix) and warnings. Then sim_reset(design=name) to simulate it and design_quote to price it.',
                   obj(D.PARAMS, ['name', 'led_count', 'ring_d_mm', 'supply'])),
 'design_layout': ('Top-down PCB/ring layout preview of a design (PNG) with its key numbers.', obj({'name': {'type': 'string'}}, ['name'])),
 'design_quote': ('Price a design for N units: LCSC parts are LIVE quotes; PCB, assembly and enclosure are JLC estimates until the JLC API is approved. Read-only, orders nothing.',
                  obj({'name': {'type': 'string'}, 'units': {'type': 'integer', 'minimum': 1, 'maximum': 1000}}, ['name', 'units'])),
 'sim_save_trace': ('Save this session (every device call, frame and check) to a JSON trace that can be replayed in Blender or against hardware.', obj({'name': {'type': 'string'}}, ['name'])),
}

async def list_tools(ctx, params):
    out = []
    for t in TOOLS:
        schema = td_input_schema(TD, t.source_name) if t.tool_type == 'action' else obj()
        out.append(types.Tool(name=t.name, description=t.description, input_schema=schema))
    out += [types.Tool(name=k, description=d, input_schema=s) for k, (d, s) in SIM.items()]
    return types.ListToolsResult(tools=out)

def text(x, err=False): return types.CallToolResult(content=[types.TextContent(type='text', text=json.dumps(x, default=str))], is_error=err)

SCHEMAS = {}
async def call_tool(ctx, params):
    n, a, b = params.name, params.arguments or {}, S['board']
    if not SCHEMAS: SCHEMAS.update({t.name: t.input_schema for t in (await list_tools(None, None)).tools})
    if n in SCHEMAS:   # validate every call against the advertised schema; agents get a fixable message, never a stack trace
        import jsonschema
        try: jsonschema.validate(a, SCHEMAS[n])
        except jsonschema.ValidationError as e:
            return text(dict(ok=False, error=f'invalid arguments: {e.message}', hint=f'field {"/".join(map(str, e.path)) or "(root)"}; see the tool schema'), True)
    if n in ROUTE:
        r = b.invoke(CMD[ROUTE[n][1]], a, caller='mcp'); return text(r, not r['ok'])
    if n == 'sim_parts':
        return text(dict(board=b.spec['board'], rails=b.spec['rails'], parts=[dict(ref=p['ref'], qty=p.get('qty', 1), mpn=b.cards[p['card']]['mpn'], lcsc=b.cards[p['card']]['lcsc'],
                    card_status=b.cards[p['card']]['status'], model=b.cards[p['card']]['model'], bus=p.get('bus'), rail=p['rail'],
                    datasheet=b.cards[p['card']].get('datasheet', {}).get('url')) for p in b.spec['parts']]))
    if n == 'sim_state': return text(b.state())
    if n == 'sim_advance': return text(b.advance(min(120, float(a['seconds']))))
    if n == 'sim_set_ambient': b.set_ambient(float(a['lux']), float(a.get('ramp_s', 0))); return text(dict(ok=True, at_t=b.t, lux=a['lux'], ramp_s=a.get('ramp_s', 0)))
    if n == 'sim_inject_fault': return text(dict(ok=True, result=b.inject_fault(a['ref'], a['fault'])))
    if n == 'sim_snapshot':
        png = b.snapshot_png(float(a.get('seconds', 6)))
        return types.CallToolResult(content=[types.ImageContent(type='image', data=base64.b64encode(png).decode(), mime_type='image/png'),
                                             types.TextContent(type='text', text=json.dumps(b.state()))])
    if n == 'sim_bus_log': return text(b.i2c.log[-int(a.get('last', 20)):])
    if n == 'sim_checks': return text([dict(check=c[0], result=c[1], value=c[2]) for c in b.checks()])
    if n == 'sim_reset':
        nm = a.get('design', S['design'])
        try: S['board'] = Board.load(nm, int(a.get('seed', args.seed))); S['design'] = nm
        except FileNotFoundError: return text(dict(ok=False, error=f'no design {nm!r}', hint='design_create first, or use mood_lamp'), True)
        return text(dict(ok=True, t=0, design=nm, leds=S['board'].leds.n, supply_ma=S['board'].rails['5V'].limit, max_led_ma=S['board'].manifest['safety']['max_led_ma']))
    if n == 'design_options':
        return text(dict(bases=['mood_lamp'], params=D.PARAMS, supplies=D.SUPPLIES, rules=dict(reserve_ma=D.RESERVE_MA, led_pitch_min_mm=D.LED_PITCH_MIN_MM, pcb_cheap_tier_max_mm=100)))
    if n == 'design_create':
        try: r = D.create(a)
        except Exception as e: return text(dict(ok=False, error=str(e)), True)
        return text(r, not r['ok'])
    if n in ('design_layout', 'design_quote') and not os.path.exists(f'{H}/designs/{a.get("name")}/template.json'):
        return text(dict(ok=False, error=f'no design {a.get("name")!r}', hint='call design_create first'), True)
    if n == 'design_layout':
        return types.CallToolResult(content=[types.ImageContent(type='image', data=base64.b64encode(D.layout_png(a['name'])).decode(), mime_type='image/png')])
    if n == 'design_quote':
        try: return text(D.quote(a['name'], int(a['units'])))
        except Exception as e: return text(dict(ok=False, error=f'pricing failed: {e}'), True)
    if n == 'sim_save_trace':
        p = f'{H}/out/trace_{"".join(c for c in a["name"] if c.isalnum() or c in "-_")}.json'
        json.dump(dict(board=b.spec['board'], calls=b.calls, checks=b.checks(), frames=b.frames[::2]), open(p, 'w')); return text(dict(ok=True, path=os.path.relpath(p, os.path.dirname(H)), frames=len(b.frames)))
    return text(dict(ok=False, error=f'unknown tool {n}'), True)

server = Server('oddhobb-hwsim', version='0.1.0', instructions=(
    'You are connected to a SIMULATED OddHobb device built from real supplier parts. read_*/do_* tools are the device itself '
    '(same tools the physical product exposes); sim_* tools control the simulated world. Time only passes when you call sim_advance.'),
    on_list_tools=list_tools, on_call_tool=call_tool)

if __name__ == '__main__':
    if args.http:
        import uvicorn; uvicorn.run(server.streamable_http_app(), host='127.0.0.1', port=args.http, log_level='warning')
    else:
        from mcp.server.stdio import stdio_server
        async def main():
            async with stdio_server() as (r, w): await server.run(r, w, server.create_initialization_options())
        asyncio.run(main())
