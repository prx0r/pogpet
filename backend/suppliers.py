"""Supplier registry + landed-cost estimator (vision: design contracts).

Every product declares suppliers as data: capabilities (materials, colours,
build volume, regions), ordering (API/manual/quote), and an estimate model.
Estimates are clearly marked — live quotes always win. No supplier keys live
here; API integrations store keys env-only when built.
"""
from __future__ import annotations

SUPPLIERS: dict[str, dict] = {
    "makr3d": {
        "label": "MAKR3D (Yorkshire3D farm, Huddersfield UK)",
        "home": "UK", "ships": ["UK", "worldwide"],
        "materials": ["PLA", "PETG"], "colors_max": 4,
        "build_mm": [256, 256, 256],
        "order": "api", "api": "Shopify/Etsy/CSV/manual/public API",
        "min_qty": 1, "account": "free, no card",
        "commitment": "none — pay per order",
        "dispatch_days": [1, 2],
        "notes": "Home farm. Instant file quotes (£1.29 benchy / £2.50 fidget / "
                 "£7.60 articulated ex-VAT), £1 min per order. Human QA per order.",
        "est": {"kind": "band", "bands": [[10, 129], [40, 250]],
                "default_cents": None, "ccy": "GBP"},
    },
    "yorkshire3d": {
        "label": "Yorkshire3D custom manufacturing (UK B2B)",
        "home": "UK", "ships": ["UK", "worldwide"],
        "materials": ["PLA", "PETG", "TPU", "ASA"], "colors_max": 40,
        "build_mm": [256, 256, 256],
        "order": "quote", "api": "written quote, 1 business day",
        "min_qty": 1, "account": "quote-based",
        "commitment": "none — pay per quote; tiers 50+",
        "dispatch_days": [3, 10],
        "notes": "Escape hatch for TPU/ASA/assemblies/inserts. Volume tiers 50+.",
        "est": {"kind": "quote", "ccy": "GBP"},
    },
    "fdfarm": {
        "label": "3dfarm (York UK, UK-only shipping)",
        "home": "UK", "ships": ["UK"],
        "materials": ["PLA", "PETG", "TPU", "Resin"], "colors_max": 14,
        "build_mm": [256, 256, 256],
        "order": "manual", "api": "browser quote tool (no public API)",
        "min_qty": 1, "account": "none needed",
        "commitment": "none — one part to fifty",
        "dispatch_days": [2, 2],
        "notes": "Per-cm3 published rates. Backup UK farm.",
        "est": {"kind": "per_cm3", "PLA": 320, "PETG": 450, "ccy": "GBP"},
    },
    "treatstock": {
        "label": "Treatstock (global vendor network, per-country offers)",
        "home": "global", "ships": ["worldwide"],
        "materials": ["PLA", "PETG", "TPU", "Resin", "Nylon"], "colors_max": 99,
        "build_mm": [500, 500, 500],
        "order": "api", "api": "v2: upload→price(location[country])→order; key via support",
        "min_qty": 1, "account": "free",
        "commitment": "none — single object to 10000+ parts",
        "dispatch_days": [2, 7],
        "notes": "The per-country engine: location[country] returns local vendor "
                 "offers. Affiliate rewards per order. No key stored.",
        "est": {"kind": "quote", "ccy": "USD"},
    },
    "craftcloud": {
        "label": "Craftcloud/All3DP (150+ shops, quote compare)",
        "home": "global", "ships": ["worldwide"],
        "materials": ["PLA", "PETG", "TPU", "Nylon", "Resin"], "colors_max": 99,
        "build_mm": [500, 500, 500],
        "order": "api", "api": "v5: model→parse→price→cart→order (+MCP via Kiln)",
        "min_qty": 1, "account": "free",
        "commitment": "none — no minimum order value",
        "dispatch_days": [3, 7],
        "notes": "Best for one-off compare shopping, not store sync.",
        "est": {"kind": "quote", "ccy": "USD"},
    },
    "dapi3d": {
        "label": "3DAPI (US+EU store fulfilment, 30+ centres)",
        "home": "US/EU", "ships": ["worldwide"],
        "materials": ["PLA", "PETG"], "colors_max": 4,
        "build_mm": [256, 256, 256],
        "order": "api", "api": "Shopify/Etsy/eBay/Woo + API; SKU mapping",
        "min_qty": 1, "account": "free plan",
        "commitment": "none — pay per order",
        "dispatch_days": [2, 5],
        "notes": "US/EU answer to MAKR3D: store-connected dropship fulfilment.",
        "est": {"kind": "quote", "ccy": "USD"},
    },
    "sculpteo": {
        "label": "Sculpteo (FR+US plants, enterprise API)",
        "home": "EU/US", "ships": ["worldwide"],
        "materials": ["PLA", "PETG", "Nylon", "Resin"], "colors_max": 99,
        "build_mm": [500, 500, 500],
        "order": "api", "api": "upload/quote/cart/track; key via partnership",
        "min_qty": 1, "account": "free",
        "commitment": "none — pay per print",
        "dispatch_days": [3, 7],
        "notes": "Premium/EU lane. Free API access, pay per print.",
        "est": {"kind": "quote", "ccy": "EUR"},
    },
}


def estimate(supplier_id: str, *, material: str = "PLA", colors: int = 1,
             dims_mm: list | None = None, volume_cm3: float | None = None,
             weight_g: float | None = None) -> dict:
    """Feasibility + rough cost for a line on a supplier.

    Returns {feasible, gaps[], est_cents|None, ccy, basis, dispatch_days}.
    Estimates are bands/quotes, never promises — live quotes win.
    """
    spec = SUPPLIERS.get(supplier_id)
    if not spec:
        return {"feasible": False, "gaps": ["unknown supplier"], "est_cents": None}
    gaps = []
    if material not in spec["materials"]:
        gaps.append(f"{material} not stocked (has {', '.join(spec['materials'])})")
    if colors > spec["colors_max"]:
        gaps.append(f"{colors} colours > max {spec['colors_max']}")
    if dims_mm and any(d > b for d, b in zip(dims_mm, spec["build_mm"])):
        gaps.append(f"{dims_mm}mm exceeds {spec['build_mm']}mm build")
    if gaps:
        return {"feasible": False, "gaps": gaps, "est_cents": None,
                "ccy": spec["est"].get("ccy", "GBP")}
    model = spec["est"]
    est, basis = None, "live quote"
    if model["kind"] == "band" and weight_g is not None:
        est, basis = model["bands"][-1][1], "weight band (ex-VAT)"
        for limit, cents in model["bands"]:
            if weight_g <= limit:
                est = cents
                break
        est = max(100, est)
    elif model["kind"] == "per_cm3" and volume_cm3 is not None:
        rate = model.get(material)
        if rate:
            est, basis = round(volume_cm3 * rate), f"£{rate / 100:.2f}/cm³ {material}"
    return {"feasible": True, "gaps": [], "est_cents": est,
            "ccy": model.get("ccy", "GBP"), "basis": basis,
            "dispatch_days": spec["dispatch_days"]}


def can_single_order(supplier_id: str) -> dict:
    """Qty-1 with no relationship: every registered farm takes single orders
    with no account commitment beyond (at most) a free account."""
    spec = SUPPLIERS.get(supplier_id)
    if not spec:
        return {"ok": False, "reason": "unknown supplier"}
    ok = spec.get("min_qty", 1) == 1
    return {"ok": ok, "min_qty": spec.get("min_qty", 1),
            "account": spec.get("account", "unknown"),
            "commitment": spec.get("commitment", "unknown")}


def options_for(*, material: str = "PLA", colors: int = 1,
                dims_mm: list | None = None, volume_cm3: float | None = None,
                weight_g: float | None = None,
                region: str = "") -> list[dict]:
    """All suppliers ranked: home-region feasible first, then the rest."""
    out = []
    for sid, spec in SUPPLIERS.items():
        r = estimate(sid, material=material, colors=colors, dims_mm=dims_mm,
                     volume_cm3=volume_cm3, weight_g=weight_g)
        r.update({"supplier": sid, "label": spec["label"],
                  "ships": spec["ships"], "order": spec["order"]})
        if region and region not in spec["ships"] and "worldwide" not in spec["ships"]:
            r["feasible"] = False
            r["gaps"] = (r.get("gaps") or []) + [f"does not ship to {region}"]
        out.append(r)
    out.sort(key=lambda r: (not r["feasible"],
                            0 if region in SUPPLIERS[r["supplier"]]["ships"] else 1,
                            r["est_cents"] if r["est_cents"] is not None else 10 ** 9))
    return out
