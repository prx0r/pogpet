#!/usr/bin/env python3
"""Trial a device template with an agent before ordering anything.
  python3 studio/simulate.py mood_lamp
The agent only gets the device's tool schema (Device.tools()) and calls tools, exactly as it would on the real lamp.
Swap ScriptedAgent for an LLM agent later; the device side doesn't change.
Outputs: out/<tpl>_sim.png (timeline), out/<tpl>_sim.gif (ring), out/<tpl>_sim.json (trace + invariant checks)."""
import sys, os, json, math, random
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sdk.oddhw import SimDevice, check_invariants
from PIL import Image, ImageDraw, ImageFont
H = os.path.dirname(os.path.abspath(__file__)); random.seed(7)

# Room: bright afternoon, cloud, lamp-lit evening, lights off at 44 s.
def room_lux(t):
    if t < 14: return 420
    if t < 24: return 420 - (t - 14) * 30
    if t < 44: return 90
    return 4

# What the agent goes through in the conversation (would come from the agent's own state in production).
CHAT = [(0, 'user says hi', 'neutral'), (4, 'user shares good news', 'joy'), (12, 'agent working on a hard task', 'thinking'),
        (20, 'build fails three times', 'stressed'), (27, 'fix lands', 'surprised'), (31, 'done, winding down', 'calm'),
        (38, 'user mentions their dog died', 'sad'), (50, 'goodnight', 'calm')]

class ScriptedAgent:
    """Stand-in for an LLM: decides tool calls from its feelings + device events. Uses only the public tools."""
    def __init__(self, dev): self.dev = dev; self.i = 0; self.tools = [t['name'] for t in dev.tools()]; self.mood = 'neutral'
    def tick(self, t):
        acts = []
        while self.i < len(CHAT) and CHAT[self.i][0] <= t:
            _, why, emo = CHAT[self.i]; self.i += 1; self.mood = emo
            inten = 0.9 if emo in ('joy', 'surprised') else 0.6
            self.dev.call('light_express', emotion=emo, intensity=inten); acts.append(f'{why} -> express({emo}, {inten})')
        for ev in [e for e in self.dev.events if abs(e['t'] - t) < 1e-6]:
            if ev['lux'] < 10 and self.mood in ('joy', 'stressed', 'surprised'):
                self.dev.call('light_express', emotion='calm', intensity=0.4); acts.append(f'room went dark ({ev["lux"]:.0f} lx) -> soften to calm')
        return acts

def main(tid='mood_lamp', dur=56.0, dt=0.05):
    dev = SimDevice('mood_lamp' if tid == 'mood_lamp' else tid, room_lux); ag = ScriptedAgent(dev)
    frames, actions = [], []
    for k in range(int(dur / dt)):
        f = dev.step(dt); a = ag.tick(round(dev.t, 2)); frames.append(f)
        actions += [dict(t=round(dev.t, 1), action=x) for x in a]
    checks = check_invariants(frames, dev.inv, dt)
    os.makedirs(f'{H}/out', exist_ok=True)
    json.dump(dict(template=dev.T['id'], tools=dev.tools(), actions=actions, events=dev.events[:20], checks=checks, calls=dev.log),
              open(f'{H}/out/{tid}_sim.json', 'w'), indent=1)
    draw_timeline(frames, actions, checks, dt, f'{H}/out/{tid}_sim.png', dev.inv)
    draw_gif(frames, actions, dt, f'{H}/out/{tid}_sim.gif')
    for c in checks: print(f'{c[1]:4} {c[0]}: {c[2]}')
    for a in actions: print(f'{a["t"]:5.1f}s  {a["action"]}')

def font(sz):
    for p in ['/opt/deckbuild/fonts/Inter-Medium.ttf', '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf']:
        if os.path.exists(p): return ImageFont.truetype(p, sz)
    return ImageFont.load_default()

def ring(d, cx, cy, R, px, r=None):
    n = len(px); r = r or max(4, int(R * 0.28))
    for i, c in enumerate(px):
        a = 2 * math.pi * i / n - math.pi / 2; x, y = cx + R * math.cos(a), cy + R * math.sin(a)
        glow = tuple(min(255, int(v * 0.35 + 18)) for v in c)
        d.ellipse([x - r * 1.6, y - r * 1.6, x + r * 1.6, y + r * 1.6], fill=glow); d.ellipse([x - r, y - r, x + r, y + r], fill=tuple(max(30, v) if max(c) > 8 else 30 for v in c))

def draw_timeline(frames, actions, checks, dt, path, inv):
    W, Hh = 2000, 1150; im = Image.new('RGB', (W, Hh), (18, 18, 22)); d = ImageDraw.Draw(im); F, f2, f3 = font(34), font(22), font(19)
    d.text((50, 30), 'Agent mood lamp: 56 s simulated trial (12x WS2812B, BH1750, ESP32-C3)', fill=(240, 240, 240), font=F)
    n = len(frames); x0, x1 = 80, W - 60; X = lambda i: x0 + (x1 - x0) * i / (n - 1)
    # ring strip: one ring per second
    for s in range(0, 56, 2):
        i = int(s / dt); ring(d, X(i) + 30, 190, 24, frames[i]['px'], 6); d.text((X(i) + 18, 232), f'{s}s', fill=(150, 150, 160), font=f3)
    # colour band (mean pixel)
    for i in range(0, n, 2):
        c = tuple(int(sum(p[k] for p in frames[i]['px']) / len(frames[i]['px'])) for k in range(3)); d.line([X(i), 280, X(i), 360], fill=c, width=3)
    d.text((x0, 365), 'ring colour over time (mean pixel)', fill=(150, 150, 160), font=f3)
    # lux (log) + brightness cap
    top, bot = 420, 620; d.text((x0, 395), 'ambient lux (log) and the brightness cap it allows', fill=(200, 200, 210), font=f2)
    ly = lambda v: bot - (math.log10(max(v, 1)) / 3) * (bot - top)
    d.line([(X(i), ly(frames[i]['lux'])) for i in range(0, n, 3)], fill=(255, 205, 80), width=3)
    d.line([(X(i), bot - frames[i]['cap'] * (bot - top)) for i in range(0, n, 3)], fill=(120, 200, 255), width=3)
    # current
    top2, bot2 = 680, 840; d.text((x0, 650), f'LED current (mA), firmware cap {inv["max_led_ma"]} mA', fill=(200, 200, 210), font=f2)
    d.line([x0, bot2 - inv['max_led_ma'] / 400 * (bot2 - top2), x1, bot2 - inv['max_led_ma'] / 400 * (bot2 - top2)], fill=(200, 60, 60), width=1)
    d.line([(X(i), bot2 - frames[i]['ma'] / 400 * (bot2 - top2)) for i in range(0, n, 2)], fill=(140, 255, 160), width=3)
    # actions
    for a in actions:
        i = min(n - 1, int(a['t'] / dt)); d.line([X(i), 270, X(i), 845], fill=(70, 70, 85), width=1)
    y = 870; d.text((x0, y), 'agent tool calls', fill=(200, 200, 210), font=f2)
    for k, a in enumerate(actions):
        d.text((x0 + (k % 2) * 930, y + 32 + (k // 2) * 28), f'{a["t"]:>4.1f}s  {a["action"]}', fill=(220, 220, 225), font=f3)
    yy = y + 32 + ((len(actions) + 1) // 2) * 28 + 10
    for k, c in enumerate(checks):
        d.text((x0 + k * 620, yy), f'{c[1]} {c[0]} ({c[2]})', fill=(120, 230, 140) if c[1] == 'PASS' else (255, 90, 90), font=f3)
    im.save(path)

def draw_gif(frames, actions, dt, path):
    out = []; F = font(20)
    for i in range(0, len(frames), 4):
        f = frames[i]; im = Image.new('RGB', (420, 460), (14, 14, 18)); d = ImageDraw.Draw(im)
        amb = int(min(255, 20 + math.log10(max(f['lux'], 1)) * 60)); d.rectangle([0, 0, 420, 420], fill=(amb // 3, amb // 3, amb // 3 + 4))
        ring(d, 210, 210, 120, f['px'], 22)
        last = [a for a in actions if a['t'] <= f['t']]; lab = last[-1]['action'].split('->')[-1].strip() if last else ''
        d.text((14, 428), f'{f["t"]:4.1f}s  {f["lux"]:>4.0f} lx  {lab}'[:42], fill=(220, 220, 220), font=F)
        out.append(im)
    out[0].save(path, save_all=True, append_images=out[1:], duration=int(dt * 4 * 1000), loop=0, optimize=True)

if __name__ == '__main__': main(*(sys.argv[1:2] or ['mood_lamp']))
