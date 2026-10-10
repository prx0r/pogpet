# Shenzhen-first production and fulfilment hub

Decision: make Shenzhen the default production and fulfilment hub. For
OddHobb's planned catalogue, keeping manufacturing, craft materials,
electronics, printing and gift-box assembly inside China is likely much
more economical than splitting operations between UK and Chinese
suppliers. It creates a straightforward route from £20 craft kits to
personalised dollhouses, electronic gadgets and eventually AI-designed
robots.

Architecture: JLC + Chinese component suppliers → Shenzhen warehouse →
one custom OddHobb box → international customer.

## 1. The Chinese supply chain

| Partner                     | Role                                              | Status                               |
| --------------------------- | ------------------------------------------------- | ------------------------------------ |
| JLCPCB / JLC3DP             | Resin miniatures, personalised parts, CNC, PCBs   | Verified manufacturing services      |
| Elecrow                     | Motors, robotics electronics, PCB assembly, kits  | Sourcing, sub-assembly, kitting      |
| Seeed Studio                | Sensors, controllers, AI hardware, custom kits    | Turnkey custom kits (from 5 sets)    |
| LCSC                        | Electronic components and hardware                | Component distributor                |
| 1688                        | Beads, yarn, tools, paper, boxes, craft materials | Domestic wholesale sourcing          |
| Shenzhen fulfilment partner | Receive, inspect, pack and ship                   | Partner selection still needed       |

Seeed advertises kitting from five sets (printed materials, custom
packaging, outside-catalogue components). Elecrow offers sourcing,
sub-assembly and kitting, including customer-supplied components.

## 2. AliExpress versus 1688

Use 1688 (or Taobao for small retail) for domestic Chinese purchasing,
not AliExpress — AliExpress is international retail; 1688 is wholesale.
A Charm Lab: 100 beads from a 1688 seller, chain/clasps from another,
personalised resin frog from JLC, instruction cards from a local printer,
mailer box from a packaging factory. All five ship domestically to a
Shenzhen address — no separate international shipments. JLC's domestic
courier + factory pickup support this (verify warehouse delivery).

## 3. Packaging and assembly rates (published, to verify)

China-Fulfillment, Shenzhen: pick-and-pack from $0.99/order, kitting
from $0.50/kit, custom boxes from 50-unit print runs. 1688Fulfillment:
receiving from multiple suppliers, inspection, consolidation, repacking,
international shipping. Distinguish: China-Fulfillment (branded per-order
assembly lead), 1688Fulfillment (mixed-supplier management lead), Seeed
(electronics/robotics), Elecrow (hardware/testing/kitting alternative).
Published rates are base handling, not delivered quotes.

## 4. What a real order looks like (£34.99 Grimoire Maker Kit)

Blank journal/paper/thread (1688) + brass charms (1688) + personalised 3D
emblem (JLC3DP) + instruction booklet (Shenzhen printer) + gift box
(warehouse inventory). Warehouse confirms every component before the
order becomes eligible for assembly and dispatch. The compiler must never
treat "ordered" as "received" or "received" as "verified."

## 5. Three inventory classes (don't re-source every order)

Stocked common parts (beads, clasps, yarn, paper, boxes — pick from
warehouse); made-to-order parts (JLC figure, engraved badge, printed
booklet — produce on purchase); special-order parts (unique servo, rare
item — source only when necessary).

## 6. Complications

International delivery and customs (US ended duty-free de minimis for
low-value imports Aug 2025 — landed-cost care for US). Product safety
(toy/battery/wireless obligations — start adult, non-electrical).
Timing (slowest bespoke component sets the checkout lead time).

## 7. Build plan

One Shenzhen partner + three kits sharing common inventory (Charm Lab
£19.99, Grimoire Maker £34.99, Tiny Room Starter £49.99). Get them quoted
for: 10 preassembled, 10 personalised, 1 bespoke-with-JLC-part —
receiving, storage, printing, assembly, packaging, inspection, shipping,
duties. Then build Shopify ordering around their real capabilities.
Same operation scales: charms today, grimoire tomorrow, dollhouses next
year, agent-designed electronics eventually. First validation: a partner
accepting single-order made-to-order JLC parts alongside stocked
materials and unique booklets.
