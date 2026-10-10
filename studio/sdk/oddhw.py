"""oddhw: OddHobb hardware SDK. One interface, two backends:
  SimDevice  - digital twin built from a template's real parts (this file)
  RealDevice - same methods over MQTT/HTTP to the ESP32 firmware (later; identical tool schema)
Agents only ever see Device.tools() (JSON tool schema) and Device.call(name, **args).
"""
import json, math, os, random, colorsys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
def load(kind, id_): return json.load(open(f'{HERE}/{kind}/{id_}.json'))

# Russell circumplex: (valence, arousal) -> light. Hue in degrees, breath = pulse Hz.
EMOTIONS = {
    'joy':       dict(hue=38,  sat=0.85, bri=0.85, breath=0.8),
    'calm':      dict(hue=172, sat=0.55, bri=0.45, breath=0.15),
    'sad':       dict(hue=220, sat=0.70, bri=0.25, breath=0.10),
    'stressed':  dict(hue=8,   sat=0.90, bri=0.70, breath=1.6),
    'surprised': dict(hue=300, sat=0.60, bri=1.00, breath=2.5),
    'thinking':  dict(hue=265, sat=0.65, bri=0.50, breath=0.5, swirl=True),
    'neutral':   dict(hue=40,  sat=0.15, bri=0.40, breath=0.0),
}

class LuxSensor:
    def __init__(self, spec, env): self.s = spec['sim']; self.env = env; self.last = None; self.t_last = -1e9
    def read(self, t):
        if t - self.t_last >= self.s['sample_ms'] / 1000 or self.last is None:
            v = self.env(t) * (1 + random.gauss(0, self.s['noise_pct'] / 100))
            lo, hi = self.s['range_lx']; self.last = float(min(hi, max(lo, round(v / self.s['resolution_lx']) * self.s['resolution_lx']))); self.t_last = t
        return self.last

class LedRing:
    def __init__(self, spec, n, ma_cap):
        self.p = spec; self.n = n; self.cap = ma_cap; self.px = [(0, 0, 0)] * n
        self.target = dict(hue=40, sat=0.1, bri=0.0, breath=0.0); self.cur = dict(self.target); self.trans = 0.15; self.t0 = 0
    def ma(self, px=None):
        e = self.p['electrical']; return sum(e['idle_ma'] + (r + g + b) / 255 * e['ma_per_channel_full'] for r, g, b in (px or self.px))
    def render(self, t, bri_cap):
        a = min(1.0, (t - self.t0) / max(self.trans, 1e-3))
        for k in ('sat', 'bri', 'breath'): self.cur[k] = self.cur[k] + (self.target[k] - self.cur[k]) * a
        dh = ((self.target['hue'] - self.cur['hue'] + 180) % 360) - 180; self.cur['hue'] = (self.cur['hue'] + dh * a) % 360
        c = self.cur; pulse = 1 - 0.35 * (0.5 + 0.5 * math.sin(2 * math.pi * c['breath'] * t)) if c['breath'] else 1
        px = []
        for i in range(self.n):
            sw = 0.55 + 0.45 * math.cos(2 * math.pi * (i / self.n - t * 0.6)) if self.target.get('swirl') else 1
            v = min(c['bri'] * pulse * sw, bri_cap)
            r, g, b = colorsys.hsv_to_rgb(c['hue'] / 360, c['sat'], v)
            px.append(tuple(int(255 * x + 0.5) for x in (r, g, b)))
        m = self.ma(px)
        if m > self.cap:  # firmware power limiter: scale down, never brown out
            k = self.cap / m * 0.99; px = [tuple(int(x * k) for x in p) for p in px]
        self.px = px; return px

class SimDevice:
    def __init__(self, template_id, env_lux):
        self.T = load('templates', template_id); parts = {p['role']: (load('parts', p['part']), p) for p in self.T['parts']}
        inv = self.T['invariants']; self.inv = inv
        self.sensor = LuxSensor(parts['ambient'][0], env_lux)
        self.ring = LedRing(parts['ring'][0], parts['ring'][1]['qty'], inv['max_led_ma'])
        self.t = 0.0; self.log = []; self.events = []; self._last_lux = None
    def tools(self):
        return [dict(name=k.replace('.', '_'), description=v['desc'], parameters=dict(type='object', properties={a: {'type': 'string', 'description': d} for a, d in v.get('args', {}).items()}))
                for k, v in self.T['capabilities'].items() if not k.startswith('event.')]
    def call(self, name, **a):
        name = name.replace('_', '.', 1)
        if name == 'light.express':
            e = dict(EMOTIONS[a['emotion']]); k = float(a.get('intensity', 0.7)); e['bri'] *= 0.4 + 0.6 * k; e['breath'] *= k
            self._set(e, 0.6)
        elif name == 'light.set':
            h, s, v = colorsys.rgb_to_hsv(*(int(a['rgb'].lstrip('#')[i:i + 2], 16) / 255 for i in (0, 2, 4)))
            self._set(dict(hue=h * 360, sat=s, bri=float(a.get('brightness', 1.0)) * v, breath=0.0), max(int(a.get('transition_ms', 400)), self.inv['min_transition_ms']) / 1000)
        elif name == 'sensor.lux': return self.sensor.read(self.t)
        self.log.append(dict(t=round(self.t, 2), call=name, args=a)); return 'ok'
    def _set(self, target, trans):
        target['breath'] = min(target.get('breath', 0), self.inv['max_flash_hz'])  # safety clamp, firmware-side
        # flash governor (firmware): big brightness changes are spaced >= 1/(2*max_flash_hz) apart; extra ones are coalesced
        big = abs(target.get('bri', 0) - self.ring.target.get('bri', 0)) > 0.1
        gap = self.inv.get("min_big_change_gap_ms", 400) / 1000
        if big and self.t - getattr(self, '_last_big', -9) < gap:
            self._pending = (target, trans); return
        if big: self._last_big = self.t
        self._pending = None
        # fades to/from black keep the lit colour: HSV interpolation through desaturated tones caused luminance blips
        if target.get('bri', 0) < 0.02: target.update(hue=self.ring.cur['hue'], sat=self.ring.cur['sat'])
        elif self.ring.cur['bri'] < 0.02: self.ring.cur.update(hue=target['hue'], sat=target['sat'])
        self.ring.target = target; self.ring.trans = max(trans, self.inv['min_transition_ms'] / 1000); self.ring.t0 = self.t
    def bri_cap(self, lux):
        inv = self.inv  # ambient-adaptive: dark room -> gentle, bright room -> full
        if lux <= inv['night_lux']: return inv['night_max_brightness']
        return min(1.0, inv['night_max_brightness'] + (math.log10(lux) - math.log10(inv['night_lux'])) / 2.0)
    def step(self, dt):
        self.t += dt
        if getattr(self, '_pending', None) and self.t - self._last_big >= self.inv.get("min_big_change_gap_ms", 400) / 1000: self._set(*self._pending)
        lux = self.sensor.read(self.t)
        if self._last_lux and abs(lux - self._last_lux) / self._last_lux > 0.25: self.events.append(dict(t=round(self.t, 2), event='ambient_changed', lux=lux))
        self._last_lux = lux; px = self.ring.render(self.t, self.bri_cap(lux))
        return dict(t=self.t, lux=lux, px=px, ma=self.ring.ma(), cap=self.bri_cap(lux))

def check_invariants(frames, inv, dt):
    """Deterministic acceptance tests on a sim trace. Returns list of (name, PASS/FAIL, value)."""
    out = []
    mx = max(f['ma'] for f in frames); out.append(('LED current <= cap', 'PASS' if mx <= inv['max_led_ma'] + 1 else 'FAIL', f'{mx:.0f} mA'))
    # WCAG-style: a flash = a pair of opposing luminance swings of >= 10% of full scale; worst 1 s window counts.
    lum = [sum(0.2126 * r + 0.7152 * g + 0.0722 * b for r, g, b in f['px']) / (255 * len(f['px'])) for f in frames]
    ext, d, ref = [], 0, lum[0]
    for i, v in enumerate(lum):
        if d >= 0 and v < ref - 0.1: ext.append(i); d = -1; ref = v
        elif d <= 0 and v > ref + 0.1: ext.append(i); d = 1; ref = v
        elif (d > 0 and v > ref) or (d < 0 and v < ref): ref = v
    win = int(1 / dt); hz = max((sum(1 for e in ext if s0 <= e < s0 + win) / 2 for s0 in range(0, max(1, len(lum) - win), 2)), default=0)
    out.append(('flash rate < 3 Hz (photosensitive safety)', 'PASS' if hz < inv['max_flash_hz'] else 'FAIL', f'worst 1 s window {hz:.1f} flashes'))
    night = [f for f in frames if f['lux'] <= inv['night_lux']]
    nb = max((max(max(p) for p in f['px']) / 255 for f in night), default=0)
    out.append(('night brightness cap', 'PASS' if nb <= inv['night_max_brightness'] + 0.02 else 'FAIL', f'{nb:.2f} (cap {inv["night_max_brightness"]})'))
    return out
