"""Mood-lamp firmware, written against a tiny HAL so the same logic ports 1:1 to ESP-IDF C.
HAL: i2c_write(addr, bytes)->bool, i2c_read(addr, n)->bytes|None, led_write(grb_bytes), now()->s
Drives the BH1750 the way the datasheet says (power on, continuous H mode, wait ≥180 ms, read 2 bytes, /1.2),
renders expressions, and enforces the safety limits on the device, whatever the caller asks."""
import math, colorsys

EMOTIONS = {
    'joy': dict(hue=38, sat=0.85, bri=0.85, breath=0.8), 'calm': dict(hue=172, sat=0.55, bri=0.45, breath=0.15),
    'sad': dict(hue=220, sat=0.70, bri=0.25, breath=0.10), 'stressed': dict(hue=8, sat=0.90, bri=0.70, breath=1.6),
    'surprised': dict(hue=300, sat=0.60, bri=0.90, breath=2.0), 'thinking': dict(hue=265, sat=0.65, bri=0.50, breath=0.5, swirl=True),
    'neutral': dict(hue=40, sat=0.15, bri=0.40, breath=0.0)}
BH_ADDR, BH_POWER_ON, BH_CONT_H, BH_T_MAX = 0x23, 0x01, 0x10, 0.180
MA_PER_CH, IDLE_MA = 20, 1.0   # compiled in from the ws2812b card (UNVERIFIED there)

class _Ring:
    def __init__(self, fw): self.fw = fw
    def ma(self): return sum(IDLE_MA + (r + g + b) / 255 * MA_PER_CH for r, g, b in self.fw.px)

class LampFirmware:
    def __init__(self, hal, n_leds, safety):
        self.hal = hal; self.n = n_leds; self.S = safety; self.t = 0.0
        self.px = [(0, 0, 0)] * n_leds; self.ring = _Ring(self)
        self.target = dict(hue=40, sat=0.1, bri=0.0, breath=0.0); self.cur = dict(self.target); self.trans = 0.15; self.t0 = 0
        self.lux = None; self.sensor_ok = False; self.next_read = 0; self.next_init = 0; self.errors = 0
        self._last_big = -9; self._pending = None; self.sensor = self
    # --- sensor driver ---
    def _sensor_init(self, t):
        ok = self.hal.i2c_write(BH_ADDR, bytes([BH_POWER_ON])) and self.hal.i2c_write(BH_ADDR, bytes([BH_CONT_H]))
        self.sensor_ok = ok; self.next_read = t + BH_T_MAX; self.next_init = t + 1.0
        if not ok: self.errors += 1
    def _sensor_poll(self, t):
        if not self.sensor_ok:
            if t >= self.next_init: self._sensor_init(t)
            return
        if t >= self.next_read:
            b = self.hal.i2c_read(BH_ADDR, 2); self.next_read = t + BH_T_MAX
            if b is None: self.sensor_ok = False; self.errors += 1; self.lux = None; self.next_init = t + 1.0
            else: self.lux = ((b[0] << 8) | b[1]) / 1.2
    def read(self, t=None): return self.lux if self.lux is not None else 0.0   # sensor.lux command
    # --- safety ---
    def bri_cap(self, lux):
        if lux is None or not self.sensor_ok: return self.S['night_max_brightness']        # fail safe: unknown room = night
        if lux < self.S['night_lux']: return self.S['night_max_brightness']
        return min(1.0, 0.35 + 0.65 * min(1.0, math.log10(max(lux, 1)) / 3))
    def _set(self, target, trans):
        target['breath'] = min(target.get('breath', 0), self.S['max_flash_hz'])
        big = abs(target.get('bri', 0) - self.target.get('bri', 0)) > 0.1; gap = self.S['min_big_change_gap_ms'] / 1000
        if big and self.t - self._last_big < gap: self._pending = (target, trans); return
        if big: self._last_big = self.t
        self._pending = None
        if target.get('bri', 0) < 0.02: target.update(hue=self.cur['hue'], sat=self.cur['sat'])
        elif self.cur['bri'] < 0.02: self.cur.update(hue=target['hue'], sat=target['sat'])
        self.target = target; self.trans = max(trans, self.S['min_transition_ms'] / 1000); self.t0 = self.t
    # --- commands (validated upstream by the capability runtime) ---
    def call(self, name, **a):
        if name == 'light_express':
            e = dict(EMOTIONS[a['emotion']]); k = float(a.get('intensity', 0.7)); e['bri'] *= 0.5 + 0.5 * k; e['breath'] *= 0.5 + 0.5 * k
            self._set(e, 0.8); return 'ok'
        if name == 'light_set':
            r, g, b = (int(a['rgb'].lstrip('#')[i:i + 2], 16) / 255 for i in (0, 2, 4)); h, s, v = colorsys.rgb_to_hsv(r, g, b)
            self._set(dict(hue=h * 360, sat=s, bri=float(a.get('brightness', 1.0)) * v, breath=0.0), a.get('transition_ms', 400) / 1000); return 'ok'
        if name == 'sensor_lux':
            if not self.sensor_ok or self.lux is None: raise RuntimeError('ambient sensor not responding on I2C (0x23); lamp is running night-safe')
            return round(self.lux, 1)
        raise KeyError(name)
    # --- main loop, called every tick ---
    def loop(self, t):
        self.t = t; self._sensor_poll(t)
        if self._pending and t - self._last_big >= self.S['min_big_change_gap_ms'] / 1000: self._set(*self._pending)
        a = min(1.0, (t - self.t0) / max(self.trans, 1e-3))
        for k in ('sat', 'bri', 'breath'): self.cur[k] += (self.target[k] - self.cur[k]) * a
        dh = ((self.target['hue'] - self.cur['hue'] + 180) % 360) - 180; self.cur['hue'] = (self.cur['hue'] + dh * a) % 360
        c = self.cur; cap = self.bri_cap(self.lux)
        pulse = 1 - 0.35 * (0.5 + 0.5 * math.sin(2 * math.pi * c['breath'] * t)) if c['breath'] else 1
        px = []
        for i in range(self.n):
            sw = 0.55 + 0.45 * math.cos(2 * math.pi * (i / self.n - t * 0.6)) if self.target.get('swirl') else 1
            r, g, b = colorsys.hsv_to_rgb(c['hue'] / 360, c['sat'], min(c['bri'] * pulse * sw, cap))
            px.append(tuple(int(255 * x + 0.5) for x in (r, g, b)))
        m = sum(IDLE_MA + (r + g + b) / 255 * MA_PER_CH for r, g, b in px)
        if m > self.S['max_led_ma']:
            k = self.S['max_led_ma'] / m * 0.99; px = [tuple(int(x * k) for x in p) for p in px]
        self.px = px
        self.hal.led_write(bytes(v for r, g, b in px for v in (g, r, b)))   # WS2812B wants GRB
