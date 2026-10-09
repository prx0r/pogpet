# OddHobb supplier catalog — every lane, normalized with prices

Saved 2026-10-09. Purpose: one page an agent can design against. Pick a
product idea → check material/process/dims against a lane → read the price
basis → know exactly how to get a live number. Machine twin:
`backend/supplier_catalog.json` (same data, generated from `suppliers.py` +
`config.py` + the JLC/Xometry docs).

Pricing truth, read first: only three lanes have real numbers (MAKR3D bands
from file quotes, Printie/3dfarm per-cm³ roughs, JLC list floors, one live
Prodigi SKU). Everything else is QUOTE-grade by design — the system refuses
to fake numbers (`suppliers.estimate()` returns `est_cents: None`). A QUOTE
lane lists the exact path to a live price, not a guess.

Raw upstream docs: `~/supplier-docs/` (makr3d ×3, treatstock ×2, sculpteo,
craftcloud-compare, xometry ×9 as of today).

## The 16 lanes

| # | Supplier | Lane | Home → serves | Materials / processes | Order path | Price basis (grade) | Dispatch | Min |
|---|---|---|---|---|---|---|---|---|
| 1 | MAKR3D (Yorkshire3D farm) | 3D default | UK → UK/worldwide | PLA/PETG, 4 colours, 256³mm | api (Shopify/Etsy/CSV/manual) | weight bands ≤10g £1.29 / ≤40g £2.50, else ~12p PLA / 16p PETG per cm³, £1 min, ex-VAT (BAND, verify) | 1–2d | 1 |
| 2 | Printie | 3D second UK | UK → UK/worldwide | PLA/PETG (+TPU/ASA profiles), 4 colours, 256³mm | manual (browser quote tool) | ~14p PLA / 18p PETG per cm³ (ROUGH, verify) | 2–5d | 1 |
| 3 | JLC (3DP + CNC + PCB) | 3D full-colour / metal / electronics | CN → worldwide | WJP colour/Tough, SLA, MJF/SLS, FDM, BJ/SLM metal, CNC, sheet, flex+rigid PCB | quote (upload → instant price + lead) | list floors: WJP $5, SLA/FDM/MJF ~$1, BJ $5, SLM $8, CNC $5, sheet $0.40, PCB asm $8 setup (LIST, verify landed) | varies (WJP Tough 72h+ build) | 1 |
| 4 | Yorkshire3D B2B | 3D escape hatch | UK → UK/worldwide | PLA/PETG/TPU/ASA, 40 colours | written quote (1 bus. day) | QUOTE, volume tiers 50+ | 3–10d | 1 |
| 5 | 3dfarm (York) | 3D backup UK | UK → UK only | PLA/PETG/TPU/Resin, 14 colours | manual (browser quote tool) | as-coded 320p/450p per cm³ — looks ~20× off the farm lane, VERIFY before use (SUSPECT) | 2d | 1 |
| 6 | Slant 3D | 3D US lane | US → worldwide | PLA/PETG, 4 colours, 220³mm | api (upload→estimate FREE→draft FREE→process charged, Bearer, webhooks, Etsy/Shopify) | QUOTE (free to estimate) | 2–5d | 1 |
| 7 | 3DAPI (US+EU) | 3D store fulfilment | US/EU → worldwide | PLA/PETG, 4 colours | api (Shopify/Etsy/Woo, SKU mapping) | QUOTE | 2–5d | 1 |
| 8 | Sculpteo | 3D premium EU/US | EU/US → worldwide | PLA/PETG/Nylon/Resin | api (upload/quote/cart/track, key via partnership) | QUOTE | 3–7d | 1 |
| 9 | Shapeways | 3D global platform | global → 130 countries | PLA/PETG/Nylon/Resin (+50 materials) | api (models→printability→materials→orders, free access) | QUOTE | 3–7d | 1 |
| 10 | Treatstock | 3D per-country network | global → worldwide | PLA/PETG/TPU/Resin/Nylon | api (upload→price with location[country]→order, key via support) | QUOTE (local vendor offers) | 2–7d | 1 |
| 11 | Craftcloud/All3DP | 3D compare (150+ shops) | global → worldwide | PLA/PETG/TPU/Nylon/Resin | api (model→parse→price→cart→order, +MCP via Kiln) | QUOTE (compare shops) | 3–7d | 1 |
| 12 | Xometry | 3D/CNC/sheet industrial overflow | US/EU → worldwide | FDM/SLA/SLS/MJF + CNC metals+plastics + sheet metal (+injection/urethane); DFM feedback | quote (instant quoting engine: upload CAD → price + lead + DFM; no open API — partnership/sales) | QUOTE (engine prices per part) | 3–7d | 1 |
| 13 | Prodigi | paper/merch LIVE | global → worldwide | 13 SKUs: cards, postcard, sticker, prints, mug, tote, notebook, jigsaw, canvas, wrap | api (key in `.env`, verified) | LIVE quote for SKUs in config (1 active: canvas); everything else EST | varies | 1 |
| 14 | Gelato | paper global | global → 32 countries (250+ partners) | paper | api (Order Flow REST, X-API-KEY, webhooks, Shopify/Etsy/Woo) | QUOTE | 3–6d | 1 |
| 15 | Mixam | paper UK/US/EU | UK → worldwide | paper (folded cards a speciality, 300dpi/3mm-bleed matches our contracts) | api (OpenAPI v3, instant calculator) | QUOTE (instant calculator free) | 2–5d | 1 |
| 16 | Printify | paper/merch global | global → worldwide | paper/merch via provider network | api (shops→products→orders) | QUOTE | 3–7d | 1 |

No keys stored for any lane except Prodigi. Every lane takes qty 1.

## What each lane can make today (OddHobb lines)

Farm-lane lines (all PLA/PETG, all currently `supplier: makr3d` except the
mesh five) with MAKR3D band cost vs shelf price (ex-VAT, VERIFY):

| Line | Price | Material | Weight | MAKR3D cost | Margin signal |
|---|---|---|---|---|---|
| golf_marker | £10 | PLA | 1.2g | £1.29 | wide |
| keycap | £15 | PLA | 2.9g | £1.29 | wide |
| book_holder | £5 | PLA | 3.3g | £1.29 | ok |
| clog_charm | £5 | PETG | 1.6g | £1.29 | ok |
| bag_charm | £10 | PLA | 1.6g | £1.29 | wide |
| shoelace_charm | £10 | PETG | 1.6g | £1.29 | wide |
| straw_charm | £3 | PETG | 1.6g | £1.29 | TIGHT — review price |
| cribbage_pegs | £15 | PETG | 0.5g | £1.29 | very wide |
| dart_stand | £20 | PLA | 7.5g | £1.29 | very wide |
| line_reader | £10 | PLA | 17.5g | £2.50 | ok |
| train_station | £20 | PLA | 16.3g | £2.50 | wide |
| card_rack | £15 | PLA | 67.6g | £2.50 floor | needs volume quote |
| tcg_stand | £15 | PLA | 74.2g | £2.50 floor | needs volume quote |
| rummy_rack | £15 | PLA | 134.9g | £2.50 floor | needs volume quote |
| controller_stand | £20 | PLA | 286.9g | £2.50 floor | band UNDER-prices this — real quote first |
| domino_racks | £20 | PLA | 274.9g | £2.50 floor | same — real quote first |
| wind_indicator | £15 | PLA | no geometry yet | — | stays `soon` until authored |

Mesh five: ornament £15 + keychain £15 + croc_tag £10 → Printie PLA display
lane; brick £20 + brick_keychain £10 → JLC WJP Tough (quote standard WJP
alongside) with multicolour-PLA fallback. gift_card £20 digital, no lane.
Paper: 13 Prodigi SKUs + 7 card templates → Prodigi (1 live SKU) then
Gelato/Mixam/Printify once wired — all QUOTE today.

Feasibility rule (same as `suppliers.estimate()`): material stocked +
colours ≤ max + dims ≤ build volume + region served. All 17 farm-lane lines
pass all 11 filament-capable lanes for a UK buyer (domino_racks 200mm fits
Slant's 220mm with 20mm to spare — tightest fit in the catalogue).

## New products each lane unlocks (ideas, not lines)

- **JLC**: full-colour collectible minis (WJP), tough brick figures (WJP
  Tough), durable nylon snap-fit game pieces (MJF ~$1), sculptural
  talismans + engraved seals (BJ $5 / SLM $8, detail ≥1mm — small glyphs go
  to laser), CNC discs/plates/housings + 1440dpi UV + laser mark ($5),
  sheet-metal tags/plates (from $0.40), BLE/LED/haptic/NFC wearables
  (flex+rigid PCB, asm from $8). Constraints: `docs/jlc-design-guide.md`,
  gate: `jlc_check()`.
- **Xometry**: tight-tolerance metal parts (CNC ±0.005" metals, min wall
  0.030"), plastic precision (min wall 0.060"), SLS nylon functional parts
  (walls 0.7–1mm, ±0.015"), FDM large parts (24×36×36", walls 1.2–1.5mm),
  sheet tags/brackets (edge-to-bend ±0.015"), anything needing DFM feedback
  before we commit tooling. Full numbers: `~/supplier-docs/xometry-*`.
- **Yorkshire3D**: TPU grips/cases/bumpers/straps, ASA outdoor stakes +
  memorials, multi-part assemblies, threaded inserts.
- **Slant 3D**: the entire farm-lane catalogue for US buyers (free
  estimate/draft calls prove pricing before promising dispatch).
- **Gelato/Mixam**: cards/posters printed in-country (nearest of 250+
  partners); Mixam folded greeting cards match our 300dpi/3mm-bleed
  contracts exactly.
- **Treatstock/Craftcloud**: per-country cheapest-vendor routing +
  one-off compare shopping before committing a lane.
- **Sculpteo/Shapeways**: premium/EU and 130-country fallback with real
  order APIs when the farm lane can't serve a buyer.

## How AI designs from this (hookup)

1. Agent reads `backend/supplier_catalog.json`: lines (price, material,
   dims, weight, method, zone, sample gate) + lanes (materials, build
   volume, price basis + grade, order path).
2. Agent proposes inside a line's locked interfaces (or a new line reusing
   a proven interface: MX cross, Croc pin Ø4.2mm, 1/8" peg shaft, 24mm
   marker disc) and checks material + colours + dims against the lane.
3. Agent calls `POST /api/design/validate` → feasibility + ranked supplier
   options with `est_cents` or a named gap (never a faked number).
4. Sample gate stays human: `sample: needed` lines can't flip `live`.

## Gaps (honest)

1. `POST /api/design/validate` only serves makr3d/printie options
   (`server.py` filters to those two) — the other 12 registered lanes are
   invisible to agents until that filter widens. Proposed, not built.
2. `jlc` isn't in the `SUPPLIERS` registry (`PRIMARY_SUPPLIER` points at
   it) — validate can't rank it. Proposed entry in the JSON.
3. 3dfarm's coded rates (320p/450p per cm³) look ~20× off the farm lane —
   VERIFY before any maths uses them.
4. Heavy parts (controller 287g, domino 275g, rummy 135g) sit on the
   £2.50 band floor, which under-prices them — first live quotes needed.
5. Straw charm at £3 has the thinnest margin in the catalogue.
6. Paper lanes (Gelato/Mixam/Printify) registered but unwired; one live
   Prodigi SKU. US-lane ranking unproven end-to-end (free Slant draft
   proves it for $0).
