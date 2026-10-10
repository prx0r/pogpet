"""Agent-facing design layer: parametric variants of a device template, design-rule checks, layout preview, pricing.
A design is a folder hwsim/designs/<name>/ with template.json (for pricing), board.json (for the sim) and device.json
(the capability contract, with safety limits derived from the design). Everything an agent can change is in PARAMS."""
import json, math, os, io, re, sys
H = os.path.dirname(os.path.abspath(__file__)); STUDIO = os.path.dirname(H); sys.path.insert(0, STUDIO)

SUPPLIES = {  # name: (usable mA at 5 V, what makes it true)
    'usb2_500': (500, 'any USB port; USB 2.0 default current'),
    'usb3_900': (900, 'USB 3.x port default current'),
    'usbc_1500': (1500, 'USB-C source advertising 1.5 A via CC; board needs 2x 5.1k CC pull-downs'),
    'usbc_3000': (3000, 'USB-C source advertising 3 A via CC; board needs 2x 5.1k CC pull-downs'),
}
RESERVE_MA = 120          # ESP32-C3 Wi-Fi average + sensor + LDO headroom (template rule)
LED_PITCH_MIN_MM = 6.5    # 5050 package + routing gap (DRC rule, conservative)
PARAMS = {
    'name': {'type': 'string', 'pattern': '^[a-z0-9_-]{3,32}$', 'description': 'lowercase id, 3-32 chars'},
    'base': {'type': 'string', 'enum': ['mood_lamp'], 'description': 'template to start from (keeps its locked interfaces)'},
    'led_count': {'type': 'integer', 'minimum': 1, 'maximum': 60},
    'ring_d_mm': {'type': 'number', 'minimum': 20, 'maximum': 140, 'description': 'LED ring diameter'},
    'supply': {'type': 'string', 'enum': list(SUPPLIES), 'description': '; '.join(f'{k}: {v[0]} mA ({v[1]})' for k, v in SUPPLIES.items())},
    'max_led_ma': {'type': 'integer', 'minimum': 20, 'maximum': 3000, 'description': 'LED current cap enforced by firmware; default = supply - 120 mA reserve'},
    'enclosure': {'type': 'string', 'enum': ['sla', 'mjf', 'wjp'], 'description': 'must match a JLC process with a rate: sla clear resin diffuser (default), mjf nylon (opaque, needs a separate diffuser), wjp full-colour'},
    'night_max_brightness': {'type': 'number', 'minimum': 0.02, 'maximum': 0.5},
}

def create(p):
    base = p.get('base', 'mood_lamp'); T = json.load(open(f'{STUDIO}/templates/{base}.json'))
    M = json.load(open(f'{STUDIO}/devices/{base}.device.json'))
    n = int(p.get('led_count', 12)); d = float(p.get('ring_d_mm', 52)); sup = p.get('supply', 'usb2_500'); smA = SUPPLIES[sup][0]
    cap = int(p.get('max_led_ma', smA - RESERVE_MA)); enc = p.get('enclosure', 'sla')
    errors, warnings = [], []
    pitch = math.pi * d / n if n > 1 else 99
    if pitch < LED_PITCH_MIN_MM: errors.append(f'LED pitch {pitch:.1f} mm < {LED_PITCH_MIN_MM} mm: use ≤{int(math.pi * d / LED_PITCH_MIN_MM)} LEDs or a ring ≥{math.ceil(n * LED_PITCH_MIN_MM / math.pi)} mm')
    if cap > smA - RESERVE_MA: errors.append(f'max_led_ma {cap} leaves < {RESERVE_MA} mA for the ESP32 on a {smA} mA supply: max {smA - RESERVE_MA}')
    full_white = n * (1 + 3 * 20)
    if cap < full_white * 0.25: warnings.append(f'cap {cap} mA is {cap / full_white:.0%} of full-white draw ({full_white} mA): colours will be dim')
    if sup.startswith('usbc'): warnings.append(f'{sup} only holds when the charger advertises it; on a plain USB port firmware must fall back to {500 - RESERVE_MA} mA (not modelled yet)')
    pcb = round(d + 10); 
    if pcb > 100: warnings.append(f'PCB {pcb} mm > 100 mm: leaves JLC cheapest tier')
    vol = round(0.0105 * d ** 2 * 2.2, 1)   # dome+base shell volume scaled from the 52 mm/38 cm3 template
    T2 = json.loads(json.dumps(T)); T2['id'] = f'DSN-{p["name"].upper()}'; T2['name'] = p['name']
    for part in T2['parts']:
        if part['part'] == 'ws2812b': part['qty'] = n; part['ref'] = f'LED1-{n}'; part['layout'] = {'ring_d_mm': d}
    T2['power'] = dict(source=sup, budget_ma=smA, reserve_ma=RESERVE_MA, led_cap_ma=cap)
    T2['pcb'].update(w_mm=pcb, h_mm=pcb, passives_joints=60 + 2 * n, extra_joints=16 + (4 if sup.startswith('usbc') else 0))
    T2['enclosure'] = dict(process=enc, material={'sla': 'clear resin diffuser + base', 'mjf': 'PA12 nylon base + separate diffuser', 'wjp': 'full-colour resin'}[enc], volume_cm3=vol, note='volume estimated from ring size')
    M2 = json.loads(json.dumps(M)); M2['safety']['max_led_ma'] = cap
    if 'night_max_brightness' in p: M2['safety']['night_max_brightness'] = float(p['night_max_brightness'])
    out = f'{H}/designs/{p["name"]}'; os.makedirs(out, exist_ok=True)
    if errors:   # failed DRC: record the attempt, but leave no buildable/simulatable files behind
        for f in ('template.json', 'board.json', 'device.json'):
            if os.path.exists(f'{out}/{f}'): os.remove(f'{out}/{f}')
        json.dump(dict(params=p, errors=errors, warnings=warnings), open(f'{out}/design.json', 'w'), indent=1)
        return dict(name=p['name'], ok=False, errors=errors, warnings=warnings, led_pitch_mm=round(pitch, 1), max_led_ma=cap, full_white_ma=full_white)
    board = {'board': p['name'], 'template': T2['id'], 'device_manifest': f'{out}/device.json',
             'rails': {'5V': {'source': sup, 'limit_ma': smA}, '3V3': {'source': 'LDO from 5V', 'limit_ma': 300, 'parent': '5V'}},
             'parts': [{'ref': 'U1', 'card': 'esp32c3', 'rail': '3V3'}, {'ref': 'U2', 'card': 'bh1750', 'rail': '3V3', 'bus': 'i2c0', 'strap': {'ADDR': 'L'}},
                       {'ref': f'LED1-{n}', 'card': 'ws2812b', 'rail': '5V', 'bus': 'rmt0', 'qty': n}], 'firmware': 'firmware/lamp_fw.py'}
    for f, o in (('template.json', T2), ('board.json', board), ('device.json', M2)): json.dump(o, open(f'{out}/{f}', 'w'), indent=1)
    json.dump(dict(params=p, errors=errors, warnings=warnings), open(f'{out}/design.json', 'w'), indent=1)
    return dict(name=p['name'], ok=not errors, errors=errors, warnings=warnings, led_count=n, ring_d_mm=d, led_pitch_mm=round(pitch, 1),
                pcb_mm=pcb, supply=sup, supply_ma=smA, max_led_ma=cap, full_white_ma=full_white, enclosure=enc, enclosure_cm3=vol)

def layout_png(name):
    from PIL import Image, ImageDraw
    from simulate import font
    B = json.load(open(f'{H}/designs/{name}/board.json')); T = json.load(open(f'{H}/designs/{name}/template.json'))
    n = [p for p in B['parts'] if p['card'] == 'ws2812b'][0]['qty']; d = [p for p in T['parts'] if p['part'] == 'ws2812b'][0]['layout']['ring_d_mm']
    pcb = T['pcb']['w_mm']; S = 560 / max(pcb, 60); im = Image.new('RGB', (1000, 640), (16, 16, 20)); g = ImageDraw.Draw(im); cx, cy = 320, 320
    g.ellipse([cx - pcb / 2 * S, cy - pcb / 2 * S, cx + pcb / 2 * S, cy + pcb / 2 * S], fill=(20, 70, 40), outline=(200, 200, 120), width=2)
    for i in range(n):
        a = 2 * math.pi * i / n - math.pi / 2; x, y = cx + d / 2 * S * math.cos(a), cy + d / 2 * S * math.sin(a); h = 2.5 * S
        g.rectangle([x - h, y - h, x + h, y + h], fill=(235, 235, 225), outline=(60, 60, 60))
    g.rectangle([cx - 9 * S, cy - 3 * S, cx + 9 * S, cy + 7 * S], fill=(40, 40, 46), outline=(150, 150, 160)); g.text((cx - 8 * S, cy), 'ESP32-C3', fill=(200, 200, 210), font=font(14))
    g.rectangle([cx - 1.5 * S, cy - 9 * S, cx + 1.5 * S, cy - 6 * S], fill=(90, 60, 30)); g.text((cx + 2 * S, cy - 10 * S), 'BH1750', fill=(220, 190, 140), font=font(13))
    y = 40
    for k, v in [('design', name), ('LEDs', f'{n} x WS2812B, {d:.0f} mm ring'), ('pitch', f'{math.pi * d / n:.1f} mm'), ('PCB', f'{pcb} mm round, 2L'),
                 ('supply', f'{T["power"]["source"]} ({T["power"]["budget_ma"]} mA)'), ('LED cap', f'{T["power"]["led_cap_ma"]} mA'), ('enclosure', f'{T["enclosure"]["process"]}, ~{T["enclosure"]["volume_cm3"]} cm3')]:
        g.text((640, y), k, fill=(140, 140, 150), font=font(16)); g.text((640, y + 20), str(v), fill=(230, 230, 235), font=font(18)); y += 60
    bio = io.BytesIO(); im.save(bio, 'PNG'); return bio.getvalue()

def quote(name, units):
    from estimate import estimate
    T = json.load(open(f'{H}/designs/{name}/template.json')); o = estimate(T, units); lines = o.pop('_lines')
    o['lines'] = [dict(supplier=l.supplier, service=l.service, item=l.item, qty=l.qty, usd=l.total.amount, basis=l.total.basis, note=l.total.note[:80]) for l in lines]
    json.dump(o, open(f'{H}/designs/{name}/quote_{units}.json', 'w'), indent=1, default=str); return o
