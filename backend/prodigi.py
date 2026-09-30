"""Live Prodigi pricing.

Key is in `.env` (PRODIGI_API_KEY) — verified working: `GET /v4.0/products/{sku}`
resolves real products and `/v4.0/quotes` prices them.

Why this exists: our shop labels every price **EST** because we had no key.
Now we can quote properly — but Prodigi doesn't publish a listable catalogue
(`/v4.0/products` is 404; the web catalogue is JS-driven), so each SKU has to
come from your Prodigi dashboard or the Print API docs. Add `sku` to a product
in `config.PRODIGI_PRODUCTS` and it flips from EST to LIVE automatically.

    GET /api/prodigi/quote?sku=GLOBAL-CAN-10X10        live price
    GET /api/prodigi/check?sku=GLOBAL-CAN-10X10        does it exist + attributes
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request
from pathlib import Path

from . import config

BASE = "https://api.prodigi.com"
UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0 Safari/537.36")

# GLOBAL-CAN-10X10 proved the key works but demands a `wrap` attribute, which
# tells us the shape: attributes are per-SKU, so quoting needs them passed in.
DEFAULT_ATTRS = {"wrap": "White"}


class ProdigiError(Exception):
    pass


def api_key() -> str:
    p = Path(config.ROOT) / ".env"
    if p.exists():
        for line in p.read_text().splitlines():
            if line.startswith("PRODIGI_API_KEY="):
                return line.split("=", 1)[1].strip()
    return ""


def _call(method: str, path: str, body: dict | None = None, timeout: int = 25) -> dict:
    key = api_key()
    if not key:
        raise ProdigiError("no PRODIGI_API_KEY in .env")
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(BASE + path, data=data, method=method)
    req.add_header("X-API-Key", key)
    req.add_header("User-Agent", UA)
    if data:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode() or "{}")
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")[:400]
        try:
            return json.loads(detail)
        except Exception:
            raise ProdigiError(f"Prodigi {e.code}: {detail}") from None
    except Exception as e:
        raise ProdigiError(f"Prodigi unreachable: {e}") from None


def check_sku(sku: str) -> dict:
    """Does this SKU exist, and what does it need?"""
    d = _call("GET", f"/v4.0/products/{sku}")
    if d.get("outcome") == "Ok":
        p = d.get("product") or {}
        return {"ok": True, "sku": sku, "description": p.get("description", ""),
                "dimensions": p.get("productDimensions"),
                "attributes": p.get("attributes") or p.get("attributeSchema") or {}}
    fails = d.get("failures") or d.get("outcome") or d
    return {"ok": False, "sku": sku, "error": str(fails)[:300]}


def quote(sku: str, copies: int = 1, country: str = "GB",
          attrs: dict | None = None) -> dict:
    """Live price + shipping for a SKU. Raises ProdigiError when unavailable."""
    d = _call("POST", "/v4.0/quotes", {
        "shippingMethod": "Standard",
        "destinationCountryCode": country,
        "currencyCode": "GBP",
        "items": [{"sku": sku, "copies": int(copies),
                   "attributes": attrs or DEFAULT_ATTRS,
                   "assets": [{"printArea": "default"}]}],
    })
    if d.get("outcome") != "Created":
        raise ProdigiError(str(d.get("failures") or d.get("outcome"))[:300])
    q = (d.get("quotes") or [{}])[0]
    cs = q.get("costSummary") or {}
    # Real shape is {items, shipping, branding, totalCost, totalTax}, each
    # {amount: "16.00", currency: "GBP"} — not the .value/.unit we assumed.
    def money(section) -> tuple[str, float]:
        v = cs.get(section) or {}
        return str(v.get("currency") or "GBP"), float(v.get("amount") or 0)

    cur, total = money("totalCost")
    _, item = money("items")
    _, ship = money("shipping")
    _, tax = money("totalTax")
    carrier = ""
    ships = q.get("shipments") or []
    if ships:
        car = (ships[0].get("carrier") or {})
        carrier = f"{car.get('name', '')} {car.get('service', '')}".strip()
    return {"ok": True, "sku": sku, "currency": cur,
            "total": total, "item": item, "shipping": ship, "tax": tax,
            "carrier": carrier, "grade": "LIVE",
            "country": country, "copies": copies}


def to_cents(amount: float, unit: str) -> int:
    """Prodigi quotes GBP; our cards are USD cents. No FX feed here, so this
    is a flat, clearly-labelled conversion rather than a silent guess."""
    rate = 1.27 if str(unit).upper() == "GBP" else 1.0
    return int(round(amount * rate * 100))
