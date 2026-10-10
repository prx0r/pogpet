# Shenzhen manufacturing network — who to contact and what to ask (founder research, verbatim 2026-10-10)

> You don't need one supplier that manufactures everything. You need three
> commercial relationships with the compiler coordinating them: JLC makes
> exact parts, an integration partner makes them function, a consolidation
> partner makes one gift box. Wired into: `catalog/suppliers.json`
> (prospects marked, zero processes until qualified), `docs/supplier-
> outreach.md` (living tracker), `studio/suppliers/` (adapters).
> Roles below are advertised capabilities, not completed qualifications.

The compiler is OddHobb's product. The Shenzhen companies execute the jobs
it generates. Since Elecrow previously asked for a design list, approach
every supplier as a repeatable product-generation and fulfilment platform,
not one fixed gadget.

## 1. Suppliers to contact first

01 · Digital fabrication partner — JLCPCB / JLC3DP: 3D parts,
CNC-compatible workflows, PCB fabrication, PCBA, live quoting.
Contact: support@jlcpcb.com, JLC API portal (api.jlcpcb.com).

02 · Complete electronic product partner — Makerfabs: schematic design,
PCBA, mechanical coordination, programming, testing, enclosures, end-user
packaging. Contact: service@makerfabs.com, makerfabs.cc/service.html.

03 · Order-of-one fulfilment candidate — NextSmartShip: China warehousing,
multi-product receipt, kitting, branded boxes, Shopify integration,
international shipping. No standard MOQ published; custom one-off kit
assembly needs separate confirmation. Contact: sales@nextsmartship.com.

04 · Multi-supplier kitting alternative — China Fulfillment International:
Shenzhen receiving, inspection, SKU consolidation, gift packaging,
worldwide dispatch. Contact: support@china-fulfillment.com.

05 · Hardware engineering and electronic kits — Seeed Studio Fusion: PCBA,
Grove components, customisation, kitting, production coordination.
Contact: fusion@seeed.io, seeedstudio.com kitting service.

06 · Existing relationship — Elecrow: turnkey PCBA, external sourcing,
testing, inventory, packaging, dropshipping. Contact: service@elecrow.com,
elecrow.com dropshipping services.

## 2. Can JLC build a complete robot?

JLC manufactures much of a robot but is not a general robot-design-and-
assembly company:

| Task | JLC | Makerfabs / Seeed / Elecrow |
|---|---|---|
| Print robot shell | Yes | Can coordinate |
| Mechanical parts | Selected processes | Can coordinate suppliers |
| Produce PCB | Yes | Yes |
| Populate PCB | Yes | Yes |
| Source selected electronics | Within supported parts/workflows | Potentially broader |
| Program firmware | Partially, subject to approval | Advertised integration service |
| PCBA functional tests | Scoped to agreed test plans | Yes |
| Fit motors/speaker/shell together | Not standard end-product service | Appropriate to request |
| Engineer robot mechanics from concept | Not standard API product | Some offer engineering |
| Commission/test complete robot | Not generally standard | Possible by project agreement |
| Gift-box + dropship final robot | Not normal PCB/3DP offering | Available from selected integrators |

JLC supports PCB programming and power-on testing by special evaluation
($7.86 programming engineering fee plus labour; $15.70 power-on testing
engineering plus labour) — more capable than basic manufacturing, not full
assembly. Makerfabs explicitly advertises coordinating electronics,
mechanical production, programming, testing, enclosure design and final
shipping. Seeed industrialised Pollen Robotics/Hugging Face's Reachy Mini
toward 3,000 units — real robotics manufacturing experience, though not
proof of one-off commissions.

Arrangement for OddHobb Studio: compiler (intent → approved modules →
exact CAD + circuit + simulation) → JLC (fabricates parts) → hardware
integration partner (feasibility review, assembly, test) → Shenzhen
kitting/fulfilment (box → QA → ship). Compiler starts from validated
modules; novel electronics get integrator review. Supplier APIs automate
manufacturing but never independently verify an AI-generated circuit or
moving robot is safe and functional.

## 3. The crucial partner: receive four unrelated goods, make one gift box

Filter question: can you receive four different components from four
different suppliers, wait until every item for one customer is ready,
verify contents, assemble a personalised gift box, and ship one completed
order? That is order-level dynamic kitting — harder than bulk
subscription-box packing.

- **NextSmartShip (test first)**: published no standard MOQ, free setup,
  two months free storage, $0.50 first pick / $0.10 additional; customised
  kitting separately quoted. Customer example combines multi-supplier
  components into modular kits. Ask: single-order kit assembly with
  personalised instruction + per-order SKU selection.
- **China Fulfillment International**: advertises multi-supplier
  receiving, per-delivery checks, branded kits, finished kit SKUs, no
  minimum volumes, $0.99 baseline pick-and-pack (do not assume it covers
  personalised kitting/inspection). Ask: filmed pilot, four incoming
  shipments, one custom gift box.
- **Elecrow (third candidate)**: receives customer-supplied components
  from other Chinese suppliers for PCBA (possible handling fees) plus
  warehousing/packing dropship operation. Ask: extend to non-electronic
  craft goods, books, yarn, gift boxes. Unverified.

Trial: personalised grimoire gift box — Supplier A printed book (A5
hardcover, custom cover/contents), Supplier B engraved brass token/plaque
in pouch, Supplier C blank journal, Supplier D wax-seal/ribbon craft
pack; warehouse verifies four parts against BOM, compartments, custom
instruction card, photographs box, ships. Require during pilot: received
quantities, per-item QC, missing components, kitting labour time, boxed
dimensions/weight, packing photos, tracking, itemised cost. Success =
reliable for ONE unique order, not 100 identical boxes.

## 4. Grimoire, beads, knitting: three compiler test cases

Different sourcing without expensive electronics:

- **A. Ochema Grimoire Kit** (custom printing + metalwork + components +
  premium packaging): book from OneBookPrint, Guangzhou (one-copy
  hardcover/paperback advertised); JLC3DP accessories; approved metal
  engraver for brass; craft supplier remainder. Tests: provenance, file
  generation, personalisation, mixed materials, lead-time coordination,
  custom packaging.
- **B. Personalised Bead-Making Kit** (catalogues + compatibility +
  quantities + kits): named glass-bead palette, cord, clasps, charms,
  tools, printed tutorial; pet/flower/season/palette inspiration. Mostly
  approved Chinese craft vendors; JLC only for genuinely custom charm/tool.
  Tests: exact counts, hole-vs-cord diameter, clasp compatibility, safe
  substitution, per-customer picking.
- **C. Custom Knitting Project Kit** (variable quantities + sizing +
  equivalence): project + palette → yardage, needle sizes, pattern,
  accessories, personalised packaging. Tests: weight/gauge, yardage,
  dye-lot consistency, substitution rules, packaging volume, full BOM.

A normal catalogue stores product and price. OddHobb stores constraints
and substitutions: DK yarn must never silently become super bulky; bead
hole diameter and findings compatibility are engineering constraints.

Specialist sourcing starts: OneBookPrint (confirm Shenzhen-warehouse
delivery + written turnaround — lead times differ across their pages);
JLC3DP (exact geometry/material quotes); JLCPCB (verified circuit + files);
1688 vendors (individual vetting, samples, MOQs, possible local buying
support); Seeed kitting (starts at five sets — unproven for one-offs);
NextSmartShip / China Fulfillment (qualify personalised assembly + extra
charges). Don't ask JLC to be the whole chain — wrong supplier for most
of a bead or knitting pack.

## 5. What to say to them

Stop describing an ambitious general AI factory. Describe the immediate
operational requirement, show a specific pilot, mention software
generating many similar jobs automatically. Every supplier should know
the next-30-day need.

**Email 1 — JLC API partnership** (support@jlcpcb.com + api.jlcpcb.com):
OddHobb (oddhobb.com), personalised physical-product platform, AI-assisted
design → manufacturable products. Compiler validates, estimates, quotes,
routes approved orders. Want JLC as primary for low-volume 3D parts +
enclosures, PCB fabrication/assembly, component availability/pricing,
automated quote/order/status. Reference products: personalised figurines,
illuminated stands, small ESP32 interactive objects; designs vary per
order over standardised interfaces. Ask: (1) 3D Printing + PCB/Components
API access, (2) pricing-only access while building, (3) formats/MOQs/
quote validity/order requirements, (4) ship finished parts + assemblies
to a nominated Shenzhen assembly partner, (5) any assembly/integration
beyond standard PCBA. Start with a small prototype order + share API
workflow. Nuance: September 2026 policy weighs order history — submit an
ordinary prototype order alongside the application, don't wait.

**Email 2 — warehouse (NextSmartShip + China Fulfillment independently)**:
personalised gift/custom-project business needing Shenzhen partner to
receive multi-supplier goods and combine into one custom box per
customer; orders may be unique (book + engraved object + journal + craft,
or bead/knitting kits). Pilot: four suppliers deliver, warehouse
receives/identifies/checks, packs one box with customer-specific insert,
ships. Ask: (1) unique-order custom kitting (not batch), (2) receiving
from JLC/1688/independents, (3) order BOM/packing instructions as
CSV/JSON/PDF, (4) personalised insert printing, quantity checks, box
photos, (5) missing/late/defective handling, (6) receiving/storage/
picking/kitting/packaging/shipping fees, (7) API/Shopify integration with
receiving events, packing confirmation, photos, tracking. Goal:
repeatable workflow from small volumes. What matters isn't the shipping
rate — it's receiving a unique job manifest, associating parcels to the
order, evidencing correct packing.

**Email 3 — integrator (Makerfabs / Seeed / Elecrow separately)**:
AI-assisted design + manufacturing platform standardising verified
electronics modules, many custom enclosures around them; want long-term
integration partner, not one fixed design. Reference: USB-powered
illuminated display/miniature house (ESP32, addressable RGB, ambient
sensor, optional button/mic/speaker, custom 3D shell, bounded
agent-lighting firmware). Provide 3D design, interface spec, initial BOM,
simulator, test requirements; want manufacturability review + circuit/
assembly/integration/testing help. Process: validated package → prototype
quote → engineering mods → source/assemble → flash → defined test pass →
pack or forward to fulfilment partner. Ask: NRE fees, quantity-one
feasibility, MOQs, lead times, test procedures, JLC-supplied
parts/enclosures accepted, API/structured intake/recurring workflow for
same-core designs. For Elecrow: reframe the design-list request as a
family of designs over standard interfaces, attach one reference design
to cost.

## 6. The manufacturing job packet (what the compiler generates)

Ordinary gift kit — `ODDHOBB JOB: GRIMOIRE-001`, qty 1, UK destination:
components A–D with quantities; packaging (box 260×200×80mm, 4
compartments, personalised A5 insert); QC (correct book revision,
engraving matches, quantities, all present, photograph box); delivery
(one parcel; return weight, price, tracking). Interactive hardware adds:
schematics, board files, firmware, power limits, pinouts, CAD, assembly
drawings, functional test procedures. The warehouse executes the packet;
the engineer gets a spec + explicit test (press button, sample sensor,
change LED scene, receive audio, meet power limits). No AI understanding
required at either end.

## 7. First money (three proofs, qty 1/10/100 pricing, NRE split out)

One custom grimoire box (four-supplier receiving + packing + one
international shipment); one illuminated base (PCB/module/LEDs/shell/
assembly/firmware — off-the-shelf controller first); one bead/knitting
kit (variant BOM, picking, instructions — standard materials, no new
tooling). Avoid unrelated stock until fulfilment is qualified.

## 8. Long-term arrangement

JLC3DP (exact geometry, revision, quote, material) → JLCPCB/LCSC (BOM,
firmware, test spec) → Makerfabs/Seeed (assembly instructions, test
results, device identity) → OneBookPrint/printers (approved PDF + spec)
→ vetted 1688 vendors (exact part IDs + substitutes) → NextSmartShip /
China Fulfillment (per-customer manifest + QC) → OddHobb compiler (all
recipes, suppliers, pricing, job history, customer experience). Note:
basic gift boxes may eventually need only the 3PL + its sourcing network.

## Priority for the next seven days

Two Shenzhen fulfilment companies answering in writing: will you assemble
a different custom kit per customer from multi-factory components, and at
what cost? In parallel: JLC 3D+PCB API applications, Makerfabs/Seeed
quote for one assembled GlowBase reference. Those three confirmations
decide whether the compiler becomes a real product.
