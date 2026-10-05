#!/usr/bin/env python3
"""Factory register: canonical product format for the Christmas 20.

    python3 scripts/factory/register.py

Writes data/3dprint/_ingest/factory_registry.json — one canonical entry per
planned listing. Canonical product format v1 (every field has a purpose):

  id / label / blurb            storefront + Etsy/Shopify copy
  price_cents / currency        list price (inc. personalisation)
  material PLA|PETG             farm material flag (thesis: PLA rigid detail,
                                PETG flex/clips/pegs/connectors)
  colors_max                    always <= 4 (MAKR3D review threshold)
  dims_mm [x,y,z]               measured off the base master (measure.py)
  weight_g + weight_basis       measured 100%-infill upper bound, or "master"
                                (re-measure at master time); farm quotes real
  personalization               method: emboss|relief|photo_print|face_swap,
                                zone: named face/area, max_chars
  supplier / fulfilment         makr3d / print_farm|digital
  recipes                       render + production_3mf ids (exist|todo)
  base / refs                   master file + reference files on disk
  status                        live|ready|convert|missing
  theme / occasion              shop section (stocking|game_night|gamer|christmas)
  sample                        have|needed (thesis rule: sample every base)

DRAFT ONLY. Nothing touches backend/config.py until a human reviews this
file and runs the activation.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
INGEST = ROOT / "data" / "3dprint" / "_ingest"

C = "GBP"

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
    "mx_keycap": {"dims_mm": [18.0, 18.0, 12.0], "weight_g": 2.9},
    "slab_stand": {"dims_mm": [70.0, 32.4, 42.7], "weight_g": 22.6},
    "rummy_rack": {"dims_mm": [200.0, 58.0, 40.0], "weight_g": 134.9},
    "straw_ring": {"dims_mm": [34.0, 24.0, 4.0], "weight_g": 1.6},
    "mtg-deck-box-bottom": {"dims_mm": [75.0, 75.0, 69.0], "weight_g": 68.0},
}

LINES = [
    dict(id="clog_charm", label="Personalised Clog Shoe Charm",
         blurb="Name/pet/face/hobby on a Jibbitz-style post. Tiny, instant gift.",
         price_cents=799, currency=C, material="PETG", colors_max=4,
         measured="heart-croc-jibbitz",
         hardware="printed pin stem (Jibbitz-style)", fits="Crocs classic / most clog holes",
         personalization={"method": "relief", "zone": "top_face", "max_chars": 10},
         supplier="makr3d", fulfilment="print_farm",
         recipes={"render": "todo", "production_3mf": "todo"},
         base="", refs=["croc-jibbit-base", "heart-croc-jibbitz", "crocs-spike-jibbitz"],
         status="ready", theme="stocking", occasion="christmas", sample="needed"),
    dict(id="bag_charm", label="Personalised Bag Charm",
         blurb="Pet/person/motif charm for bags and zips.",
         price_cents=999, currency=C, material="PLA", colors_max=4,
         measured="heart-croc-jibbitz",
         hardware="printed loop + split-ring seat", fits="bags, zips, keyrings",
         personalization={"method": "relief", "zone": "front_face", "max_chars": 10},
         supplier="makr3d", fulfilment="print_farm",
         recipes={"render": "todo", "production_3mf": "todo"},
         base="", refs=["heart-croc-jibbitz"], status="ready",
         theme="stocking", occasion="christmas", sample="needed"),
    dict(id="keychain", label="Custom Pet Keychain",
         blurb="Same design, smaller. Printed ring, never metal.",
         price_cents=999, currency=C, material="PLA", colors_max=4,
         measured=None, dims_mm=[60, 40, 15], weight_g=None, weight_basis="subject mesh at 60mm",
         hardware="printed loop + printed ring", fits="keys, bags",
         personalization={"method": "face_swap", "zone": "full_mesh", "max_chars": 0},
         supplier="makr3d", fulfilment="print_farm",
         recipes={"render": "live", "production_3mf": "todo"},
         base="chibi-figure-hook.glb", refs=[], status="live",
         theme="stocking", occasion="christmas", sample="have"),
    dict(id="brick_keychain", label="Custom Brick/Person Keychain",
         blurb="Brick-style minifig keychain from your photo.",
         price_cents=999, currency=C, material="PLA", colors_max=4,
         measured=None, dims_mm=[60, 40, 20], weight_g=None, weight_basis="brick mesh at 60mm",
         hardware="printed loop + printed ring", fits="keys, bags",
         personalization={"method": "face_swap", "zone": "full_mesh", "max_chars": 0},
         supplier="makr3d", fulfilment="print_farm",
         recipes={"render": "live", "production_3mf": "todo"},
         base="brick-figure.glb", refs=[], status="live",
         theme="stocking", occasion="christmas", sample="have"),
    dict(id="ornament", label="Custom 3D Christmas Ornament",
         blurb="Tree hanger. Loop is part of the print, never metal.",
         price_cents=1499, currency=C, material="PLA", colors_max=4,
         measured=None, dims_mm=[80, 60, 30], weight_g=None, weight_basis="subject mesh at 80mm",
         hardware="printed loop", fits="standard tree branches",
         personalization={"method": "face_swap", "zone": "full_mesh", "max_chars": 0},
         supplier="makr3d", fulfilment="print_farm",
         recipes={"render": "live", "production_3mf": "todo"},
         base="chibi-figure-hook.glb", refs=[], status="live",
         theme="christmas", occasion="christmas", sample="have"),
    dict(id="keycap", label="Personalised Cherry-MX Artisan Keycap",
         blurb="Standard MX stem, infinite custom top. Gamer stocking filler.",
         price_cents=1299, currency=C, material="PLA", colors_max=4,
         measured="mx_keycap",
         hardware="none (MX cruciform socket)", fits="Cherry-MX stems",
         personalization={"method": "relief", "zone": "cap_top", "max_chars": 6},
         supplier="makr3d", fulfilment="print_farm",
         recipes={"render": "todo", "production_3mf": "todo"},
         base="masters/mx_keycap.stl", refs=["skull-keycaps (stem ref only)"],
         status="ready", theme="gamer", occasion="christmas", sample="needed"),
    dict(id="shoelace_charm", label="Personalised Shoelace Charm Pair",
         blurb="Clog-charm engine reused for trainers. Pet/name/initial/hobby.",
         price_cents=999, currency=C, material="PETG", colors_max=4,
         measured="shoe-lace-tag",
         hardware="lace-loop interface", fits="standard trainer laces",
         personalization={"method": "relief", "zone": "top_face", "max_chars": 8},
         supplier="makr3d", fulfilment="print_farm",
         recipes={"render": "todo", "production_3mf": "todo"},
         base="", refs=["shoelace-tag-charms (4 STLs)"], status="ready",
         theme="stocking", occasion="christmas", sample="needed"),
    dict(id="book_holder", label="Personalised Book Thumb Page Holder",
         blurb="26mm thumb ring + paddle. ~3g print, BookTok audience.",
         price_cents=799, currency=C, material="PLA", colors_max=4,
         measured="book_holder",
         hardware="none", fits="thumb ID 26mm",
         personalization={"method": "emboss", "zone": "paddle_face", "max_chars": 12},
         supplier="makr3d", fulfilment="print_farm",
         recipes={"render": "todo", "production_3mf": "todo"},
         base="masters/book_holder.stl", refs=[], status="ready",
         theme="stocking", occasion="christmas", sample="needed"),
    dict(id="golf_marker", label="Personalised Golf Ball Marker",
         blurb="Names, initials, pets, jokes, club motif. Evergreen gift.",
         price_cents=999, currency=C, material="PLA", colors_max=4,
         measured="marker-template",
         hardware="none (flat marker)", fits="hat-clip / pocket",
         personalization={"method": "relief", "zone": "top_face", "max_chars": 10},
         supplier="makr3d", fulfilment="print_farm",
         recipes={"render": "todo", "production_3mf": "todo"},
         base="", refs=["golf-golf-ball-marker-assorted/converted (13 STLs)", "golf-tees (9 STLs)"],
         status="ready", theme="stocking", occasion="christmas", sample="needed"),
    dict(id="straw_charm", label="Personalised Tumbler Straw Charm",
         blurb="ID ring + topper pad. Charm format, no food-contact claims.",
         price_cents=799, currency=C, material="PETG", colors_max=4,
         measured="straw_ring",
         hardware="none", fits="~10mm straws (ring ID 10.5)",
         personalization={"method": "relief", "zone": "topper_pad", "max_chars": 8},
         supplier="makr3d", fulfilment="print_farm",
         recipes={"render": "todo", "production_3mf": "todo"},
         base="masters/straw_ring.stl", refs=["bear-straw-topper (bore ref)"],
         status="ready", theme="stocking", occasion="christmas", sample="needed"),
    dict(id="controller_stand", label="Personalised Controller Stand",
         blurb="Gamertag embossed. Broad gamer gift, obvious on a desk.",
         price_cents=1999, currency=C, material="PLA", colors_max=4,
         measured=None, dims_mm=[124.5, 67.6, 56.9], weight_g=286.9,
         weight_basis="ref stand.stl at 100% — COST RISK, slim or re-quote",
         hardware="none", fits="Xbox/PS5 pads (per variant)",
         personalization={"method": "emboss", "zone": "fascia", "max_chars": 14},
         supplier="makr3d", fulfilment="print_farm",
         recipes={"render": "todo", "production_3mf": "todo"},
         base="", refs=["minimalistic-xbox-controller-stand/stand.stl (HEAVY: slim before listing)"],
         status="ready", theme="gamer", occasion="christmas", sample="needed"),
    dict(id="train_station", label="Mexican Train Family Station",
         blurb="THE PRIOR EXPRESS + functional hub. Niche gift differentiator.",
         price_cents=1999, currency=C, material="PLA", colors_max=4,
         measured="train-hub-half",
         hardware="none", fits="double-9/12 dominoes (verify tile size)",
         personalization={"method": "emboss", "zone": "hub_face", "max_chars": 18},
         supplier="makr3d", fulfilment="print_farm",
         recipes={"render": "todo", "production_3mf": "todo"},
         base="", refs=["Train Hub Half.stl (16g — use, NOT the 220mm/301g tray)"],
         status="ready", theme="game_night", occasion="christmas", sample="needed"),
    dict(id="domino_racks", label="Personalised Mexican Train Domino Racks",
         blurb="MUM / DAD / TOM / SARAH. Family set, upsell to the station.",
         price_cents=2499, currency=C, material="PLA", colors_max=4,
         measured=None, dims_mm=None, weight_g=None, weight_basis="derive from tile dims",
         hardware="none", fits="double-9/12 dominoes (verify tile size)",
         personalization={"method": "emboss", "zone": "rack_fascia", "max_chars": 10},
         supplier="makr3d", fulfilment="print_farm",
         recipes={"render": "todo", "production_3mf": "todo"},
         base="", refs=["mexican-domino-train-hub-and-case (case STLs)"], status="ready",
         theme="game_night", occasion="christmas", sample="needed"),
    dict(id="line_reader", label="Personalised Mahjong Line Reader",
         blurb="Exploding category, tiny print, huge name surface.",
         price_cents=999, currency=C, material="PLA", colors_max=4,
         measured="line_reader",
         hardware="none", fits="standard mahjong tiles (verify channel)",
         personalization={"method": "emboss", "zone": "plate_face", "max_chars": 12},
         supplier="makr3d", fulfilment="print_farm",
         recipes={"render": "todo", "production_3mf": "todo"},
         base="masters/line_reader.stl", refs=[], status="ready",
         theme="game_night", occasion="christmas", sample="needed"),
    dict(id="wind_indicator", label="Personalised Mahjong Wind Indicator",
         blurb="Tiny quirky add-on. No source geometry yet.",
         price_cents=1299, currency=C, material="PLA", colors_max=4,
         measured=None, dims_mm=None, weight_g=None, weight_basis="author at master time (~13g target)",
         hardware="snap-fit wheel (2 parts)", fits="tabletop",
         personalization={"method": "emboss", "zone": "base_ring", "max_chars": 8},
         supplier="makr3d", fulfilment="print_farm",
         recipes={"render": "todo", "production_3mf": "todo"},
         base="", refs=[], status="missing", theme="game_night",
         occasion="christmas", sample="needed"),
    dict(id="rummy_rack", label="Personalised 4-Tier Rummy Tile Rack",
         blurb="Simple stepped geometry, big name fascia. Family packs later.",
         price_cents=1499, currency=C, material="PLA", colors_max=4,
         measured="rummy_rack",
         hardware="none", fits="rummy tiles (verify tile size)",
         personalization={"method": "emboss", "zone": "back_fascia", "max_chars": 12},
         supplier="makr3d", fulfilment="print_farm",
         recipes={"render": "todo", "production_3mf": "todo"},
         base="masters/rummy_rack.stl (134.9g at 100% — check infill cost)",
         refs=[], status="ready", theme="game_night", occasion="christmas", sample="needed"),
    dict(id="card_rack", label="Personalised Playing-Card Hand Rack",
         blurb="Canasta, Bridge, Hand & Foot, kids, older players.",
         price_cents=1299, currency=C, material="PLA", colors_max=4,
         measured=None, dims_mm=[70.0, 32.4, 42.7], weight_g=22.6,
         weight_basis="own slab_stand master; card-riser ref is 159mm/160g — too big, use ours",
         hardware="none", fits="poker 63.5x88.9 / bridge 57x88.8 (verify groove)",
         personalization={"method": "emboss", "zone": "front_fascia", "max_chars": 12},
         supplier="makr3d", fulfilment="print_farm",
         recipes={"render": "todo", "production_3mf": "todo"},
         base="masters/slab_stand.stl", refs=["card-riser converted (dims ref only)"],
         status="ready", theme="game_night", occasion="christmas", sample="needed"),
    dict(id="tcg_stand", label='Personalised TCG "Grail" Stand',
         blurb="Collector name/deck/gamertag. No character IP needed.",
         price_cents=1499, currency=C, material="PLA", colors_max=4,
         measured="slab_stand",
         hardware="none", fits="graded slabs ~85x55x7 (verify groove 8mm)",
         personalization={"method": "emboss", "zone": "base_front", "max_chars": 14},
         supplier="makr3d", fulfilment="print_farm",
         recipes={"render": "todo", "production_3mf": "todo"},
         base="masters/slab_stand.stl", refs=["mtg-card-deck-box (dims ref)"],
         status="ready", theme="gamer", occasion="christmas", sample="needed"),
    dict(id="cribbage_pegs", label="Personalised Cribbage Peg Pair",
         blurb="Standard 1/8in shaft, sculptural topper. Names/pets/people.",
         price_cents=1299, currency=C, material="PETG", colors_max=4,
         measured="Cribbage_peg_5",
         hardware="none", fits='1/8" cribbage holes (shaft ~3.0-3.2mm)',
         personalization={"method": "relief", "zone": "topper", "max_chars": 0},
         supplier="makr3d", fulfilment="print_farm",
         recipes={"render": "todo", "production_3mf": "todo"},
         base="", refs=["Cribbage_peg_5.stl", "wearables peg_classic/ball (own masters)"],
         status="ready", theme="stocking", occasion="christmas", sample="needed"),
    dict(id="dart_stand", label="Personalised Dart Stand",
         blurb="DAD'S DARTS, 180 CLUB. Obvious male/family gift, one-shot print.",
         price_cents=1999, currency=C, material="PLA", colors_max=4,
         measured="dart_stand",
         hardware="none", fits="standard brass/tungsten darts (verify bore)",
         personalization={"method": "emboss", "zone": "base_front", "max_chars": 14},
         supplier="makr3d", fulfilment="print_farm",
         recipes={"render": "todo", "production_3mf": "todo"},
         base="", refs=["dart_stand/dart_stand.stl (7.5g)"],
         status="ready", theme="game_night", occasion="christmas", sample="needed"),
]


def main() -> int:
    out = {}
    for e in LINES:
        e = dict(e)
        key = e.pop("measured")
        if key and key in MEASURED:
            m = MEASURED[key]
            e["dims_mm"] = m["dims_mm"]
            e["weight_g"] = m["weight_g"]
            e["weight_basis"] = f"measured {key} at 100% infill (upper bound)"
        out[e["id"]] = e
    dest = INGEST / "factory_registry.json"
    dest.write_text(json.dumps(out, indent=2))
    counts: dict[str, int] = {}
    for v in out.values():
        counts[v["status"]] = counts.get(v["status"], 0) + 1
    print(f"20 lines -> {dest.relative_to(ROOT)} {json.dumps(counts)}")
    print("cost flags:",
          "controller_stand HEAVY (287g ref) | train tray 301g REJECTED for hub-half 16g | "
          "card-riser 160g REJECTED for own 22g slab_stand | rummy 135g check infill")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
