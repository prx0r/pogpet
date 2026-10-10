"""Project feasibility: run a kit idea through every supplier lane.

Idea = {name, parts_3d[], paper_skus[], components_std[], kitting}.
Each lane returns {lane, grade, feasible, est_cents/ccy, gaps[], note}.
Grades: LIVE (live quote now) > verified (catalog/SKU confirmed) >
STAGED (needs setup: template/shop/app approval/partner) > quote
(web quote path) > unavailable. Overall verdict: producible (all lanes
live/feasible) · staged (setup steps remain) · blocked (a lane refuses
with no path). Costs roll up knowns; unknowns stay flagged, never faked.
Docs: docs/personalised-projects.md (the vision), docs/vendor/*.
"""
from __future__ import annotations

ALIAXPRESS_NOTE = ("standard components via AliExpress Open Platform "
                   "dropshipping APIs (product search + orders) — needs "
                   "developer app approval (1–2 days); no key stored")
US_STATION_NOTE = ("kitting/pack/ship op takes the frozen BOM + packing "
                   "list — partner interface defined, no partner signed")


def check_idea(idea: dict) -> dict:
    """Pure runner except paper SKUs (free live Prodigi quotes)."""
    from backend import suppliers as _sup
    name = str(idea.get("name") or "untitled")[:80]
    lanes = []
    for part in idea.get("parts_3d") or []:
        lanes.append(_check_3d_part(_sup, part))
    for part in idea.get("parts_elec") or []:
        lanes.append(_check_elec_part(part))
    for sku in idea.get("paper_skus") or []:
        lanes.append(_check_paper(sku))
    if idea.get("components_std"):
        lanes.append({"lane": "aliexpress", "grade": "staged",
                      "feasible": True,
                      "components": list(idea["components_std"]),
                      "est_cents": None, "ccy": None,
                      "gaps": ["app approval + component price pull"],
                      "note": ALIAXPRESS_NOTE})
    if idea.get("kitting"):
        lanes.append({"lane": "us_station", "grade": "staged",
                      "feasible": True, "est_cents": None, "ccy": None,
                      "gaps": ["kitting partner + ship rates"],
                      "options": [
                          {"partner": "china_fulfillment",
                           "base": "USD 50 kit + 99 pick/pack",
                           "note": "branded per-order lead (verify RFQ)"},
                          {"partner": "leicester",
                           "base": "GBP from 50/kit",
                           "note": "UK pilot, assemble-to-order, no minimum"}],
                      "note": US_STATION_NOTE})
    known = {}
    for l in lanes:
        if l.get("est_cents") and l.get("feasible") and l.get("ccy"):
            known[l["ccy"]] = known.get(l["ccy"], 0) + l["est_cents"]
    grades = [l["grade"] for l in lanes]
    if any(not l.get("feasible") for l in lanes):
        verdict = "blocked"
    elif any(g in ("staged", "quote", "unavailable") for g in grades):
        verdict = "staged"
    else:
        verdict = "producible"
    return {"ok": True, "idea": name, "verdict": verdict, "lanes": lanes,
            "known_costs": known,
            "note": "unknowns flagged per lane — never faked"}


def _check_3d_part(sup, part: dict) -> dict:
    material = str(part.get("material") or "PLA")
    opts = sup.options_for(material=material,
                           colors=int(part.get("colors") or 1),
                           dims_mm=part.get("dims_mm"),
                           volume_cm3=part.get("volume_cm3"),
                           weight_g=part.get("weight_g"))
    feasible = [o for o in opts if o["feasible"]]
    live = [o for o in feasible if o.get("est_cents") is not None]
    best = min(live, key=lambda o: o["est_cents"]) if live else None
    gaps = []
    if not feasible:
        gaps = sorted({g for o in opts for g in (o.get("gaps") or [])})
    return {"lane": "fdm_3d", "part": str(part.get("name") or "part")[:40],
            "grade": "LIVE" if best else ("quote" if feasible else "blocked"),
            "feasible": bool(feasible),
            "est_cents": best["est_cents"] if best else None,
            "ccy": best["ccy"] if best else None,
            "best_supplier": best["supplier"] if best else None,
            "feasible_suppliers": [o["supplier"] for o in feasible],
            "gaps": gaps,
            "note": "cheapest live estimate wins; resin needs the jlc lane"}


def _check_elec_part(part: dict) -> dict:
    """Electronics sub-assembly: Elecrow/Makerfabs/Seeed/PCBWay quote
    lanes (all RFQ, no fake numbers). M5Stack/LCSC feed modules/parts
    into those lanes rather than assembling."""
    houses = ["elecrow", "makerfabs", "seeed", "pcbway"]
    if str(part.get("modules_only") or "").lower() in ("1", "true", "yes"):
        houses = ["m5stack", "lcsc", "seeed"]
    return {"lane": "electronics",
            "part": str(part.get("name") or "assembly")[:40],
            "grade": "quote", "feasible": True,
            "est_cents": None, "ccy": "USD",
            "quote_houses": houses,
            "gaps": ["RFQ per house (no public pricing API)"],
            "note": "Elecrow first (prior contact Sep 2026); Seeed from "
                    "5 sets; modules via M5Stack/LCSC into house assembly"}


def _check_paper(sku: str) -> dict:
    try:
        from backend import prodigi as _pdi
        q = _pdi.quote(sku, country="GB", attrs={})
        return {"lane": "paper", "sku": sku, "grade": "LIVE", "feasible": True,
                "est_cents": _pdi.to_cents(q["item"], q["currency"]),
                "ccy": "USD",
                "note": f"Prodigi live: item £{q['item']:.2f} + ship £{q['shipping']:.2f}"}
    except Exception as e:
        return {"lane": "paper", "sku": sku, "grade": "error",
                "feasible": False, "est_cents": None, "ccy": None,
                "gaps": [str(e)[:200]], "note": "live quote failed"}
