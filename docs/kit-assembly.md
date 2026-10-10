# OddHobb Kit Assembly (the missing piece)

If we solve sourcing unrelated objects and combining them into one
beautiful gift box, we unlock everything: £19 charm kits, £49 witchcraft
sets, grimoire kits, dollhouses, eventually electronics projects. We
don't need our own warehouse — we need a system that tells a fulfilment
partner precisely what goes in each box.

> Describe the person or project. OddHobb finds the components, creates
> the instructions and delivers the entire experience in one box.

## 1. Candidate assemblers

| Provider | Offer | Published base |
|---|---|---|
| China-Fulfillment, Shenzhen | Multi-supplier receiving, checks, kit assembly, branded packaging, single-SKU finished box | $0.50 kitting + $0.99 pick/pack |
| Angler Fulfilment, UK | Gift sets, hampers, personalisation, kit building | From £0.50/kit |
| Leicester Pallet Storage, UK | Assemble-to-order, no minimum, 24–48h kitting | Quote-based |
| Cloud9 Fulfilment, UK | Kit building, Shopify/Etsy integration | Quote-based |
| Seeed Fusion Kitting | Components, PCBs, print, custom boxes | From 5 sets |
| ShipBob | Inventory, gift boxes, inspections, shipping | Custom quote |

Published prices are handling bases, not delivered quotations. The
Shenzhen provider explicitly does multi-supplier receiving, quantity
checks, spec builds and single-SKU boxing, with zero receiving fees and
visual inspection. Leicester is the UK pilot lead (assemble-to-order,
no minimum).

## 2. Fulfilment model

JLC/Slant (custom 3D) + craft suppliers (materials) + print supplier
(booklets/cards) + packaging supplier (boxes/inserts) → ONE assembly
location → receive → check → label → consolidate → package → audit →
one gift box, one parcel, one tracking number. Six component shipments
in, one customer parcel out. Modes: pre-kitted bestsellers (25–50 ahead,
faster/cheaper) vs pack-to-order personalised (per-order assembly) vs
hybrid.

## 3. Stock components, not finished sets

~100 reusable components in the warehouse; the agent composes gift
boxes from them. Grimoire Maker (journal, aged paper, seals,
illustrations, personalised cover, booklet, £29–49), Little Witch
Workshop (£24–39), Charm Laboratory (£17–25) all draw from shared
inventory. Component registry shape:

```
component_id: OH-BOOK-001
suppliers: [{supplier, sku, minimum_order}]
inventory: [{warehouse, available}]
compatible_projects: [...]
packing: {bag, label}
```

Recipes hold exact component IDs, quantities, assembly steps, artwork,
packaging rules. The compiler validates in-stock, compatible, safe and
economical before checkout. Bespoke raises a production order (JLC/Slant)
and waits for arrival before dispatch.

## 4. The warehouse-print question

Can the warehouse print a unique 8–16-page booklet + gift card per
order? If yes, standard-materials boxes still feel unique. If no, add a
short-run print partner. Without it, customisation means split shipments.

## 5. First test without inventory

Leicester (UK pilot): receive 15 SKUs, store separately, assemble three
recipes to order, add personalised booklet, ship one branded parcel —
real sample of three different packing recipes. China-Fulfillment:
delivered cost of 10 kits (JLC + two craft suppliers) to UK customers.
Start non-hazardous: paper, thread, beads, charms, bottles, print (no
ingestibles, oils, burning supplies, unverified cosmetics).

## 6. Strategic insight

OddHobb's unit is the verified project recipe (not a design): digital
download, DIY box, gift set, finished object, compatible upgrade — from
one infrastructure. Existing products become components (ornament in a
decoration set, brick figure as diorama centrepiece, card as the gift's
introduction). First question to answer: arbitrary 10–15 stocked
components + unique booklet + single gift box at a viable all-in price.
