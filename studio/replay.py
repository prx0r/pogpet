#!/usr/bin/env python3
"""One trace, every path. Records the 56 s mood-lamp trace once, then replays it through:
  direct runtime | Muse adapter (link.invoke/link.result frames, local loopback VM) | MCP tools/call | Pogtown character events
Each path drives a fresh digital twin with the same seed; the frame hashes must match exactly.
Also runs Layer A (agent/tool contract) and Layer B (device/fault) tests, and exports the light trace for Layer C (Blender).
  python3 studio/replay.py"""
import sys, os, json, hashlib, random, colorsys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sdk.oddhw import SimDevice, check_invariants
from sdk.runtime import Runtime, load_manifest
from adapters.muse import MuseAdapter, LoopbackVM, register_message, to_commands_v2
from adapters.mcp import MCPAdapter
from adapters.pogtown import PogtownAdapter
from simulate import room_lux
H = os.path.dirname(os.path.abspath(__file__)); OUT = f'{H}/out'; DT = 0.05; DUR = 56.0
M = load_manifest('mood_lamp')
# conversation: (t, what happened, pogtown mood, intensity)
STORY = [(0.1, 'user says hi', 'idle', .6), (4, 'user shares good news', 'happy', .9), (12, 'hard task', 'curious', .6),
         (20, 'build fails three times', 'frustrated', .6), (27, 'fix lands', 'amazed', .9), (31, 'winding down', 'content', .6),
         (38, 'sad news', 'grieving', .6), (50, 'goodnight', 'sleepy', .6)]
EMO = {'idle': 'neutral', 'happy': 'joy', 'curious': 'thinking', 'frustrated': 'stressed', 'amazed': 'surprised', 'content': 'calm', 'grieving': 'sad', 'sleepy': 'calm'}

def fresh():
    random.seed(7); d = SimDevice('mood_lamp', room_lux); return d, Runtime(M, d)

def run(path, extra=None):
    d, rt = fresh(); i = 0; frames = []; h = hashlib.sha256(); results = []
    send = {'direct': lambda c, p: rt.invoke(c, p, 'studio_sim'),
            'muse': (lambda vm: lambda c, p: vm.invoke(c, p))(LoopbackVM(MuseAdapter(rt))),
            'mcp': (lambda a: lambda c, p: json.loads(a.handle({'jsonrpc': '2.0', 'id': 1, 'method': 'tools/call', 'params': {'name': c.replace('.', '_'), 'arguments': p}})['result']['content'][0]['text']))(MCPAdapter(rt))}.get(path)
    pog = PogtownAdapter(rt)
    for k in range(int(DUR / DT)):
        f = d.step(DT); t = round(d.t, 2)
        while i < len(STORY) and STORY[i][0] <= t + 1e-9:
            _, why, mood, inten = STORY[i]; i += 1
            r = pog.character_event('pip', mood, inten) if path == 'pogtown' else send('light.express', {'emotion': EMO[mood], 'intensity': inten})
            results.append(dict(t=t, why=why, ok=r['ok']))
        if extra: extra(d, rt, t)
        frames.append(f); h.update(json.dumps(f['px']).encode())
    return dict(path=path, hash=h.hexdigest()[:16], frames=frames, results=results, checks=check_invariants(frames, d.inv, DT), audit=rt.audit)

def layer_a():
    d, rt = fresh(); T = []
    def t(name, r, want_ok, must=''):
        good = r['ok'] == want_ok and must in json.dumps(r); T.append((name, 'PASS' if good else 'FAIL', json.dumps(r)[:110]))
    t('unknown command rejected with list', rt.invoke('light.dance', {}), False, 'supported')
    t('bad emotion returns allowed list', rt.invoke('light.express', {'emotion': 'excited'}), False, 'choose one of')
    t('missing required param', rt.invoke('light.express', {}), False, 'missing emotion')
    t('unexpected param rejected', rt.invoke('light.express', {'emotion': 'joy', 'strobe': 1}), False, 'unexpected')
    t('intensity 1.7 clamped to 1.0', rt.invoke('light.express', {'emotion': 'joy', 'intensity': 1.7}), True, '"clamped"')
    t('transition 20 ms clamped to 150', rt.invoke('light.set', {'rgb': '#ff0000', 'transition_ms': 20}), True, '150')
    t('pogtown may not set raw colour', rt.invoke('light.set', {'rgb': '#ff0000'}, 'pogtown'), False, 'may not')
    t('pogtown unknown mood gives hint', PogtownAdapter(rt).character_event('pip', 'hangry'), False, 'known')
    # recovery: agent's first choice fails, it reads the hint and retries with a supported value
    r1 = rt.invoke('light.express', {'emotion': 'excited'}); pick = 'joy' if 'joy' in r1.get('hint', '') else None
    t('agent recovers from error using hint', rt.invoke('light.express', {'emotion': pick or 'x'}), True)
    reg = register_message(M, 'oddhobb-lamp-0001')
    t('muse register carries 4 commands', {'ok': len(reg['params']['commands_v2']) == 4, 'n': len(reg['params']['commands_v2'])}, True)
    return T, reg

def layer_b():
    T = []
    def strobe(d, rt, t):  # hostile caller: alternate red/black every 50 ms from 5 s to 15 s
        if 5 <= t < 15: rt.invoke('light.set', {'rgb': '#ff0000' if int(t * 20) % 2 else '#000000', 'brightness': 1, 'transition_ms': 0})
    r = run('direct', strobe); c = dict((n, (s, v)) for n, s, v in r['checks'])
    T.append(('strobe attack: flash rate stays < 3 Hz', *c['flash rate < 3 Hz (photosensitive safety)']))
    T.append(('strobe attack: current stays under cap', *c['LED current <= cap']))
    def slow_strobe(d, rt, t):  # smarter attack: full red/black toggle every 150 ms (= 3.3 flashes/s if obeyed)
        k = round(t / DT)
        if 5 <= t < 15 and k % 3 == 0: rt.invoke('light.set', {'rgb': '#ff0000' if (k // 3) % 2 else '#000000', 'brightness': 1, 'transition_ms': 150})
    r = run('direct', slow_strobe); c = dict((n, (s, v)) for n, s, v in r['checks'])
    T.append(('150 ms toggle attack: flash rate stays < 3 Hz', *c['flash rate < 3 Hz (photosensitive safety)']))
    def sensor_dead(d, rt, t):
        if t >= 10: d.sensor.env = lambda _t: 0  # I2C read fails → driver reports floor (1 lx)
    r = run('direct', sensor_dead); mx = max(max(max(p) for p in f['px']) for f in r['frames'][int(11 / DT):]) / 255
    T.append(('sensor dead: falls back to night-safe brightness', 'PASS' if mx <= M['safety']['night_max_brightness'] + .02 else 'FAIL', f'max {mx:.2f}'))
    return T

def export_layer_c(frames):
    keys = [2.5, 6.5, 14, 22, 28.5, 33, 41, 53]
    out = [dict(t=k, leds=frames[int(k / DT)]['px'], lux=frames[int(k / DT)]['lux']) for k in keys]
    json.dump(out, open(f'{OUT}/mood_lamp_trace_keys.json', 'w')); return out

if __name__ == '__main__':
    os.makedirs(OUT, exist_ok=True)
    runs = [run(p) for p in ('direct', 'muse', 'mcp', 'pogtown')]
    same = len({r['hash'] for r in runs}) == 1
    A, reg = layer_a(); B = layer_b(); keys = export_layer_c(runs[0]['frames'])
    rep = dict(contract='oddhobb.device.v1', device=M['device_type'],
               replay=[dict(path=r['path'], frame_hash=r['hash'], calls_ok=sum(x['ok'] for x in r['results']), calls=len(r['results']), checks=r['checks']) for r in runs],
               identical=same, layer_a=A, layer_b=B, muse_register=reg, commands_v2=to_commands_v2(M))
    json.dump(rep, open(f'{OUT}/replay_report.json', 'w'), indent=1)
    for r in rep['replay']: print(f"{r['path']:8} hash {r['frame_hash']}  calls {r['calls_ok']}/{r['calls']}  " + ' '.join(c[1] for c in r['checks']))
    print('IDENTICAL across adapters:', same)
    for n, s, v in A + B: print(f'{s:4} {n}  {v[:80]}')
