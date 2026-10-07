# Product + supplier system — what a product is, what a card is, and how machines design inside them

> Status: live contract docs (2026-10-06). Code truth: `backend/config.py`
> (`STUDIO_LINES`, `DESIGN_CONTRACTS`, `PRODIGI_PRODUCTS`), `backend/card_scenes.py`
> (`FORMATS`, `CARD_DESIGN_CONTRACTS`), `backend/suppliers.py` (14 suppliers),
> `backend/prodigi.py` (live paper quotes), `backend/server.py` (`/api/design/validate`,
> `/api/products/studio`, `/api/gift-packs`). Vision parent: `vision/docs-vision.md`
> (products as AI design contracts), `vision/thesis.md` (one-shot manufacturing).

## Short answer

Yes — with one honest caveat. Every 3D line ChatGPT can sell already carries a
machine-readable design contract (locked interface geometry, envelope, material,
colour cap, volume estimate, cost targets, physical verify steps), and every card
template carries a paper contract (bleed, DPI floor, spine clearance, photo counts,
stock, formats, cost targets). Estimated pricing exists for all of them, but it is
two-tier: 3D estimates are computed from the farm-lane model for MAKR3D/Printie and
quote-grade (no faked numbers) for everyone else; paper is EST everywhere except the
one Prodigi SKU with a verified live quote. The routing rule is: feasibility gates
first, home-region first, cheapest estimate first, live quote always wins, and the
shopper never sees a farm name.

## 1. What determines a product vs a card

A **product** is a physical 3D-printable line. It exists in three places that must
agree: `STUDIO_LINES` (shop truth — label, scale, price, status live/soon,
personalisation method/zone, supplier, fulfilment, recipes), `DESIGN_CONTRACTS`
(engineering truth — same ids), and the factory registry (`scripts/factory/`
adapters + masters + `factory_registry.json` gates). The two maps are fused at
import time (`config.py:769` copies each contract onto its line as
`design_contract`), so the shop cannot drift from the engineering.

A **card** is paper stationery, not a 3D line. It exists in `backend/card_scenes.py`:
`FORMATS` (A6/5x7/A5 with trim mm, folded flag, price) plus `TEMPLATES` (7 templates
with photo min/max, motion, palette) plus `CARD_DESIGN_CONTRACTS` (same reusable
shape as 3D lines, but `domain: paper` — locked = print truths, envelope = largest
trim, material = stock, cost = rough print cost per format). The 13 `PRODIGI_PRODUCTS`
in config are the wider paper/merch shelf (cards, postcards, stickers, prints, mugs,
etc.) — card templates are the personalisable core, Prodigi products are the
fulfilment SKUs around them.

Domains, and why they matter to a designer:

| Domain | Who | Personalisation | Example locked truths |
|---|---|---|---|
| `mesh` | subject-derived lines (ornament, keychain, brick…) | `face_swap` full mesh | loop/ring diameters, scale, no metal |
| `reference` | functional lines (keycap, golf marker, racks…) | `emboss`/`relief` text + motif | MX cross 4×4mm, pin stems, channel widths |
| `digital` | gift_card | `credit` amount | none — no manufacture |
| `paper` | card templates | photo + headline/message | 3mm bleed, 300dpi floor, spine clearance |

`origin` is the guarantee from the validated vision: reference-first where function
must hold (the adapter transform is the law), mesh where the friend's mesh is the
gift. The five `face_swap` lines are approved mesh-origin exceptions, not violations —
their functional geometry (loop, ring, pin, footprint) is still locked.

## 2. Constraint anatomy (what ChatGPT actually gets)

3D line contract (`DESIGN_CONTRACTS[keycap]` as the smallest complete example):

```jsonc
{
  "origin": "reference",
  "locked": ["Cherry MX stem: cross 4.0x4.0mm outer, wall 1.2mm, mount depth 4.5mm",
             "cap top zone 12x12mm for relief"],
  "envelope_mm": [18, 18, 14],
  "material": "PLA",
  "colors_max": 4,
  "volume_cm3_est": 1.8,
  "cost_target_cents": {"makr3d": 100, "printie": 100},
  "verify": ["stem fit on a real MX switch"]
}
```

Paper template contract (`CARD_DESIGN_CONTRACTS[portrait]`):

```jsonc
{
  "domain": "paper",
  "locked": ["3mm bleed all round", "300dpi floor at trim",
             "folded formats: artwork keeps clear of the spine 6mm",
             "1 photo exactly (face crop with focus point)"],
  "envelope_mm": [148, 210],
  "material": "350gsm silk",
  "colors_max": 0,
  "formats": ["A6", "5x7", "A5"],
  "cost_target_cents": {"A6": 120, "5x7": 200, "A5": 280},
  "verify": []
}
```

Rules for agents: `locked` is never negotiable (validation is the same gate as
manufacture — `POST /api/design/validate` enforces dims/material/text against it);
everything else (name, motif, coat, pattern, message, photos inside min/max) is free.
`verify` is the physical truth step (pin fit on a real Croc hole, stem fit on a real
switch) — a line with an open `verify` item stays `soon` no matter how good the
render looks. `wind_indicator` is the extreme case: geometry not yet authored, so the
contract itself says so.

## 3. Material assignment logic

Materials are assigned, not chosen by the shopper. The thesis rule (`vision/thesis.md`):
if it can be one part, it is one part; PLA by default, PETG where flex or abuse is
expected. In code that is the per-line `material` in the contract:

- **PLA** (default): racks, readers, stations, stands, markers, ornaments, keychains —
  rigid, precise, cleanest detail, broadest colour selection.
- **PETG** (flagged): clog/croc connectors, shoelace channels, straw rings, cribbage
  peg shafts, keycap stems if testing says so, anything thin or droppable — tougher,
  some flex before breaking.
- **TPU/ASA** (escape hatch): nothing in the default shelf; routed to Yorkshire3D
  custom manufacturing when genuinely required, never to the automated farm lane.
- **digital**: gift_card — no material, no manufacture.
- **paper**: card templates — `350gsm silk` default; Prodigi/Mixam/Gelato stocks at
  fulfilment time.

`colors_max: 4` on every 3D line is a farm constraint turned into a design constraint
(MAKR3D AMS workflow; five-plus colours route to review). A design asking for 5
colours is infeasible on the default lane — `estimate()` returns the gap rather than
a price.

## 4. Supplier routing by user location

Routing lives in `backend/suppliers.py:options_for()` and is served per line by
`POST /api/design/validate` (which returns ranked `options`) and `_fulfilment_options`
(shop-facing, names stripped per the invisibility house rule). The algorithm:

1. **Feasibility gates.** Material stocked? Colours within max? Dims inside build
   volume? Region served (`ships` contains the user's region or `worldwide`)? Any
   failure marks that supplier infeasible with a named gap — never a silent price.
2. **Home-region first.** Feasible suppliers whose `ships`/`home` matches the user
   rank above the rest.
3. **Cheapest estimate first.** Among feasible, lowest `est_cents` wins; `None`
   (quote-grade) sorts last — estimates never outrank a live number.
4. **Live quote always wins.** `suppliers.estimate()` is a band or a rough per-cm³
   normalisation explicitly marked VERIFY; Prodigi `quote()` and any farm quote tool
   replace it the moment they return. The customer sees true landed cost before
   anything renders twice.
5. **Invisible farms.** The storefront and agent surfaces serve capability summaries
   (materials, colours, dispatch range) — never farm names. Routing happens
   server-side; Oddy proposes adjustments ("make it this big") when close to a
   better fit.

Worked example — golf marker for a UK buyer (`PLA`, `[24,24,4]`, ~1.2cm³):
MAKR3D feasible (~£1.00 band), Printie feasible (~£1.00), Slant 3D feasible but
quote-grade and US-home (ranks below for UK), Gelato/Mixam infeasible (paper lane —
correctly excluded from a filament line), Xometry feasible but quote-grade industrial
overflow. UK buyer sees the MAKR3D-lane estimate; US buyer sees the same line with
Slant 3D ranked as the home API lane once live quotes land.

## 5. Supplier table (normalised, 13 + paper-live)

All entries share one schema (`label/home/ships/materials/colors_max/build_mm/order/
api/min_qty/account/commitment/dispatch_days/notes/est`). Every farm takes qty 1
with no relationship (`can_single_order`). No keys stored anywhere.

| Supplier | Lane | Home → serves | Materials | Order | Pricing today |
|---|---|---|---|---|---|
| MAKR3D (Yorkshire3D farm) | 3D default | UK → UK/worldwide | PLA/PETG, 4 colours | api | **band** (weight bands + per-cm³ cross-check, ex-VAT, VERIFY) |
| Printie | 3D second UK | UK → UK/worldwide | PLA/PETG, 4 | manual quote tool | **per-cm³ rough** (VERIFY) |
| Yorkshire3D B2B | 3D escape hatch | UK → UK/worldwide | PLA/PETG/TPU/ASA | written quote | **quote** |
| 3dfarm (York) | 3D backup UK | UK → UK only | PLA/PETG/TPU/Resin | manual | **per-cm³ published** |
| Slant 3D megafarm | 3D US lane | US → worldwide | PLA/PETG, 4 | **api** (upload→estimate→draft→process, Bearer, webhooks; Etsy/Shopify) | **quote** (estimate+draft free, charged on process) |
| Shapeways | 3D global platform | global → worldwide (130 countries) | PLA/PETG/Nylon/Resin | **api** (models/materials/orders, free access) | **quote** |
| 3DAPI (US+EU) | 3D store fulfilment | US/EU → worldwide | PLA/PETG, 4 | api (Shopify/Etsy/Woo) | **quote** |
| Sculpteo | 3D premium EU/US | EU/US → worldwide | PLA/PETG/Nylon/Resin | api | **quote** |
| Treatstock | 3D per-country network | global → worldwide | PLA/PETG/TPU/Resin/Nylon | api (location[country] offers) | **quote** |
| Craftcloud/All3DP | 3D compare (150+ shops) | global → worldwide | PLA/PETG/TPU/Nylon/Resin | api (+MCP via Kiln) | **quote** |
| Xometry | 3D industrial overflow | US/EU → worldwide | PLA/PETG/Nylon/Resin | quote (instant engine + DFM, no open key) | **quote** |
| Gelato | **paper** global | global → worldwide (32 countries, 250+ partners) | paper | **api** (Order Flow + ecommerce, X-API-KEY, webhooks) | **quote** |
| Mixam | **paper** UK/US/EU | UK → worldwide (UK/US/IE/CA/DE/AU shops) | paper | **api** (OpenAPI v3, instant calculator) | **quote** |
| Printify | **paper/merch** global | global → worldwide | paper | **api** (shops → products → orders) | **quote** |
| Prodigi (separate module) | **paper/merch live** | global → worldwide | paper + merch SKUs | **api** (key in `.env`, verified) | **LIVE quote** for SKUs in config; everything else EST |

Why these five are the right additions: Slant 3D is the US equivalent of MAKR3D with
the cleanest POD API in the category (free estimate/draft, charge on process,
Etsy/Shopify native); Shapeways brings the 130-country fallback with a real orders
API; Xometry covers the industrial-overflow case the thesis explicitly reserves
(TPU/ASA/metals, DFM feedback); Gelato gives cards/posters the same local-production
routing the 3D side already has (nearest of 250+ partners); Mixam gives the UK card
lane a trade printer whose 300dpi/3mm-bleed/folded-card truths already match our paper
contracts, with a public OpenAPI. Sources: slant3d.com API pages, developers.shapeways.com
reference, xometry.com/quoting + xometry.eu IQE, gelato.com network/API docs,
mixam.co.uk + mixam.com API documentation pages.

## 6. Pricing grades (read this before quoting a customer)

- **LIVE**: Prodigi SKUs with `sku` in config (currently 1: `GLOBAL-CAN-10X10`
  canvas) — `prodigi.quote()` returns item + shipping + tax + carrier per country.
  Every other Prodigi product shows EST until its SKU is looked up in the dashboard.
- **Band** (MAKR3D): weight bands from real file quotes (£1.29 benchy / £2.50 fidget
  anchors), cross-checked against the per-cm³ rough — ex-VAT, VERIFY on first live
  quote, farm pricing moves.
- **Per-cm³ rough** (Printie, 3dfarm): clearly labelled rate × volume — VERIFY.
- **Quote** (everyone else): `est_cents: None` by design. The system refuses to fake
  a number; the agent must call the live quote path. This is why `cost_target_cents`
  on 3D contracts only lists makr3d/printie today — targets for the other eleven
  lanes get filled from first live quotes, not invented here.

## 7. What ChatGPT designs against (machine surfaces)

- `figg_product_assets` → `GET /api/products/studio`: every line with its contract,
  stills, prices, plus `gifts` derivations and `suggestion` motif.
- `figg_design_base` / `figg_design_validate` → `GET /api/design/base`,
  `POST /api/design/validate`: download the base, check dims/material/text/colours
  against locked interfaces, returns feasibility + ranked supplier options.
- `figg_supplier_quote` → same validate path with material/colours/dims.
- `figg_gift_pack` → `POST /api/gift-packs`: Oddy's game — best physical leaving
  room for a card inside the budget, video free, exact requests honoured with cheap
  add-ons.
- `figg_fullchain_personalise_order` → personalise + reserve + optional Shopify draft
  (`fulfil:true`). No card charge from our API; price shown before every order call.

## 8. Intelligence sits beside it

The same normalization now covers AI models: `backend/ai_models.py` registers
three aggregators (OpenRouter = brain, fal.ai = media specialist, Alibaba =
value lane) against twelve machine needs (card art, lipsync, voice clone,
mesh second opinion…). Full comparison: `docs/ai-models.md`.

## 9. Gaps and next steps (honest)

1. `cost_target_cents` covers 2 of 13 suppliers — fill the rest from first live
   quotes (Slant estimate/draft calls are free; Mixam instant calculator; Gelato
   order-flow quotes; Prodigi per-SKU activation).
2. Material is a per-line default, not yet auto-derived from geometry — the matcher
   (`vision/docs-asset-filters.md` part 3) should confirm PETG flags from bbox/wall
   analysis rather than trusting the default.
3. Paper fulfilment is Prodigi-only in code — Gelato, Mixam and Printify are registered but
   unwired (no keys stored, no order path). Next: one paper order path with the same
   invisible-farm rule.
4. US-lane ranking is ready but unproven end-to-end — run a Slant draft (free) on a
   golf-marker STL to prove thelane before promising US dispatch times.
5. Samples still gate honesty — every `verify` item and every `sample: needed` line
   from the Round 13 list stays `soon` until a real print passes.
