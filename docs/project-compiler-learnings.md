# Project compiler: what people who've tried this learned

Saved 2026-10-10. Source: founder research paste (case studies + stack
recommendations). Canonical vision: `stallshark` upload
ODDHOBB_CANONICAL_VISION.md (see provider list note in
docs/provider-templates.md).

## Case studies (margins are operational, not design)

- Hardware-kit seller ($10k revenue, $2k profit, <$5/hr): China-sourced
  screws/motors/bearings + free design files. Lessons: source far below
  AliExpress retail, but postage/ads/support/packing eat margin ($6 kit,
  shipping outweighed goods on Kickstarter). Thingiverse = acquisition.
  Outsourced China shipping reduced manual work.
- Etsy jewellery-kit seller: kits + supplies growth channel, assembly
  labour accounted, ~4–5x material pricing practice (theirs, not gospel).
- Shenzhen/China 3PL threads (May 2026): demand receiving photos,
  component inspection, batch tracking, inventory logs, shortage
  responsibility, fee schedules. Treat posters as leads, not endorsements.

Takeaway: design discovery cheap, components standardised,
packing/support tight. Never let AI invent 17-item bespoke projects.

## Recommended stack (adapt, don't rebuild ERP)

- **InvenTree** (open-source inventory/MRP: parts, suppliers, stock,
  BOMs, build orders, REST) — core backend candidate. Build-order API
  reserves stock against assemblies ≈ our kit recipes.
- **Odoo** — full ERP, subcontracting workflow close to OddHobb; excessive
  for the pilot.
- **build123d** (Python parametric CAD on Open Cascade) — precise room
  panels, interfaces, mounting holes. Blender stays for organic meshes.
- **BrickLink Studio Instruction Maker** — reference for step assembly
  illustrations, not a compiler.
- **CADAM** (OSE CAD Automator): project schema → CAD + BOM + build
  guide. Closest architecture seen; generated procedures unproven
  physically.
- **PartsBox** — electronics distributor pricing API (live offers, MOQs).
  Don't build component pricing from scratch.

## Physical QA (enforced, not WhatsApp)

Every project ships a warehouse execution pack: supplier POs,
received-component IDs, packing quantities, booklet revision, inspection
checklist, label + shipping instructions, customer design files. Scans
confirm each item; missing components block release. Our run-states
(needed → ordered → received → verified) already model this.

## Implementation shape

Standalone project layer over the mesh engine (not mixed into it).
First deliverable: one complete compiled kit (Charm Lab v1: project.json,
bom.json, supplier_quotes.json, custom STL, instructions.pdf,
packing_manifest.pdf, quote.json, order ref) — automated fulfilment only
after a physical prototype passes. Repeat for Grimoire + Tiny Room.

## Strategic shift (accepted)

Thin structured layer over InvenTree + Blender/build123d + supplier
adapters + Shopify — not an enormous standalone compiler. Proprietary
edge: personalising verified projects without breaking them, exact
compatible parts across Chinese suppliers, one reproducible pack spec,
delivered price before checkout, learning from fulfilment failures.
Catalogue becomes combinable library (ornament in decoration set, brick
figure as diorama centrepiece, card as gift intro).

## Canonical five engines → our modules (2026-10-10)

Source: docs/canonical-vision.md §5 (imported from R2 stallshark).

| Canonical engine | Ours | Gap |
|---|---|---|
| Source compiler | xmas_card_preview, wrap_preview, booklet_preview, template_engine | rights_status tracked; source-text structuring (grimoire) future |
| Capability resolver | suppliers.py + project_check.py + delivery.py | parametric tolerances (build123d covers geometry) |
| Kit compiler | components.py (recipes, run-states) + template_engine | revision freezing (status field) still to add |
| Commercial compiler | quotes/compare, feasibility.py, postage rule, GB/US matrix | Mixam live client; landed-cost table per country |
| Gift recommender | guide funnel, select_for_template, reminders, families | occasion/budget ranking pass |

Agent contract mapping: discover≈products/for+guide, configure=templates/fill, preview=triptych/render, quote=quotes/compare, checkout=checkout endpoints, track=**MISSING** (no order-tracking endpoint yet — next).
