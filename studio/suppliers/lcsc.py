"""LCSC parts (JLC's parts house). Public live endpoint, no credentials: price ladders + stock.
Note: LCSC retail stock != JLC assembly stock (official Parts API gives the latter once approved)."""
import json, urllib.request
from .base import Supplier, Line, Money
URL = 'https://wmsc.lcsc.com/ftps/wm/product/detail?productCode='
class LCSC(Supplier):
    id = 'lcsc'; services = ['parts']
    def configured(self): return True
    def part(self, code):
        req = urllib.request.Request(URL + code, headers={'User-Agent': 'Mozilla/5.0', 'Referer': 'https://jlcpcb.com/'})
        r = json.load(urllib.request.urlopen(req, timeout=20)).get('result') or {}
        return dict(code=code, model=r.get('productModel'), stock=r.get('stockNumber'),
                    ladder=[(p['ladder'], float(p['productPrice'])) for p in r.get('productPriceList') or []])
    def quote(self, service, spec):
        p = self.part(spec['lcsc']); q = spec['qty']
        unit = next((pr for lad, pr in reversed(p['ladder']) if q >= lad), p['ladder'][0][1] if p['ladder'] else None)
        moq = p['ladder'][0][0] if p['ladder'] else 1
        buy = max(q, moq)
        return Line('lcsc', 'parts', p['model'], buy, Money(unit, basis='quote', ref=f'lcsc live {spec["lcsc"]}'),
                    Money(round(unit * buy, 2) if unit else None, basis='quote', ref=f'lcsc live {spec["lcsc"]}', note=f'stock {p["stock"]}, MOQ {moq}'), p)
    estimate = quote
