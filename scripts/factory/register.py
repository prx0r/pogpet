#!/usr/bin/env python3
"""Factory register: emit the draft STUDIO_LINES extension for the Christmas 20.

    python3 scripts/factory/register.py

Reads data/3dprint/_ingest/manifest.json + validate.json and writes
data/3dprint/_ingest/factory_registry.json — one entry per planned listing:

  {line_id: {label, price_cents, material(PLA|PETG), base(master .stl),
             ref(reference files in data/3dprint), status: live|ready|convert|missing,
             sample: needed|have, notes}}

DRAFT ONLY. Nothing touches backend/config.py until a human reviews this
file and runs the activation. Status meanings:
  live     already in STUDIO_LINES today
  ready    base STL validated PASS/FIXABLE, personalise proven, needs stills+entry
  convert  source needs normalize_3mf output checked or a CAD step (STEP)
  missing  no printable source yet (gcode-only or absent) — author or download
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
INGEST = ROOT / "data" / "3dprint" / "_ingest"

# line: label, price_cents, material, base master or '', refs, status, sample
LINES = [
    ("clog_charm", "Personalised Clog Shoe Charm", 799, "PETG",
     "", ["croc-jibbit-base/croc-jibbit-base.stl", "heart-croc-jibbitz/heart-croc-jibbitz.stl",
           "crocs-spike-jibbitz/*", "crocs-f1-rear-wing/crocs rear wing.stl"], "ready", "needed"),
    ("bag_charm", "Personalised Bag Charm", 999, "PLA",
     "", ["heart-croc-jibbitz/heart-croc-jibbitz.stl"], "ready", "needed"),
    ("keychain", "Custom Pet Keychain", 999, "PLA", "", [], "live", "have"),
    ("brick_keychain", "Custom Brick/Person Keychain", 999, "PLA", "", [], "live", "have"),
    ("ornament", "Custom 3D Christmas Ornament", 1499, "PLA", "", [], "live", "have"),
    ("keycap", "Personalised Cherry-MX Artisan Keycap", 1299, "PLA",
     "masters/mx_keycap.stl", ["skull-keycaps/skull*.stl (stem ref only)"], "ready", "needed"),
    ("shoelace_charm", "Personalised Shoelace Charm Pair", 999, "PETG",
     "", ["shoelace-tag-charms/*.stl"], "ready", "needed"),
    ("book_holder", "Personalised Book Thumb Page Holder", 799, "PLA",
     "masters/book_holder.stl", [], "ready", "needed"),
    ("golf_marker", "Personalised Golf Ball Marker", 999, "PLA",
     "", ["golf-golf-ball-marker-assorted/converted/*.stl", "golf-tees/*.stl",
           "golf-ball-holder/converted/*.stl"], "ready", "needed"),
    ("straw_charm", "Personalised Tumbler Straw Charm", 799, "PETG",
     "masters/straw_ring.stl", ["bear-straw-topper/bear-straw-topper.stl (bore ref)"], "ready", "needed"),
    ("controller_stand", "Personalised Controller Stand", 1999, "PLA",
     "", ["minimalistic-xbox-controller-stand/stand.stl",
           "dual-ps5-controller-stand-no-supports/*.stl",
           "playstation-ps5-dualsense-minimalist-controller-stand/*.stl"], "ready", "needed"),
    ("train_station", "Mexican Train Family Station", 1999, "PLA",
     "", ["mexican-train-tray-domino-tray/Mexican Train Holder.stl",
           "mexican-domino-train-hub-and-case/*.stl", "Mexican Train.stl"], "ready", "needed"),
    ("domino_racks", "Personalised Mexican Train Domino Racks", 2499, "PLA",
     "", ["mexican-domino-train-hub-and-case/*.stl"], "ready", "needed"),
    ("line_reader", "Personalised Mahjong Line Reader", 999, "PLA",
     "masters/line_reader.stl", ["mahjong.stl (6KB, verify content)"], "ready", "needed"),
    ("wind_indicator", "Personalised Mahjong Wind Indicator", 1299, "PLA",
     "", [], "missing", "needed"),
    ("rummy_rack", "Personalised 4-Tier Rummy Tile Rack", 1499, "PLA",
     "masters/rummy_rack.stl", [], "ready", "needed"),
    ("card_rack", "Personalised Playing-Card Hand Rack", 1299, "PLA",
     "", ["playing-card-holder-riser-3-tiers/converted/*.stl"], "ready", "needed"),
    ("tcg_stand", 'Personalised TCG "Grail" Stand', 1499, "PLA",
     "masters/slab_stand.stl", ["mtg-card-deck-box/*.stl (dims ref)"], "ready", "needed"),
    ("cribbage_pegs", "Personalised Cribbage Peg Pair", 1299, "PETG",
     "", ["Cribbage_peg_5.stl", "wearables peg_classic/ball (own masters)"], "ready", "needed"),
    ("dart_stand", "Personalised Dart Stand", 1999, "PLA",
     "", ["dart-stand-model_files/*.stl", "drum-magazine-darts-holder/*.stl",
           "simple-darts-stand/*.stl"], "ready", "needed"),
]


def main() -> int:
    valid = {}
    try:
        valid = {r["file"]: r["verdict"]
                 for r in json.loads((INGEST / "validate.json").read_text())}
    except FileNotFoundError:
        pass
    out = {}
    for lid, label, price, mat, base, refs, status, sample in LINES:
        ref_health = {}
        for r in refs:
            hits = [f for f in valid if f.startswith(r.split("*")[0].split("/")[0][:12])]
            if hits:
                ref_health[r] = f"{len(hits)} files"
        out[lid] = {
            "label": label, "price_cents": price, "material": mat,
            "base": base, "refs": refs, "status": status,
            "sample": sample, "ref_health": ref_health,
        }
    dest = INGEST / "factory_registry.json"
    dest.write_text(json.dumps(out, indent=2))
    counts: dict[str, int] = {}
    for v in out.values():
        counts[v["status"]] = counts.get(v["status"], 0) + 1
    print(f"20 lines -> {dest.relative_to(ROOT)} {json.dumps(counts)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
