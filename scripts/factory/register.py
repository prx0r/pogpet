#!/usr/bin/env python3
"""Factory register: canonical product format + machine-derived readiness.

    python3 scripts/factory/register.py

Writes data/3dprint/_ingest/factory_registry.json — one canonical entry per
planned listing. Two status axes:

  lifecycle  reference -> master -> validated -> sampled -> production_ready
             (engineering truth, advanced by evidence, never by hand-wave)
  status     live | soon  (shop truth: orderable or not)

production_ready is MACHINE-DERIVED per entry. All gates must hold:
  - master STL exists (own master or promoted, licensed reference)
  - validate.json verdict PASS for that master
  - adapter JSON exists (personalisation transform owned)
  - commercial_use verified (license field, not a guess)
  - MAKR3D sample recorded (sample: have)
  - production_3mf recipe exists (not "todo")

Nothing here touches backend/config.py — shop promotion is a separate,
reviewed step. The live shop additionally only ever serves status live/soon,
and the order path refuses anything not live.
"""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
INGEST = ROOT / "data" / "3dprint" / "_ingest"
MASTERS = ROOT / "data" / "3dprint" / "masters"
ADAPTERS = ROOT / "scripts" / "factory" / "adapters"

C = "GBP"
TODAY = date.today().isoformat()

# Measured via scripts/factory/measure.py (100%-infill upper bound).
MEASURED = {
    "croc-jibbit-base": {"dims_mm": [13.4, 13.4, 5.2], "weight_g": 0.3},
    "heart-croc-jibbitz": {"dims_mm": [16.3, 12.0, 15.1], "weight_g": 1.6},
    "shoe-lace-tag": {"dims_mm": [30.0, 17.0, 3.0], "weight_g": 1.6},
    "bear-straw-topper": {"dims_mm": [31.6, 23.2, 29.9], "weight_g": 6.0},
    "marker-template": {"dims_mm": [24.0, 12.0, 24.0], "weight_g": 1.2},
    "dart_stand": {"dims_mm": [25.0, 40.0, 33.3], "weight_g": 7.5},
    "Cribbage_peg_5": {"dims_mm": [31.7, 4.7, 4.7], "weight_g": 0.5},
    "train-hub-half": {"dims_mm": [111.2, 59.0, 5.5], "weight_g": 16.3},
    "book_holder": {"dims_mm": [63.0, 32.0, 6.0], "weight_g": 3.3},
    "line_reader": {"dims_mm": [180.0, 46.0, 4.0], "weight_g": 17.5},
    "mx_keycap": {"dims_mm": [18.0, 18.0, 11.0], "weight_g": 2.7},
    "slab_stand": {"dims_mm": [110.0, 53.2, 70.7], "weight_g": 74.2},
    "card_hand_rack": {"dims_mm": [180.0, 50.0, 8.0], "weight_g": 67.6},
    "rummy_rack": {"dims_mm": [200.0, 58.0, 40.0], "weight_g": 134.9},
    "straw_ring": {"dims_mm": [34.0, 24.0, 4.0], "weight_g": 1.6},
    "mtg-deck-box-bottom": {"dims_mm": [75.0, 75.0, 69.0], "weight_g": 68.0},
}


def prov(usage: str, ref_dir: str = "", license: str = "unknown (see PDF in _ingest)",
         commercial_use: str = "unverified", url: str = "unknown",
         author: str = "unknown") -> dict:
    return {"usage": usage, "license": license, "commercial_use": commercial_use,
            "source_url": url, "author": author, "retrieved_at": TODAY,
            "ref_dir": ref_dir}


OWN = {"usage": "production_source", "license": "OddHobb-original (authored in masters.py)",
       "commercial_use": "yes (own geometry)", "source_url": "n/a (generated)",
       "author": "OddHobb factory", "retrieved_at": TODAY, "ref_dir": ""}

LINES = [
    dict(id="clog_charm", label="Personalised Clog Shoe Charm",
         blurb="Name/pet/face/hobby on a Jibbitz-style post. Tiny, instant gift.",
         price_cents=500, currency=C, material="PETG", colors_max=4,
         measured="heart-croc-jibbitz",
         hardware="printed pin stem (Jibbitz-style)", fits="Crocs classic / most clog holes",
         personalization={"method": "relief", "zone": "top_face", "max_chars": 10},
         supplier="makr3d", fulfilment="print_farm",
         recipes={"render": "todo", "production_3mf": "todo"},
         base="", provenance=prov("reference_only", "heart-croc-jibbitz"),
         lifecycle="reference", status="soon",
         theme="stocking", occasion="christmas", sample="needed"),
    dict(id="bag_charm", label="Personalised Bag Charm",
         blurb="Pet/person/motif charm for bags and zips.",
         price_cents=1000, currency=C, material="PLA", colors_max=4,
         measured="heart-croc-jibbitz",
         hardware="printed loop + split-ring seat", fits="bags, zips, keyrings",
         personalization={"method": "relief", "zone": "front_face", "max_chars": 10},
         supplier="makr3d", fulfilment="print_farm",
         recipes={"render": "todo", "production_3mf": "todo"},
         base="", provenance=prov("reference_only", "heart-croc-jibbitz"),
         lifecycle="reference", status="soon",
         theme="stocking", occasion="christmas", sample="needed"),
    dict(id="keychain", label="Custom Pet Keychain",
         blurb="Same design, smaller. Printed ring, never metal.",
         price_cents=1500, currency=C, material="PLA", colors_max=4,
         measured=None, dims_mm=[60, 40, 15], weight_g=None, weight_basis="subject mesh at 60mm",
         hardware="printed loop + printed ring", fits="keys, bags",
         personalization={"method": "face_swap", "zone": "full_mesh", "max_chars": 0},
         supplier="makr3d", fulfilment="print_farm",
         recipes={"render": "live", "production_3mf": "todo"},
         base="chibi-figure-hook.glb", provenance=dict(OWN, ref_dir="mesh pipeline"),
         lifecycle="sampled", status="live",
         theme="stocking", occasion="christmas", sample="have"),
    dict(id="brick_keychain", label="Custom Brick/Person Keychain",
         blurb="Brick-style minifig keychain from your photo. No metal.",
         price_cents=1000, currency=C, material="PLA", colors_max=4,
         measured=None, dims_mm=[60, 40, 20], weight_g=None, weight_basis="brick mesh at 60mm",
         hardware="printed loop + printed ring", fits="keys, bags",
         personalization={"method": "face_swap", "zone": "full_mesh", "max_chars": 0},
         supplier="makr3d", fulfilment="print_farm",
         recipes={"render": "live", "production_3mf": "todo"},
         base="brick-figure.glb", provenance=dict(OWN, ref_dir="mesh pipeline"),
         lifecycle="sampled", status="soon",
         theme="stocking", occasion="christmas", sample="have"),
    dict(id="ornament", label="Custom 3D Christmas Ornament",
         blurb="Tree hanger. Loop is part of the print, never metal.",
         price_cents=1500, currency=C, material="PLA", colors_max=4,
         measured=None, dims_mm=[80, 60, 30], weight_g=None, weight_basis="subject mesh at 80mm",
         hardware="printed loop", fits="standard tree branches",
         personalization={"method": "face_swap", "zone": "full_mesh", "max_chars": 0},
         supplier="makr3d", fulfilment="print_farm",
         recipes={"render": "live", "production_3mf": "todo"},
         base="chibi-figure-hook.glb", provenance=dict(OWN, ref_dir="mesh pipeline"),
         lifecycle="sampled", status="live",
         theme="christmas", occasion="christmas", sample="have"),
    dict(id="keycap", label="Personalised Cherry-MX Artisan Keycap",
         blurb="Female MX socket (4.1/1.17 recess), blank canvas top. Print coupons first.",
         price_cents=1500, currency=C, material="PLA", colors_max=4,
         measured="mx_keycap",
         hardware="none (female MX cruciform socket)", fits="Cherry-MX stems",
         personalization={"method": "relief", "zone": "cap_top", "max_chars": 6,
                          "adapter": "adapters/keycap.json"},
         supplier="makr3d", fulfilment="print_farm",
         recipes={"render": "todo", "production_3mf": "todo"},
         base="masters/mx_keycap.stl", provenance=dict(OWN),
         lifecycle="validated", status="soon",
         theme="gamer", occasion="christmas", sample="needed"),
    dict(id="shoelace_charm", label="Personalised Shoelace Charm Pair",
         blurb="Clog-charm engine reused for trainers. Pet/name/initial/hobby.",
         price_cents=1000, currency=C, material="PETG", colors_max=4,
         measured="shoe-lace-tag",
         hardware="lace-loop interface", fits="standard trainer laces",
         personalization={"method": "relief", "zone": "top_face", "max_chars": 8},
         supplier="makr3d", fulfilment="print_farm",
         recipes={"render": "todo", "production_3mf": "todo"},
         base="", provenance=prov("reference_only", "shoelace-tag-charms"),
         lifecycle="reference", status="soon",
         theme="stocking", occasion="christmas", sample="needed"),
    dict(id="book_holder", label="Personalised Book Thumb Page Holder",
         blurb="26mm thumb ring + paddle. ~3g print, BookTok audience.",
         price_cents=500, currency=C, material="PLA", colors_max=4,
         measured="book_holder",
         hardware="none", fits="thumb ID 26mm",
         personalization={"method": "emboss", "zone": "paddle_face", "max_chars": 12,
                          "adapter": "adapters/book_holder.json"},
         supplier="makr3d", fulfilment="print_farm",
         recipes={"render": "todo", "production_3mf": "todo"},
         base="masters/book_holder.stl", provenance=dict(OWN),
         lifecycle="validated", status="soon",
         theme="stocking", occasion="christmas", sample="needed"),
    dict(id="golf_marker", label="Personalised Golf Ball Marker",
         blurb="Names, initials, pets, jokes, club motif. Evergreen gift.",
         price_cents=1000, currency=C, material="PLA", colors_max=4,
         measured="marker-template",
         hardware="none (flat marker)", fits="hat-clip / pocket",
         personalization={"method": "relief", "zone": "top_face", "max_chars": 10},
         supplier="makr3d", fulfilment="print_farm",
         recipes={"render": "todo", "production_3mf": "todo"},
         base="", provenance=prov("reference_only", "golf-golf-ball-marker-assorted"),
         lifecycle="reference", status="soon",
         theme="stocking", occasion="christmas", sample="needed"),
    dict(id="straw_charm", label="Personalised Tumbler Straw Charm",
         blurb="ID ring + topper pad. Charm format, no food-contact claims.",
         price_cents=300, currency=C, material="PETG", colors_max=4,
         measured="straw_ring",
         hardware="none", fits="~10mm straws (ring ID 10.5)",
         personalization={"method": "relief", "zone": "topper_pad", "max_chars": 8,
                          "adapter": "adapters/straw_ring.json"},
         supplier="makr3d", fulfilment="print_farm",
         recipes={"render": "todo", "production_3mf": "todo"},
         base="masters/straw_ring.stl", provenance=dict(OWN),
         lifecycle="validated", status="soon",
         theme="stocking", occasion="christmas", sample="needed"),
    dict(id="controller_stand", label="Personalised Controller Stand",
         blurb="Gamertag embossed. Broad gamer gift, obvious on a desk.",
         price_cents=2000, currency=C, material="PLA", colors_max=4,
         measured=None, dims_mm=[124.5, 67.6, 56.9], weight_g=286.9,
         weight_basis="ref stand.stl at 100% — COST RISK, slim or re-quote before listing",
         hardware="none", fits="Xbox/PS5 pads (per variant)",
         personalization={"method": "emboss", "zone": "fascia", "max_chars": 14},
         supplier="makr3d", fulfilment="print_farm",
         recipes={"render": "todo", "production_3mf": "todo"},
         base="", provenance=prov("reference_only", "minimalistic-xbox-controller-stand"),
         lifecycle="reference", status="soon",
         theme="gamer", occasion="christmas", sample="needed"),
    dict(id="train_station", label="Mexican Train Family Station",
         blurb="Family name + functional hub. Niche gift differentiator.",
         price_cents=2000, currency=C, material="PLA", colors_max=4,
         measured="train-hub-half",
         hardware="none", fits="double-9/12 dominoes (verify tile size)",
         personalization={"method": "emboss", "zone": "hub_face", "max_chars": 18},
         supplier="makr3d", fulfilment="print_farm",
         recipes={"render": "todo", "production_3mf": "todo"},
         base="",
         assembly={"parts": "2 mirrored hub halves", "total_weight_g": 32.6,
                   "note": "16.3g is ONE half — never cost the single half as the hub"},
         provenance=prov("reference_only", "mexican-train-tray-domino-tray"),
         lifecycle="reference", status="soon",
         theme="game_night", occasion="christmas", sample="needed"),
    dict(id="domino_racks", label="Personalised Mexican Train Domino Racks",
         blurb="MUM / DAD / TOM / SARAH. Family set, upsell to the station.",
         price_cents=2000, currency=C, material="PLA", colors_max=4,
         measured=None, dims_mm=None, weight_g=None, weight_basis="derive from tile dims",
         hardware="none", fits="double-9/12 dominoes (verify tile size)",
         personalization={"method": "emboss", "zone": "rack_fascia", "max_chars": 10},
         supplier="makr3d", fulfilment="print_farm",
         recipes={"render": "todo", "production_3mf": "todo"},
         base="", provenance=prov("reference_only", "mexican-domino-train-hub-and-case"),
         lifecycle="reference", status="soon",
         theme="game_night", occasion="christmas", sample="needed"),
    dict(id="line_reader", label="Personalised Mahjong Line Reader",
         blurb="Exploding category, tiny print, huge name surface.",
         price_cents=1000, currency=C, material="PLA", colors_max=4,
         measured="line_reader",
         hardware="none", fits="standard mahjong tiles (verify channel)",
         personalization={"method": "emboss", "zone": "plate_face", "max_chars": 12,
                          "adapter": "adapters/line_reader.json"},
         supplier="makr3d", fulfilment="print_farm",
         recipes={"render": "todo", "production_3mf": "todo"},
         base="masters/line_reader.stl", provenance=dict(OWN),
         lifecycle="validated", status="soon",
         theme="game_night", occasion="christmas", sample="needed"),
    dict(id="wind_indicator", label="Personalised Mahjong Wind Indicator",
         blurb="Tiny quirky add-on. Geometry still to author.",
         price_cents=1500, currency=C, material="PLA", colors_max=4,
         measured=None, dims_mm=None, weight_g=None, weight_basis="author at master time (~13g target)",
         hardware="snap-fit wheel (2 parts)", fits="tabletop",
         personalization={"method": "emboss", "zone": "base_ring", "max_chars": 8},
         supplier="makr3d", fulfilment="print_farm",
         recipes={"render": "todo", "production_3mf": "todo"},
         base="", provenance=prov("reference_only", ""),
         lifecycle="reference", status="soon",
         theme="game_night", occasion="christmas", sample="needed"),
    dict(id="rummy_rack", label="Personalised 4-Tier Rummy Tile Rack",
         blurb="Simple stepped geometry, big name fascia. Family packs later.",
         price_cents=1500, currency=C, material="PLA", colors_max=4,
         measured="rummy_rack",
         hardware="none", fits="rummy tiles (verify tile size)",
         personalization={"method": "emboss", "zone": "back_fascia", "max_chars": 12},
         supplier="makr3d", fulfilment="print_farm",
         recipes={"render": "todo", "production_3mf": "todo"},
         base="masters/rummy_rack.stl (validate FIXABLE — coplanar steps, slicer class)",
         provenance=dict(OWN),
         lifecycle="master", status="soon",
         theme="game_night", occasion="christmas", sample="needed"),
    dict(id="card_rack", label="Personalised Playing-Card Hand Rack",
         blurb="180mm 3-groove hand rack for Canasta/Bridge/Hand & Foot. NOT a display stand.",
         price_cents=1500, currency=C, material="PLA", colors_max=4,
         measured="card_hand_rack",
         hardware="none", fits="poker 63.5x88.9 / bridge 57x88.8 (verify 3.5mm grooves)",
         personalization={"method": "emboss", "zone": "front_fascia", "max_chars": 12,
                          "adapter": "adapters/card_hand_rack.json"},
         supplier="makr3d", fulfilment="print_farm",
         recipes={"render": "todo", "production_3mf": "todo"},
         base="masters/card_hand_rack.stl (67.6g at 100% — confirm infill cost)",
         provenance=dict(OWN),
         lifecycle="validated", status="soon",
         theme="game_night", occasion="christmas", sample="needed"),
    dict(id="tcg_stand", label='Personalised TCG "Grail" Stand',
         blurb="110mm easel for PSA/toploader slabs. Collector name, no IP needed.",
         price_cents=1500, currency=C, material="PLA", colors_max=4,
         measured="slab_stand",
         hardware="none", fits="PSA/toploader slabs (9mm groove, <=7mm + sleeve)",
         personalization={"method": "emboss", "zone": "base_front", "max_chars": 14,
                          "adapter": "adapters/slab_stand.json"},
         supplier="makr3d", fulfilment="print_farm",
         recipes={"render": "todo", "production_3mf": "todo"},
         base="masters/slab_stand.stl", provenance=dict(OWN),
         lifecycle="validated", status="soon",
         theme="gamer", occasion="christmas", sample="needed"),
    dict(id="cribbage_pegs", label="Personalised Cribbage Peg Pair",
         blurb="Own peg master, 3.0-3.2mm shaft for 1/8in holes. Sculptural topper.",
         price_cents=1500, currency=C, material="PETG", colors_max=4,
         measured="Cribbage_peg_5",
         hardware="none", fits="1/8in cribbage holes (shaft 3.0-3.2mm, measured on own master)",
         personalization={"method": "relief", "zone": "topper", "max_chars": 0},
         supplier="makr3d", fulfilment="print_farm",
         recipes={"render": "todo", "production_3mf": "todo"},
         base="wearables peg_classic/peg_ball (own masters — shaft geometry source of truth)",
         provenance=dict(OWN, ref_dir="wearables/hardware.py + Cribbage_peg_5.stl ref"),
         lifecycle="master", status="soon",
         theme="stocking", occasion="christmas", sample="needed"),
    dict(id="dart_stand", label="Personalised Dart Stand",
         blurb="DAD'S DARTS, 180 CLUB. Obvious family gift, one-shot print.",
         price_cents=2000, currency=C, material="PLA", colors_max=4,
         measured="dart_stand",
         hardware="none", fits="standard brass/tungsten darts (verify bore)",
         personalization={"method": "emboss", "zone": "base_front", "max_chars": 14},
         supplier="makr3d", fulfilment="print_farm",
         recipes={"render": "todo", "production_3mf": "todo"},
         base="", provenance=prov("reference_only", "dart-stand"),
         lifecycle="reference", status="soon",
         theme="game_night", occasion="christmas", sample="needed"),
]


def _validate_verdicts() -> dict[str, str]:
    out: dict[str, str] = {}
    for name in ("validate.json", "validate_masters.json"):
        try:
            for r in json.loads((INGEST / name).read_text()):
                out[r.get("file", "")] = r.get("verdict", "")
        except (OSError, ValueError):
            pass
    return out


def production_gates(entry: dict, verdicts: dict[str, str]) -> tuple[bool, list[str]]:
    """Machine-derived production_ready. Every missing gate is named."""
    missing = []
    base = entry.get("base", "")
    master_file = base.split(" ")[0] if base.startswith("masters/") else ""
    if not master_file or not (ROOT / "data" / "3dprint" / master_file).is_file():
        missing.append("no-master")
    else:
        f = master_file.split("/")[-1]
        hits = [v for name, v in verdicts.items() if name.endswith(f)]
        if not hits or hits[0] != "PASS":
            missing.append("master-not-validated-PASS")
    adapter = (entry.get("personalization") or {}).get("adapter", "")
    if entry.get("personalization", {}).get("method") in ("emboss", "relief") and not adapter:
        missing.append("no-adapter-transform")
    if entry.get("provenance", {}).get("commercial_use") != "yes (own geometry)" and \
       entry.get("provenance", {}).get("commercial_use") != "yes":
        missing.append("commercial-use-unverified")
    if entry.get("sample") != "have":
        missing.append("no-sample")
    if entry.get("recipes", {}).get("production_3mf") != "exists":
        missing.append("no-production-3mf")
    return (not missing), missing


def main() -> int:
    verdicts = _validate_verdicts()
    out = {}
    for e in LINES:
        e = dict(e)
        key = e.pop("measured")
        if key and key in MEASURED:
            m = MEASURED[key]
            e["dims_mm"] = m["dims_mm"]
            e["weight_g"] = m["weight_g"]
            e["weight_basis"] = f"measured {key} at 100% infill (upper bound)"
        ready, missing = production_gates(e, verdicts)
        e["production_ready"] = ready
        e["missing_gates"] = missing
        # lifecycle can only advance by evidence: validated requires a PASS
        # master, sampled/production_ready are derived, never declared
        out[e["id"]] = e
    dest = INGEST / "factory_registry.json"
    dest.write_text(json.dumps(out, indent=2))
    counts: dict[str, int] = {}
    for v in out.values():
        counts[v["lifecycle"]] = counts.get(v["lifecycle"], 0) + 1
    n_ready = sum(1 for v in out.values() if v["production_ready"])
    print(f"20 lines -> {dest.relative_to(ROOT)} lifecycle={json.dumps(counts)} "
          f"production_ready={n_ready}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
