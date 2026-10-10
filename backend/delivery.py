"""Value / speed / balanced routing + order-by countdowns.

Delivery-date reality (researched 2026-10-10 — no supplier hands us a
guaranteed-date API except Overnight's order-time BITGIT promise):
- Prodigi quotes carry costs + carrier only, no dates. Typical production:
  classic UK cards 24h, global range 24–72h, wrap 1–2d.
- Mixam's calculator shows estimated delivery dates (manual path).
- Overnight BITGIT / Moo next-day promise dates AT ORDER time.
So countdowns below are COMPUTED from order cutoffs + production windows
and labelled dispatch (not delivery) — except where a supplier promises.
Docs: docs/vendor/*.md. Pure functions (now-injectable) + live builders.
"""
from __future__ import annotations

import datetime as _dt

# Order cutoffs: supplier tz + local hour. Sources: Mixam 4pm GMT/CT/AEST
# cutoff docs; Moo 2pm EST next-day page; Overnight 8pm EST BITGIT page.
CUTOFFS = {
    "mixam": ("Europe/London", 16),
    "overnightprints": ("America/New_York", 20),
    "moo": ("America/New_York", 14),
}

# Typical production windows (business days) per Prodigi SKU family.
# Classic UK = 24h manufacture; global = 24–72h; wrap = 1–2d typical.
PROD_DAYS = {
    "WRAP-1-50X70": (1, 2),
    "CLASSIC-GRE-FEDR-7X5-BLA": (1, 1),
    "GLOBAL-GRE-MOH-7X5-BLA": (1, 3),
}

# Routable lines: live Prodigi SKUs (+markets) + staged supplier entries.
ROUTES = {
    "wrapping_paper": {
        "prodigi": [{"sku": "WRAP-1-50X70", "markets": ["GB", "US"]}],
        "staged": [
            {"supplier": "printify", "grade": "catalog",
             "blueprint_id": 848, "print_provider_id": 69,
             "provider_name": "Prodigi",
             "variants": [
                 {"id": 76531, "label": "20x28in satin single",
                  "placeholder_px": [5906, 8268]},
                 {"id": 76532, "label": "30x36in satin single",
                  "placeholder_px": [8858, 10630]}],
             "dispatch": [2, 5],
             "note": "same farm as direct SKU; variant print costs need "
                     "shop context (PRINTIFY_SHOP_ID)"},
            {"supplier": "gelato", "grade": "unavailable",
             "dispatch": None,
             "note": "no wrapping paper in Gelato range — enters on "
                     "cards/stationery"},
        ],
    },
    "greeting_card": {
        "prodigi": [
            {"sku": "CLASSIC-GRE-FEDR-7X5-BLA", "markets": ["GB"]},
            {"sku": "GLOBAL-GRE-MOH-7X5-BLA", "markets": ["GB", "US"]},
        ],
        "staged": [
            {"supplier": "mixam", "grade": "staged", "dispatch": [2, 5],
             "note": "instant calculator shows delivery dates (manual path)"},
            {"supplier": "overnightprints", "grade": "staged",
             "dispatch": [1, 2],
             "note": "BITGIT promises the date at order (US only)"},
            {"supplier": "moo", "grade": "staged", "dispatch": [2, 5],
             "note": "premium; US next-day postcards at 2pm EST"},
            {"supplier": "gotprint", "grade": "staged", "dispatch": [3, 7],
             "note": "3 US plants; min 25 cards"},
        ],
    },
}


def _add_bdays(day: _dt.date, n: int) -> _dt.date:
    d = day
    while n > 0:
        d += _dt.timedelta(days=1)
        if d.weekday() < 5:
            n -= 1
    return d


def _fmt_delta(td: _dt.timedelta) -> str:
    s = max(0, int(td.total_seconds()))
    h, rem = divmod(s, 3600)
    m = rem // 60
    if h >= 48:
        return f"{h // 24}d {h % 24}h"
    return f"{h}h {m:02d}m"


def countdown(dispatch: list | None, supplier: str,
              now: _dt.datetime | None = None) -> dict:
    """Order-by countdown for one option. now: aware datetime (UTC default).

    Returns {mode, order_within?, cutoff_at?, dispatch_early,
    dispatch_guaranteed, note}. Dates are dispatch (not delivery) except
    BITGIT-style promises, flagged in note. Business days throughout.
    """
    from zoneinfo import ZoneInfo
    if now is None:
        now = _dt.datetime.now(_dt.timezone.utc)
    lo, hi = (dispatch or [1, 3])[:2]
    cut = CUTOFFS.get(supplier)
    if not cut:
        return {"mode": "open",
                "dispatch_early": _add_bdays(now.date(), lo).isoformat(),
                "dispatch_guaranteed": _add_bdays(now.date(), hi).isoformat(),
                "note": "no published order cutoff — dispatch counted from now"}
    tzname, hour = cut
    local = now.astimezone(ZoneInfo(tzname))
    decide = local.date()
    if local.weekday() >= 5 or local.hour >= hour:
        # after cutoff (or weekend): next working day
        decide += _dt.timedelta(days=1)
        while decide.weekday() >= 5:
            decide += _dt.timedelta(days=1)
    cutoff_at = _dt.datetime(decide.year, decide.month, decide.day, hour,
                             tzinfo=ZoneInfo(tzname))
    return {"mode": "cutoff",
            "order_within": _fmt_delta(cutoff_at - local),
            "cutoff_at": cutoff_at.isoformat(),
            "dispatch_early": _add_bdays(decide, lo).isoformat(),
            "dispatch_guaranteed": _add_bdays(decide, hi).isoformat(),
            "note": "dispatch dates (business days); delivery per carrier"}


def pick(live: list) -> dict:
    """value (cheapest) / speed (quickest dispatch) / balanced (best ratio)
    across LIVE options. Each pick: {supplier, total, currency[, note]}."""
    if not live:
        return {}
    value = min(live, key=lambda o: o["total"])
    speed = min(live, key=lambda o: o.get("dispatch", [99])[0])
    ratio = min(live, key=lambda o: o["total"] / max(1, o.get("dispatch", [1, 3])[1]))
    out = {
        "value": {"supplier": value["supplier"], "total": value["total"],
                  "currency": value["currency"]},
        "speed": {"supplier": speed["supplier"], "total": speed["total"],
                  "currency": speed["currency"]},
        "balanced": {"supplier": ratio["supplier"], "total": ratio["total"],
                     "currency": ratio["currency"]},
    }
    if len(live) == 1:
        out["speed"]["note"] = ("single live quote — speed splits when 2+ "
                                "suppliers quote etas")
        out["balanced"]["note"] = "single live quote — ratio trivial"
    return out


def build(line: str, country: str = "GB") -> dict:
    """Live options + picks + GB/US matrix + countdowns. Raises KeyError
    on unmapped lines (caller 400s). Prodigi quotes are free."""
    from backend import prodigi as _pdi
    route = ROUTES[line]  # KeyError → caller maps to 400
    options = []
    for spec in route["prodigi"]:
        if country not in spec["markets"]:
            options.append({"supplier": "prodigi", "grade": "unavailable",
                            "sku": spec["sku"],
                            "note": f"{spec['sku']} does not serve {country}"})
            continue
        try:
            q = _pdi.quote(spec["sku"], country=country, attrs={})
            lo, hi = PROD_DAYS.get(spec["sku"], (1, 3))
            options.append({"supplier": "prodigi", "grade": "LIVE",
                            "sku": spec["sku"], "currency": q["currency"],
                            "item": q["item"], "shipping": q["shipping"],
                            "tax": q["tax"], "total": q["total"],
                            "carrier": q["carrier"],
                            "lab_country": q.get("lab_country", ""),
                            "warnings": q.get("warnings", []),
                            "dispatch": [lo, hi]})
        except Exception as e:
            options.append({"supplier": "prodigi", "grade": "error",
                            "sku": spec["sku"], "error": str(e)[:200]})
    options.extend(dict(s) for s in route.get("staged", []))
    live = [o for o in options if o["grade"] == "LIVE"]
    picks = pick(live)
    if picks.get("speed"):
        spd = next(o for o in live
                   if o["supplier"] == picks["speed"]["supplier"]
                   and o.get("sku"))
        picks["speed"]["countdown"] = countdown(
            spd.get("dispatch"), spd["supplier"])
    matrix = {}
    if line == "wrapping_paper":
        for dest in ("GB", "US"):
            try:
                qm = _pdi.quote("WRAP-1-50X70", country=dest, attrs={})
                matrix[dest] = {"total": qm["total"],
                                "currency": qm["currency"],
                                "carrier": qm["carrier"],
                                "lab_country": qm.get("lab_country", ""),
                                "warnings": qm.get("warnings", [])}
            except Exception as e:
                matrix[dest] = {"error": str(e)[:200]}
    return {"options": options, "picks": picks, "matrix": matrix}
