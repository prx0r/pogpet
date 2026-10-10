"""Component registry + verified project recipes (kit assembly core).

Units: stocked common parts (pick from warehouse), made-to-order parts
(produce on purchase), special-order parts (source when necessary).
Order states are explicit and forward-only: needed → ordered → received
→ verified. "Ordered" is never "received"; "received" is never
"verified". A box packs only when every line is verified.
Box rates are published bases (China-Fulfillment: $0.50 kit + $0.99
pick/pack) — estimates, confirmed per partner RFQ.
Docs: docs/kit-assembly.md, docs/shenzhen-hub.md.
"""
from __future__ import annotations

import time

KIT_RATES = {"kitting_cents": 50, "pick_pack_cents": 99, "ccy": "USD",
             "note": "published base rates — confirm per partner RFQ"}

# kind: stocked | made | special
COMPONENTS = {
    "OH-BEAD-001": {"name": "Glass bead mix", "kind": "stocked",
                    "suppliers": [{"supplier": "1688", "sku": "BEAD-MIX-100",
                                   "moq": 100}],
                    "inventory": {"Shenzhen": 400, "UK-01": 0},
                    "compatible_projects": ["charm_lab"],
                    "packing": {"bag": "A", "label": "A01"}},
    "OH-CHAIN-001": {"name": "Chain, 10cm", "kind": "stocked",
                     "suppliers": [{"supplier": "1688", "sku": "CHAIN-10",
                                    "moq": 50}],
                     "inventory": {"Shenzhen": 120, "UK-01": 0},
                     "compatible_projects": ["charm_lab"],
                     "packing": {"bag": "A", "label": "A02"}},
    "OH-CLASP-001": {"name": "Lobster clasp", "kind": "stocked",
                     "suppliers": [{"supplier": "1688", "sku": "CLASP-12",
                                    "moq": 50}],
                     "inventory": {"Shenzhen": 120, "UK-01": 0},
                     "compatible_projects": ["charm_lab"],
                     "packing": {"bag": "A", "label": "A03"}},
    "OH-CORD-001": {"name": "Cord, 1m", "kind": "stocked",
                    "suppliers": [{"supplier": "1688", "sku": "CORD-1M",
                                   "moq": 50}],
                    "inventory": {"Shenzhen": 90, "UK-01": 0},
                    "compatible_projects": ["charm_lab"],
                    "packing": {"bag": "A", "label": "A04"}},
    "OH-CHARM-SIG": {"name": "Signature 3D charm (personalised)",
                     "kind": "made",
                     "suppliers": [{"supplier": "jlc3dp", "sku": "SLA-RESIN",
                                    "moq": 1}],
                     "inventory": {"Shenzhen": 0, "UK-01": 0},
                     "compatible_projects": ["charm_lab"],
                     "packing": {"bag": "B", "label": "B01"}},
    "OH-BOOKLET-8": {"name": "Instruction booklet, 8pp", "kind": "made",
                     "suppliers": [{"supplier": "shenzhen_print",
                                    "sku": "BOOKLET-8PP", "moq": 1}],
                     "inventory": {"Shenzhen": 0, "UK-01": 0},
                     "compatible_projects": ["charm_lab", "grimoire_maker"],
                     "packing": {"bag": None, "label": "C01"}},
    "OH-JOURNAL-A6": {"name": "Blank A6 kraft journal", "kind": "stocked",
                      "suppliers": [{"supplier": "1688", "sku": "JOURNAL-A6",
                                     "moq": 20}],
                      "inventory": {"Shenzhen": 68, "UK-01": 0},
                      "compatible_projects": ["grimoire_maker",
                                              "tiny_book_studio"],
                      "packing": {"bag": None, "label": "D01"}},
    "OH-CHARM-BRASS": {"name": "Decorative brass charm", "kind": "stocked",
                       "suppliers": [{"supplier": "1688",
                                      "sku": "BRASS-CHARM-10", "moq": 30}],
                       "inventory": {"Shenzhen": 45, "UK-01": 0},
                       "compatible_projects": ["grimoire_maker"],
                       "packing": {"bag": "A", "label": "A05"}},
    "OH-EMBLEM-3D": {"name": "Personalised 3D emblem", "kind": "made",
                     "suppliers": [{"supplier": "jlc3dp", "sku": "SLA-RESIN",
                                    "moq": 1}],
                     "inventory": {"Shenzhen": 0, "UK-01": 0},
                     "compatible_projects": ["grimoire_maker"],
                     "packing": {"bag": "B", "label": "B02"}},
    "OH-SHELL-COTTAGE": {"name": "Cottage shell (personalised exterior)",
                         "kind": "made",
                         "suppliers": [{"supplier": "jlc3dp",
                                        "sku": "SLA-RESIN", "moq": 1}],
                         "inventory": {"Shenzhen": 0, "UK-01": 0},
                         "compatible_projects": ["living_cottage_001"],
                         "packing": {"bag": "B", "label": "B03"}},
    "OH-LED-STRIP": {"name": "Addressable LED strip, USB", "kind": "stocked",
                     "suppliers": [{"supplier": "1688", "sku": "LED-WS2812-1M",
                                    "moq": 20}],
                     "inventory": {"Shenzhen": 150, "UK-01": 0},
                     "compatible_projects": ["living_cottage_001"],
                     "packing": {"bag": "A", "label": "A06"}},
    "OH-VOICE-MOD": {"name": "Voice module (speaker + mic)",
                     "kind": "special",
                     "suppliers": [{"supplier": "m5stack",
                                    "sku": "ATOM-ECHO-CLASS", "moq": 1}],
                     "inventory": {"Shenzhen": 0, "UK-01": 0},
                     "compatible_projects": ["living_cottage_001"],
                     "packing": {"bag": "B", "label": "B04"}},
}

RECIPES = {
    "charm_lab": {"label": "Charm Laboratory", "target_cents": 1999,
                  "target_ccy": "GBP",
                  "components": {"OH-BEAD-001": 10, "OH-CHAIN-001": 1,
                                 "OH-CLASP-001": 2, "OH-CORD-001": 1,
                                 "OH-CHARM-SIG": 1, "OH-BOOKLET-8": 1}},
    "grimoire_maker": {"label": "Grimoire Maker", "target_cents": 3499,
                       "target_ccy": "GBP",
                       "components": {"OH-JOURNAL-A6": 1, "OH-CHARM-BRASS": 3,
                                      "OH-EMBLEM-3D": 1, "OH-BOOKLET-8": 1}},
    "tiny_room_starter": {"label": "Tiny Room Starter", "target_cents": 4999,
                          "target_ccy": "GBP",
                          "components": {"OH-CHARM-SIG": 1, "OH-BOOKLET-8": 1}},
    "living_cottage_001": {"label": "Living Cottage 001 — Jenny's House",
                           "target_cents": 3900, "target_ccy": "GBP",
                           "components": {"OH-SHELL-COTTAGE": 1,
                                          "OH-LED-STRIP": 1,
                                          "OH-VOICE-MOD": 1,
                                          "OH-BOOKLET-8": 1}},
}

# Gift recipes: component-first, product-second. A line is either a
# registry component {component, qty} or one of our live products
# {product: "<studio_line|prodigi_id>", qty} (ornament in a decoration
# set, brick figure as a diorama centrepiece, card as the intro).
GIFT_RECIPES = {
    "little_witch": {
        "label": "The Little Witch", "target_cents": 3000,
        "target_ccy": "GBP",
        "recipient": {"interests": ["cats", "tarot", "journaling"]},
        # Rights gate (canonical vision §4): purchasable stays false until
        # source rights are cleared AND manufacturing is validated.
        "rights": {"status": "review_required",
                   "note": "botanical art sources TBC"},
        "lines": [
            {"component": "OH-JOURNAL-A6", "qty": 1},
            {"component": "OH-CHARM-BRASS", "qty": 3},
            {"component": "OH-BOOKLET-8", "qty": 1},
            {"product": "brick", "qty": 1},
            {"product": "greeting_card", "qty": 1},
        ],
    },
}

# Postage viability: shipping must stay under this share of target
# retail. £30 gift + £8 materials + £22 postage is NOT viable.
POSTAGE_MAX_SHARE = 0.40


def compile_gift(recipe_id: str, warehouse: str = "Shenzhen",
                 ship_cents: int | None = None) -> dict:
    """Resolve every gift line (registry stock or live product price),
    then apply the postage rule. ship_cents unknown → viability pending
    shipment quote (never assumed)."""
    from backend import config as _config
    recipe = GIFT_RECIPES.get(recipe_id)
    if not recipe:
        return {"ok": False, "error": f"unknown gift recipe {recipe_id}"}
    lines, ok, materials = [], True, 0
    for entry in recipe["lines"]:
        qty = int(entry.get("qty") or 1)
        if "component" in entry:
            cid = entry["component"]
            comp = COMPONENTS.get(cid, {})
            have = (comp.get("inventory") or {}).get(warehouse, 0)
            kind = comp.get("kind", "stocked")
            feasible = (have >= qty) if kind == "stocked" else True
            status = ("in_stock" if feasible else f"short ({have}/{qty})") \
                if kind == "stocked" else ("make_to_order"
                                           if kind == "made"
                                           else "special_order")
            lines.append({"kind": "component", "id": cid,
                          "name": comp.get("name", cid), "qty": qty,
                          "status": status, "feasible": feasible})
            ok = ok and feasible
        elif "product" in entry:
            pid = entry["product"]
            spec = (_config.STUDIO_LINES.get(pid)
                    or _config.PRODIGI_PRODUCTS.get(pid) or {})
            live = bool(spec) and spec.get("status", "live") == "live"
            price = int(spec.get("price_cents") or 0) * qty if live else 0
            materials += price
            lines.append({"kind": "product", "id": pid,
                          "name": spec.get("label", pid), "qty": qty,
                          "status": "live" if live else "unavailable",
                          "feasible": live, "price_cents": price})
            ok = ok and live
    verdict, reasons = "viable", []
    if not ok:
        verdict, reasons = "blocked", ["a line is unavailable"]
    if ship_cents is None:
        verdict = "pending-shipment" if verdict == "viable" else verdict
        reasons.append("shipping unquoted — viability needs the parcel quote")
    elif ship_cents > recipe["target_cents"] * POSTAGE_MAX_SHARE:
        verdict = "unviable"
        reasons.append(f"postage {ship_cents}c exceeds "
                       f"{int(POSTAGE_MAX_SHARE * 100)}% of target "
                       f"{recipe['target_cents']}c")
    rights = recipe.get("rights") or {}
    rights_ok = rights.get("status") == "cleared"
    if not rights_ok:
        reasons.append("rights %s — %s" % (
            rights.get("status", "unknown"),
            rights.get("note", "clear sources before sale")))
    return {"ok": True, "recipe": recipe_id, "label": recipe["label"],
            "warehouse": warehouse, "target_cents": recipe["target_cents"],
            "target_ccy": recipe["target_ccy"], "lines": lines,
            "materials_cents": materials, "ship_cents": ship_cents,
            "verdict": verdict, "reasons": reasons,
            "rights": rights or {"status": "unknown"},
            "purchasable": verdict == "viable" and rights_ok}

SCHEMA = """
CREATE TABLE IF NOT EXISTS project_runs (
 run_id TEXT PRIMARY KEY, recipe TEXT NOT NULL, warehouse TEXT NOT NULL,
 created_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS run_items (
 run_id TEXT NOT NULL, component_id TEXT NOT NULL, qty INTEGER NOT NULL,
 status TEXT NOT NULL DEFAULT 'needed',
 PRIMARY KEY (run_id, component_id)
);
"""

STATES = ("needed", "ordered", "received", "verified")


def ensure_schema() -> None:
    from backend import db as _db
    with _db.connect() as c:
        c.executescript(SCHEMA)


def check_recipe(recipe_id: str, warehouse: str = "Shenzhen",
                 qty: int = 1) -> dict:
    """Can this warehouse build N boxes today? Per-component status +
    box quote from published base rates. No network."""
    recipe = RECIPES.get(recipe_id)
    if not recipe:
        return {"ok": False, "error": f"unknown recipe {recipe_id}"}
    lines, ok = [], True
    for cid, per_box in recipe["components"].items():
        comp = COMPONENTS.get(cid, {})
        need = per_box * qty
        have = (comp.get("inventory") or {}).get(warehouse, 0)
        kind = comp.get("kind", "stocked")
        if kind == "stocked" and have >= need:
            status, feasible = "in_stock", True
        elif kind == "stocked":
            status, feasible = f"short ({have}/{need})", False
        elif kind == "made":
            status, feasible = "make_to_order", True
        else:
            status, feasible = "special_order", True
        ok = ok and feasible
        lines.append({"component_id": cid, "name": comp.get("name", cid),
                      "kind": kind, "need": need, "have": have,
                      "status": status, "feasible": feasible})
    quote = {"kitting_cents": KIT_RATES["kitting_cents"] * qty,
             "pick_pack_cents": KIT_RATES["pick_pack_cents"] * qty,
             "ccy": KIT_RATES["ccy"], "note": KIT_RATES["note"]}
    return {"ok": True, "recipe": recipe_id, "label": recipe["label"],
            "warehouse": warehouse, "qty": qty,
            "ready_to_pack": ok, "lines": lines, "box_quote": quote,
            "target_cents": recipe["target_cents"],
            "target_ccy": recipe["target_ccy"]}


def start_run(recipe_id: str, warehouse: str = "Shenzhen",
              qty: int = 1) -> dict:
    """Freeze a run: every line starts at needed. Returns run_id."""
    from backend import db as _db
    if recipe_id not in RECIPES:
        return {"ok": False, "error": f"unknown recipe {recipe_id}"}
    ensure_schema()
    rid = f"run_{int(time.time() * 1000):x}"
    with _db.connect() as c:
        c.execute("INSERT INTO project_runs (run_id,recipe,warehouse,created_at)"
                  " VALUES (?,?,?,?)", (rid, recipe_id, warehouse, time.time()))
        for cid, per_box in RECIPES[recipe_id]["components"].items():
            c.execute("INSERT INTO run_items (run_id,component_id,qty,status)"
                      " VALUES (?,?,?,?)", (rid, cid, per_box * qty, "needed"))
    return {"ok": True, "run_id": rid, "recipe": recipe_id}


def set_item_status(run_id: str, component_id: str, status: str) -> dict:
    """Forward-only: needed → ordered → received → verified. No skipping,
    no going back — the compiler's whole point."""
    if status not in STATES:
        return {"ok": False, "error": f"status must be one of {STATES}"}
    from backend import db as _db
    ensure_schema()
    with _db.connect() as c:
        row = c.execute("SELECT status FROM run_items WHERE run_id=? AND component_id=?",
                        (run_id, component_id)).fetchone()
        if not row:
            return {"ok": False, "error": "line not in run"}
        cur = STATES.index(row["status"])
        nxt = STATES.index(status)
        if nxt != cur + 1:
            return {"ok": False, "error": f"must advance one step from {row['status']}"}
        c.execute("UPDATE run_items SET status=? WHERE run_id=? AND component_id=?",
                  (status, run_id, component_id))
    return {"ok": True, "run_id": run_id, "component_id": component_id,
            "status": status}


def run_status(run_id: str) -> dict:
    """Eligible to pack only when every line is verified."""
    from backend import db as _db
    ensure_schema()
    with _db.connect() as c:
        run = c.execute("SELECT * FROM project_runs WHERE run_id=?",
                        (run_id,)).fetchone()
        if not run:
            return {"ok": False, "error": "unknown run"}
        items = [dict(r) for r in c.execute(
            "SELECT * FROM run_items WHERE run_id=?", (run_id,)).fetchall()]
    eligible = bool(items) and all(i["status"] == "verified" for i in items)
    return {"ok": True, "run_id": run_id, "recipe": run["recipe"],
            "eligible_to_pack": eligible, "items": items}
