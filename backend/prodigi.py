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


def _base() -> str:
    import os as _os
    return (_os.environ.get("PRODIGI_BASE") or BASE).rstrip("/")


def _call(method: str, path: str, body: dict | None = None, timeout: int = 25) -> dict:
    key = api_key()
    if not key:
        raise ProdigiError("no PRODIGI_API_KEY in .env")
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(_base() + path, data=data, method=method)
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
          attrs: dict | None = None, shipping_method: str = "Standard") -> dict:
    """Live price + shipping for a SKU. Raises ProdigiError when unavailable.
    attrs=None keeps the legacy default set; pass {} for SKUs (like the
    classic card) that reject unexpected attributes."""
    item = {"sku": sku, "copies": int(copies),
            "assets": [{"printArea": "default"}]}
    picked = DEFAULT_ATTRS if attrs is None else attrs
    if picked:
        item["attributes"] = picked
    d = _call("POST", "/v4.0/quotes", {
        "shippingMethod": shipping_method,
        "destinationCountryCode": country,
        "currencyCode": "GBP",
        "items": [item],
    })
    if d.get("outcome") not in ("Created", "CreatedWithIssues"):
        raise ProdigiError(str(d.get("failures") or d.get("outcome"))[:300])
    # CreatedWithIssues still quotes (e.g. US sales-tax warning) — surface
    # the warnings instead of failing: location-dependent pricing depends
    # on accepting them. Issues shape: [{errorCode, description}].
    warnings = [i.get("description", i.get("errorCode", ""))
                for i in (d.get("issues") or []) if isinstance(i, dict)]
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
    lab = ""
    ships = q.get("shipments") or []
    if ships:
        car = (ships[0].get("carrier") or {})
        carrier = f"{car.get('name', '')} {car.get('service', '')}".strip()
        lab = ((ships[0].get("fulfillmentLocation") or {}).get("countryCode")
               or "")
    return {"ok": True, "sku": sku, "currency": cur,
            "total": total, "item": item, "shipping": ship, "tax": tax,
            "carrier": carrier, "grade": "LIVE",
            "lab_country": lab, "warnings": warnings,
            "country": country, "copies": copies}


def to_cents(amount: float, unit: str) -> int:
    """Prodigi quotes GBP; our cards are USD cents. No FX feed here, so this
    is a flat, clearly-labelled conversion rather than a silent guess."""
    rate = 1.27 if str(unit).upper() == "GBP" else 1.0
    return int(round(amount * rate * 100))


def print_area(sku: str) -> dict:
    """Live print-area spec for a SKU, cached per SKU. The renderer rejects
    anything that doesn't match these exact pixels — supplier-safe, not
    'probably 5x7'."""
    cache = config.DATA / "prodigi_templates.json"
    try:
        saved = json.loads(cache.read_text()) if cache.is_file() else {}
    except ValueError:
        saved = {}
    if sku in saved and isinstance(saved[sku], dict) \
            and saved[sku].get("horizontalResolution"):
        return saved[sku]
    d = _call("GET", f"/v4.0/products/{sku}")
    variants = (d.get("product") or {}).get("variants") or []
    sizes = {}
    for v in variants:
        if isinstance(v, dict) and v.get("printAreaSizes"):
            sizes = v["printAreaSizes"]
            break
    if not sizes or "default" not in sizes:
        raise ProdigiError(f"no default print area for {sku}")
    spec = {"sku": sku,
            "horizontalResolution": int(sizes["default"]["horizontalResolution"]),
            "verticalResolution": int(sizes["default"]["verticalResolution"])}
    saved[sku] = spec
    try:
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_text(json.dumps(saved, indent=2))
    except OSError:
        pass
    return spec


def create_order(sku: str, copies: int, asset_url: str, recipient: dict,
                 shipping_method: str = "Standard",
                 currency: str = "GBP") -> dict:
    """Place a real print order. SPENDS REAL MONEY — callers gate on explicit
    fulfil + configured SKU. Returns Prodigi order id + status."""
    for k in ("name", "line1", "town", "postcode", "country"):
        if not str((recipient or {}).get(k) or "").strip():
            raise ProdigiError(f"recipient.{k} is required")
    addr = {
        "line1": recipient["line1"][:100],
        "postalOrZipCode": recipient["postcode"][:20],
        "countryCode": recipient["country"][:2].upper(),
        "townOrCity": recipient["town"][:60],
    }
    if str(recipient.get("line2") or "").strip():
        addr["line2"] = str(recipient["line2"])[:100]
    body = {
        "shippingMethod": shipping_method,
        "currencyCode": currency,
        "recipient": {
            "name": recipient["name"][:60],
            "address": addr,
        },
        "items": [{
            "sku": sku,
            "copies": max(1, int(copies)),
            "sizing": "fillPrintArea",
            "assets": [{"printArea": "default", "url": asset_url}],
        }],
    }
    if recipient.get("email"):
        body["recipient"]["email"] = str(recipient["email"])[:120]
    d = _call("POST", "/v4.0/orders", body)
    order = d.get("order") or {}
    if not order.get("id"):
        raise ProdigiError(str(d.get("failures") or d)[:300])
    return {"ok": True, "id": order.get("id"),
            "status": order.get("status", {}).get("stage", "received"),
            "sku": sku, "copies": copies}
