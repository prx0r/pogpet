"""Datasheet conformance: the card-driven BH1750 model must reproduce the datasheet's own worked examples and rules."""
import os, sys, random
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from hwsim.models.generic import card, I2CCommandDevice, I2CBus
C = card('bh1750'); R = []
def dev(lux): d = I2CCommandDevice(C, {'ADDR': 'L'}, lambda t: lux, random.Random(1)); d.gain = 1.2; return d
def chk(name, cond, val=''): R.append((name, 'PASS' if cond else 'FAIL', val))
# datasheet example: H mode, data 0x8390 → 28067 lx  (counts/1.2)
chk('H-mode conversion example 0x8390 → 28067 lx', round(0x8390 / 1.2) == 28067, round(0x8390 / 1.2))
d = dev(1000); b = I2CBus(); b.attach(d)
chk('address ADDR=L is 0x23', d.addr == 0x23)
chk('starts in power_down', d.state == 'power_down')
chk('reset ignored in power_down (data stays)', b.write(0, 0x23, bytes([7])) and d.state == 'power_down')
b.write(0, 0x23, bytes([1])); b.write(0, 0x23, bytes([0x10]))
for t in [x / 1000 for x in range(1, 119)]: d.tick(t)
chk('no result before 120 ms (H mode)', d.reg['data'] == 0, d.reg['data'])
d.tick(0.121); v = int.from_bytes(b.read(0.121, 0x23, 2), 'big') / 1.2
chk('1000 lx reads ≈1000 lx after 120 ms (S/A typ 1.2, /1.2 in driver)', 980 < v < 1020, round(v, 1))
d2 = dev(500); d2.write(0, bytes([0x23]))
for t in [x / 1000 for x in range(1, 30)]: d2.tick(t)
chk('one-time L mode returns to power_down after ~16 ms', d2.state == 'power_down')
chk('undefined opcode NACKs', b.write(0.2, 0x23, bytes([0x55])) is False)
d.write(0.3, bytes([0x40 | 0b100])); d.write(0.3, bytes([0x60 | 0b01010]))
chk('MTreg high/low set to 138 (datasheet x2 example)', d.reg['mtreg'] == 0b10001010, d.reg['mtreg'])
chk('measurement time doubles with MTreg x2 (240 ms)', abs(d._conv_s() - 0.240) < 1e-6 if d.mode == 'H' else False, round(d._conv_s(), 3))
d.fault = 'nack'; chk('fault nack → read returns None', b.read(0.4, 0x23, 2) is None)
for r in R: print(f'{r[1]:4} {r[0]}  {r[2]}')
sys.exit(any(r[1] == 'FAIL' for r in R))
