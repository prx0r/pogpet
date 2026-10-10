"""JLCPCB / JLC3DP adapter.
Official Open API: https://api.jlcpcb.com (apply; approval is reviewed). Base https://open.jlcpcb.com, POST JSON,
HMAC-SHA256 'JOP' Authorization header. Endpoint paths from the public jlcpcb-mcp client (Eyalm321), which
verifies its signer against JLC's documented sample vector. Credentials: env JLCPCB_APP_ID / JLCPCB_ACCESS_KEY /
JLCPCB_SECRET_KEY (later: Hark vault via connect_service, never in files).
Until approved, estimate() uses our measured rates and quote() raises NotConfigured -> browser quote fallback."""
import os, json, time, hmac, hashlib, base64, secrets, urllib.request, urllib.parse
from .base import Supplier, Line, Money

ENDPOINTS = {
    'tdp.upload': '/overseas/openapi/tdp/api/upload',          # multipart; signed body = meta JSON
    'tdp.analysis': '/overseas/openapi/tdp/api/file/result',   # {fileAccessId}
    'tdp.calculate': '/overseas/openapi/tdp/api/calculate',    # {fileAccessId, materialAccessId, materialColorAccessId, itemCount, surfaceTreatmentProcess, shippingAddress, freightMode}
    'tdp.order.create': '/overseas/openapi/tdp/api/order/create',
    'tdp.order.list': '/overseas/openapi/tdp/api/order/list',
    'tdp.order.detail': '/overseas/openapi/tdp/api/order/detail',
    'tdp.order.process': '/overseas/openapi/tdp/api/order/process',
    'pcb.upload': '/overseas/openapi/pcb/uploadGerber',
    'pcb.calculate': '/overseas/openapi/pcb/calculate',       # {orderType, fileKey, pcbParam{layers,dims,qty..}, country, postCode, city, shippingMethod}
    'pcb.audit': '/overseas/openapi/pcb/audit/get',
    'pcb.order.create': '/overseas/openapi/pcb/order/create',
    'pcb.order.detail': '/overseas/openapi/pcb/order/detail',
    'pcb.wip': '/overseas/openapi/pcb/wip/get',
}

class NotConfigured(RuntimeError): pass

def jop_header(app_id, access_key, secret, method, uri, body, ts=None, nonce=None):
    ts = ts or int(time.time()); nonce = nonce or secrets.token_hex(16)
    sts = f'{method.upper()}\n{uri}\n{ts}\n{nonce}\n{body}\n'
    sig = base64.b64encode(hmac.new(secret.encode(), sts.encode(), hashlib.sha256).digest()).decode()
    return f'JOP appid="{app_id}",accesskey="{access_key}",timestamp="{ts}",nonce="{nonce}",signature="{sig}"'

# Offline rates (USD). Measured where noted; 'assumption' rows must be replaced by API quotes before use in a pack.
RATES = {
    'tdp': {'wjp': dict(per_cm3=0.82, floor=6.91, basis='measured: JLC quotes 2026-10-09 (brick figure size sweep)'),
            'wjp-tough': dict(per_cm3=0.82, floor=6.91, basis='assumption: same as wjp'),
            'sla': dict(per_cm3=0.25, floor=1.0, basis='assumption'),
            'mjf': dict(per_cm3=0.35, floor=3.0, basis='assumption')},
    'pcb': dict(base_5pcs=2.0, per_extra_cm2=0.01, basis='assumption: JLC advertised 2-layer 100x100 5pcs price; quote decides'),
    'pcba': dict(setup=8.0, per_joint=0.0017, basis='assumption; quote decides'),
    'ship': dict(standard=6.05, basis='measured: JLC US Global Standard 2026-10-09'),
}

class JLC(Supplier):
    id = 'jlc'; services = ['tdp', 'pcb', 'pcba']
    base = os.environ.get('JLCPCB_ENDPOINT', 'https://open.jlcpcb.com')
    def creds(self):
        c = [os.environ.get(k) for k in ('JLCPCB_APP_ID', 'JLCPCB_ACCESS_KEY', 'JLCPCB_SECRET_KEY')]
        return c if all(c) else None
    def configured(self): return self.creds() is not None

    def _post(self, key, body):
        c = self.creds()
        if not c: raise NotConfigured('JLC API not approved/configured yet; use estimate() or the browser quote flow')
        uri = ENDPOINTS[key]; b = json.dumps(body, separators=(',', ':'))
        req = urllib.request.Request(self.base + uri, data=b.encode(), method='POST', headers={
            'Content-Type': 'application/json', 'Accept': 'application/json', 'Authorization': jop_header(*c, 'POST', uri, b)})
        d = json.load(urllib.request.urlopen(req, timeout=30))
        if d.get('code') != 200: raise RuntimeError(f'JLC {d.get("code")}: {d.get("message")}')
        return d.get('data')

    def estimate(self, service, spec):
        if service == 'tdp':
            r = RATES['tdp'][spec['process']]; q = spec.get('qty', 1)
            unit = max(r['floor'], spec['volume_cm3'] * r['per_cm3'])
            return Line('jlc', 'tdp', spec.get('name', 'part'), q, Money(round(unit, 2), note=r['basis']), Money(round(unit * q, 2), note=r['basis']), spec)
        if service == 'pcb':
            r = RATES['pcb']; area = spec['w_mm'] * spec['h_mm'] / 100
            tot = r['base_5pcs'] + max(0, area - 100) * r['per_extra_cm2'] * 5
            return Line('jlc', 'pcb', spec.get('name', 'pcb'), 5, Money(round(tot / 5, 2), note=r['basis']), Money(round(tot, 2), note=r['basis']), spec)
        if service == 'pcba':
            r = RATES['pcba']; q = spec.get('qty', 5)
            tot = r['setup'] + spec['joints'] * r['per_joint'] * q
            return Line('jlc', 'pcba', 'assembly', q, Money(round(tot / q, 2), note=r['basis']), Money(round(tot, 2), note=r['basis']), spec)
        raise ValueError(service)

    def quote(self, service, spec):
        if service == 'tdp':
            d = self._post('tdp.calculate', spec['jlc_params'])
            return Line('jlc', 'tdp', spec.get('name', 'part'), spec['jlc_params'].get('itemCount', 1), Money(None, basis='quote'), Money(d.get('totalPrice') if isinstance(d, dict) else None, basis='quote', ref=json.dumps(d)[:200]), d)
        if service == 'pcb':
            d = self._post('pcb.calculate', spec['jlc_params'])
            return Line('jlc', 'pcb', spec.get('name', 'pcb'), 0, Money(None, basis='quote'), Money(None, basis='quote', ref=json.dumps(d)[:200]), d)
        raise NotConfigured(f'no JLC API for {service} (PCBA/CNC quotes go through the browser flow)')
