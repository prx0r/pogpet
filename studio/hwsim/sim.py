"""Board-level simulator: part cards + board file + firmware → a virtual device an agent can drive.
Time is simulated: device commands land at the current sim time; sim.advance(s) lets time pass.
  b = Board.load('mood_lamp'); b.set_ambient(400); b.invoke('light.express', {'emotion': 'joy'}); b.advance(5); b.checks()"""
import json, os, sys, random, importlib, io, base64
H = os.path.dirname(os.path.abspath(__file__)); STUDIO = os.path.dirname(H); sys.path.insert(0, STUDIO)
from hwsim.models.generic import card, I2CCommandDevice, LedChain, Rail, I2CBus
from sdk.runtime import Runtime
from sdk.oddhw import check_invariants

TICK, FRAME = 0.01, 0.05

class HAL:
    def __init__(self, b): self.b = b
    def i2c_write(self, addr, data): return self.b.i2c.write(self.b.t, addr, data)
    def i2c_read(self, addr, n): return self.b.i2c.read(self.b.t, addr, n)
    def led_write(self, grb): self.b.leds.write(grb)
    def now(self): return self.b.t

class Board:
    @classmethod
    def load(cls, name, seed=7):
        f = f'{H}/designs/{name}/board.json' if os.path.exists(f'{H}/designs/{name}/board.json') else f'{H}/board.{name}.json'
        return cls(json.load(open(f)), seed)
    def __init__(self, spec, seed=7):
        self.spec = spec; self.rng = random.Random(seed); self.t = 0.0; self.amb = [(0.0, 300.0)]
        self.manifest = json.load(open(os.path.normpath(os.path.join(H, spec["device_manifest"]))))
        self.i2c = I2CBus(); self.rails = {k: Rail(k, v) for k, v in spec['rails'].items()}
        self.cards = {}; self.parts = {}
        for p in spec['parts']:
            c = card(p['card']); self.cards[p['card']] = c
            if c['model'] == 'i2c_command_device':
                d = I2CCommandDevice(c, p.get('strap', {}), self.ambient, self.rng); self.i2c.attach(d); self.parts[p['ref']] = d
                self.rails[p['rail']].loads.append(d.current_ma)
            elif c['model'] == 'addressable_led_chain':
                self.leds = LedChain(c, p['qty']); self.parts[p['ref']] = self.leds; self.rails[p['rail']].loads.append(self.leds.current_ma)
            elif c['model'] == 'mcu_host':
                self.rails[p['rail']].loads.append(lambda c=c: c['power']['ma_avg_wifi'])
        for name, spec_r in spec['rails'].items():   # an LDO's input current = its output load (linear regulator)
            if spec_r.get('parent'): self.rails[spec_r['parent']].loads.append(lambda r=self.rails[name]: sum(l() for l in r.loads))
        fw = importlib.import_module('hwsim.firmware.lamp_fw')
        self.fw = fw.LampFirmware(HAL(self), self.leds.n, self.manifest['safety'])
        self.rt = Runtime(self.manifest, self.fw); self.frames = []; self.calls = []; self._next_frame = 0
    # environment
    def ambient(self, t):
        pts = [p for p in self.amb if p[0] <= t]; t0, v0 = pts[-1]
        nxt = [p for p in self.amb if p[0] > t]
        if not nxt: return v0
        t1, v1 = nxt[0]; return v0 + (v1 - v0) * (t - t0) / (t1 - t0)
    def set_ambient(self, lux, ramp_s=0.0):
        now = self.ambient(self.t); self.amb = [p for p in self.amb if p[0] <= self.t] + [(self.t, now), (self.t + max(ramp_s, 1e-6), float(lux))]
    def inject_fault(self, ref, fault):
        d = self.parts[ref]; d.fault = None if fault in ('none', 'clear') else fault; return f'{ref}: fault={d.fault}'
    # time
    def advance(self, seconds):
        end = self.t + seconds
        while self.t < end - 1e-9:
            self.t = round(self.t + TICK, 4)
            for d in self.parts.values():
                if hasattr(d, 'tick'): d.tick(self.t)
            self.fw.loop(self.t)
            ma5 = self.rails['5V'].sample(TICK); self.rails['3V3'].sample(TICK)
            if self.t >= self._next_frame - 1e-9:
                self.frames.append(dict(t=self.t, lux=self.ambient(self.t), lux_fw=self.fw.lux, px=list(self.leds.px), ma=self.fw.ring.ma(), rail5_ma=ma5))
                self._next_frame = self.t + FRAME
        return self.state()
    # agent-facing
    def invoke(self, command, params=None, caller='mcp'):
        r = self.rt.invoke(command, params or {}, caller); self.calls.append(dict(t=self.t, command=command, params=params, ok=r['ok'])); return r
    def state(self):
        f = self.frames[-1] if self.frames else None
        return dict(t=round(self.t, 2), ambient_lux=round(self.ambient(self.t), 1), firmware_lux=None if self.fw.lux is None else round(self.fw.lux, 1),
                    sensor_ok=self.fw.sensor_ok, sensor_errors=self.fw.errors, led_ma=round(self.fw.ring.ma(), 1),
                    rail_5v_peak_ma=round(self.rails['5V'].peak, 1), rail_5v_limit_ma=self.rails['5V'].limit,
                    mean_rgb=[round(sum(p[i] for p in f['px']) / len(f['px'])) for i in range(3)] if f else None,
                    faults={k: d.fault for k, d in self.parts.items() if getattr(d, 'fault', None)})
    def checks(self):
        inv = dict(self.manifest['safety'])
        out = [c for c in check_invariants(self.frames, inv, FRAME) if c[0] != 'night brightness cap'] if self.frames else []
        # night cap applies once the room has been dark longer than the sensor can know it (2 x BH1750 max conversion + poll)
        grace = 2 * 0.180 + 0.05; dark_since = None; nb = 0
        for f in self.frames:
            if f['lux'] <= inv['night_lux']:
                dark_since = f['t'] if dark_since is None else dark_since
                if f['t'] - dark_since >= grace: nb = max(nb, max(max(p) for p in f['px']) / 255)
            else: dark_since = None
        out.append(('night brightness cap (after sensor latency %.2f s)' % grace, 'PASS' if nb <= inv['night_max_brightness'] + 0.02 else 'FAIL', f'{nb:.2f} (cap {inv["night_max_brightness"]})'))
        r = self.rails['5V']; out.append(('5V rail within supply limit', 'PASS' if r.over == 0 else 'FAIL', f'peak {r.peak:.0f} mA of {r.limit} mA'))
        nacks = sum(1 for l in self.i2c.log if l[4] == 'NACK'); out.append(('I2C bus clean', 'PASS' if nacks == 0 else 'WARN', f'{nacks} NACKs of {len(self.i2c.log)} transactions'))
        drafts = [c['id'] for c in self.cards.values() if c['status'] != 'VERIFIED']
        out.append(('all part cards human-verified', 'PASS' if not drafts else 'WARN', 'unverified: ' + ', '.join(drafts) if drafts else 'all verified'))
        return out
    def snapshot_png(self, seconds=6.0):
        from PIL import Image, ImageDraw
        from simulate import ring, font
        fr = [f for f in self.frames if f['t'] >= self.t - seconds] or self.frames[-1:]
        im = Image.new('RGB', (900, 420), (16, 16, 20)); d = ImageDraw.Draw(im)
        if fr: ring(d, 200, 200, 120, fr[-1]['px'], 22)
        s = self.state(); F = font(22); y = 40
        for k in ('t', 'ambient_lux', 'firmware_lux', 'sensor_ok', 'led_ma', 'rail_5v_peak_ma', 'faults'):
            d.text((420, y), f'{k}: {s[k]}', fill=(220, 220, 225), font=F); y += 34
        if fr:
            n = len(fr); x0 = 420
            for i, f in enumerate(fr):
                c = tuple(int(sum(p[j] for p in f['px']) / len(f['px'])) for j in range(3)); x = x0 + 440 * i / max(n, 1)
                d.rectangle([x, 330, x + 440 / max(n, 1) + 1, 390], fill=c)
            d.text((x0, 300), f'last {seconds:.0f} s, mean colour', fill=(150, 150, 160), font=font(18))
        bio = io.BytesIO(); im.save(bio, 'PNG'); return bio.getvalue()
