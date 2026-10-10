#!/usr/bin/env python3
"""Estimate a device template end to end: parts (LCSC live), PCB + assembly + enclosure (JLC), shipping.
  python3 studio/estimate.py mood_lamp [--units 5]
Every line says its basis: quote (live supplier data) or estimate (our rate table). Never call an estimate a quote."""
import sys, os, json, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from suppliers.jlc import JLC, RATES
from suppliers.lcsc import LCSC
from suppliers.base import as_dict
H = os.path.dirname(os.path.abspath(__file__))
tid = sys.argv[1]; units = int(sys.argv[sys.argv.index('--units') + 1]) if '--units' in sys.argv else 5
T = json.load(open(f'{H}/templates/{tid}.json')); jlc, lcsc = JLC(), LCSC(); lines = []; joints = 0
for p in T['parts']:
    P = json.load(open(f'{H}/parts/{p["part"]}.json')); joints += P['joints'] * p['qty']
    lines.append(lcsc.quote('parts', dict(lcsc=P['lcsc'], qty=p['qty'] * units)))
pc = T['pcb']; joints += pc['passives_joints'] + pc['extra_joints']
lines.append(jlc.estimate('pcb', dict(name=f'{pc["layers"]}L PCB {pc["w_mm"]}x{pc["h_mm"]}', w_mm=pc['w_mm'], h_mm=pc['h_mm'])))
lines.append(jlc.estimate('pcba', dict(joints=joints, qty=units)))
e = T['enclosure']; lines.append(jlc.estimate('tdp', dict(name='enclosure', process=e['process'], volume_cm3=e['volume_cm3'], qty=units)))
tot = sum(l.total.amount or 0 for l in lines) + RATES['ship']['standard'] * 2
quoted = sum(l.total.amount or 0 for l in lines if l.total.basis == 'quote')
out = dict(template=tid, units=units, lines=[as_dict(l) for l in lines], shipping_usd=RATES['ship']['standard'] * 2,
           total_usd=round(tot, 2), per_unit_usd=round(tot / units, 2), quoted_share=round(quoted / tot, 2), joints_per_board=joints,
           jlc_api=('configured' if jlc.configured() else 'not approved yet: PCB/PCBA/enclosure lines are estimates'))
os.makedirs(f'{H}/out', exist_ok=True); json.dump(out, open(f'{H}/out/{tid}_estimate.json', 'w'), indent=1, default=str)
for l in lines: print(f'{l.supplier:5} {l.service:6} {l.item[:34]:34} x{l.qty:<4} ${l.total.amount:>7}  [{l.total.basis}] {l.total.note[:60]}')
print(f'ship   2 parcels ${RATES["ship"]["standard"]*2:.2f} [estimate]\nTOTAL ${tot:.2f} for {units} units = ${tot/units:.2f}/unit; {out["quoted_share"]*100:.0f}% of it is live-quoted')
