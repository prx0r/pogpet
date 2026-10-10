"""Card-driven peripheral models. No part-specific code: behaviour comes from the part card.
  I2CCommandDevice  — opcode-table devices (BH1750, many sensors): states, opcodes, timed conversions, faults
  LedChain          — addressable LED chains (WS2812B…): decodes the GRB byte stream, current per channel
  Rail              — supply rail: sums load currents, flags overload/brownout
  I2CBus            — routes master transactions to devices by address, logs every transaction"""
import json, os, random
H = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
def card(id_): return json.load(open(f'{H}/cards/{id_}.card.json'))
def _i(x): return int(x, 16) if isinstance(x, str) else x

class I2CCommandDevice:
    def __init__(self, c, strap, env, rng):
        self.c = c; self.addr = _i(c['interface']['addresses']['ADDR_' + strap.get('ADDR', 'L')])
        self.env = env; self.rng = rng; self.state = c['initial_state']; self.reg = {k: v['reset'] for k, v in c['registers'].items()}
        self.mode = None; self.t_start = None; self.t_conv = None; self.fault = None; self.gain = c['measurement']['accuracy_ratio']['typ']
        self.unit_ms = None
    def _conv_s(self):
        m = self.c['modes'][self.mode]; return m['t_typ_ms'] * self.reg['mtreg'] / 69 / 1000
    def write(self, t, data):
        if self.fault == 'nack': return False
        op = data[0]
        for o in self.c['opcodes']:
            if op & _i(o['mask']) == _i(o['value']):
                if self.state in o.get('rejected_in', []): return True  # ACKed but ignored, per datasheet
                eff = o.get('effect', '')
                if eff == 'data=0': self.reg['data'] = 0
                elif eff.startswith('mtreg[7:5]'): self.reg['mtreg'] = (self.reg['mtreg'] & 0x1F) | ((op & 7) << 5)
                elif eff.startswith('mtreg[4:0]'): self.reg['mtreg'] = (self.reg['mtreg'] & 0xE0) | (op & 0x1F)
                if 'goto' in o:
                    self.state = o['goto']
                    if 'mode' in o: self.mode = o['mode']; self.t_start = t
                return True
        return False  # undefined opcode: NACK (datasheet: don't send)
    def tick(self, t):
        if self.state.startswith('measuring') and self.fault != 'stuck' and t - self.t_start >= self._conv_s():
            m = self.c['modes'][self.mode]; lpc = eval(m['lx_per_count'], {}, {'mtreg': self.reg['mtreg']})
            lux = self.env(t); counts = lux * self.gain / (1.2 * lpc) * (1 + self.rng.gauss(0, 0.01))  # sensor reports lux*S/A
            counts += self.rng.uniform(0, self.c['measurement']['dark_counts_max']) if lux < 1 else 0
            self.reg['data'] = max(0, min(65535, int(counts)))
            self.t_start = t
            if self.state == 'measuring_once': self.state = 'power_down'
    def read(self, t, n):
        if self.fault == 'nack': return None
        v = self.reg['data']; return bytes([(v >> 8) & 0xFF, v & 0xFF])[:n]
    def current_ma(self):
        p = self.c['power']; return (p['i_powerdown_ua']['typ'] if self.state == 'power_down' else p['i_active_ua']['typ']) / 1000

class LedChain:
    def __init__(self, c, n):
        self.c = c; self.n = n; self.px = [(0, 0, 0)] * n; self.frames = 0
    def write(self, stream: bytes):
        if len(stream) < 3 * self.n: raise ValueError(f'short frame: {len(stream)} bytes for {self.n} LEDs')
        if self.c['interface']['byte_order'] == 'GRB':
            self.px = [(stream[i + 1], stream[i], stream[i + 2]) for i in range(0, 3 * self.n, 3)]
        self.frames += 1
    def current_ma(self):
        p = self.c['power']; return sum(p['idle_ma'] + (r + g + b) / 255 * p['ma_per_channel_full'] for r, g, b in self.px)

class Rail:
    def __init__(self, name, spec): self.name = name; self.limit = spec['limit_ma']; self.loads = []; self.peak = 0; self.over = 0
    def sample(self, dt):
        ma = sum(l() for l in self.loads); self.peak = max(self.peak, ma)
        if ma > self.limit: self.over += dt
        return ma

class I2CBus:
    def __init__(self): self.dev = {}; self.log = []
    def attach(self, d): self.dev[d.addr] = d
    def write(self, t, addr, data):
        d = self.dev.get(addr); ok = bool(d and d.write(t, data)); self.log.append((round(t, 3), 'W', hex(addr), data.hex(), 'ACK' if ok else 'NACK')); return ok
    def read(self, t, addr, n):
        d = self.dev.get(addr); r = d.read(t, n) if d else None; self.log.append((round(t, 3), 'R', hex(addr), r.hex() if r else '', 'ACK' if r else 'NACK')); return r
