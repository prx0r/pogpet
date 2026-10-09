# OddHobb Factory: an AI manufacturing router

Saved 2026-10-09 (founder vision, lightly cleaned). Companion build docs:
`docs/fulfilment-automation.md` (automation matrix), `docs/jlc-materials.md`
(materials bible), `backend/jlc_materials.json` + `backend/supplier_catalog.json`
(machine twins). Verification notes at the end — two claims checked out,
three remain open.

> An agent designs something in Blender, checks whether it can be
> manufactured, compares supplier prices and delivery dates, shows the buyer
> a preview, and — with approval — orders the finished physical object.

That could become the core of OddHobb, while Grimoirer, Glimlings and
Pogtown use the same infrastructure.

## 1. Suppliers to integrate

Ranked by usefulness for agent-driven manufacturing, not print quality.

| Supplier | Speciality | Automated quoting/ordering | Priority |
|---|---|---|---|
| JLC (api.jlcpcb.com) | Full-colour 3D, resin, nylon, metal, PCBs | Documented partner APIs; approval required | 1 |
| Sculpteo | Industrial polymer and metal 3D printing | Documented upload, quote and order API | 2 |
| PCBWay | 3D printing, CNC, PCB assembly | PCB API documented (verified 2026-10-09); 3D/CNC API coverage unverified | 3 |
| RapidDirect | CNC, metal, plastic, precision parts | Instant web quotes; public ordering API not established | 4 |
| Protolabs Network (Hubs) | Global/local CNC, 3D, sheet metal | Instant web quotes; API access to verify | 5 |
| Xometry | Large US manufacturing network | Instant web quotes; customer API unverified (dev docs look partner-oriented) | 6 |
| Fictiv | Consumer hardware, moulding, CNC | Digital quotations and ordering; API to verify | 7 |
| Seeed Fusion | Electronics and IoT prototyping | PCB assembly quoting; API access to verify | 8 |

JLC and Sculpteo first: their documentation describes the key steps an
agent needs, including order submission. Sculpteo is the fallback because
its docs describe a genuine model-pricing endpoint (quantity, material,
scale, currency, delivery) plus ordering to customer addresses — but note:
our Sculpteo snapshot is Cloudflare-blocked, so this rests on vendor docs
until re-verified.

## 2. Why Sculpteo is interesting

Uploading designs, configuring materials, retrieving prices, placing orders
from another application, direct e-commerce integration — a documented
intended use, not browser-automation workaround. Best fit: reusable
mechanical accessories (nylon mounts, keycaps, board-game components,
jewellery forms, wearable enclosures). JLC wins on extremely affordable
full-colour and mixed-process manufacturing.

## 3. Glimlings hardware fit

JLCPCB for the reusable electronic core (custom boards, sourcing,
assembly; API includes pricing/ordering plus parts catalogue). Seeed
Fusion + XIAO/Grove for early proof-of-concept electronics. Fictiv for
finished enclosures once the design is validated and tooling spend is
justified (silicone/moulded shells, not rough prints). JLC and Seeed
develop the electronics; Fictiv finishes the shell.

## 4. Router, not directory

Agent / Blender / OddHobb editor → manufacturing compiler (geometry
validation, units, textures, materials, licence checks) → comparable
offers (price, delivery, finish, durability, shipping, confidence) →
approval → order → tracking. Three price states:

| State | Meaning | May the agent order? |
|---|---|---|
| `estimated` | OddHobb's own cost model from previous orders | No |
| `quoted` | Supplier price, possibly subject to review | Only when conditions are met |
| `approved` | Final manufacturability + purchase terms accepted | Yes, with buyer authorisation |

A file being printable doesn't mean its textures, orientation or appearance
are correct — hence the proof gate (cf. the missing-face lesson).

Core verbs: `factory.analyze · repair · export · estimate · quote ·
compare · request_proof · order · track`. Example: personalised pet figure,
60mm, full-colour, qty 1, US destination, max $25 delivered, 12 days — the
response distinguishes real supplier quotes from OddHobb estimates, and a
supplier that can't do full-colour is excluded no matter how cheap its
resin price is. Ordering requires explicit approval of supplier, landed
cost, address and proof.

## 5. JLC access: pricing first, ordering second

JLC3DP has two tiers: Pricing API (comparison/estimation) and Ordering API
(upload, pricing, orders, tracking) aimed at approved commercial partners
with volume. Apply for pricing access now (developer portal +
JLC3DP API requirements), build the fuller workflow when granted.

## 6. Assemblies, not just parts

A breathing Stone is a small assembly: curved LED PCB (JLCPCB/PCBWay),
BLE + components (assembly), optics/diffuser (JLC3DP/specialist), rigid
enclosure (JLC3D/RapidDirect), silicone shell (moulding supplier), haptics
+ USB-C (procurement), flashing/assembly/QA (own line or contractor). The
agent generates a manufacturing *plan* — cheap printed-shell prototype vs
refined small-batch vs moulded production — each with unit cost, tooling,
delivery and MOQ. JLC, PCBWay, Seeed and Fictiv complement; they don't
interchange.

## 7. MVP in this repo

Phase 1 — quote router: accept STL/STEP/textured OBJ, inspect units/dims/
volume/manifold/walls/UVs/format, produce estimates + real quotes via
supported APIs. Phase 2 — orders: approved JLC (+Sculpteo) APIs, file
hashes, quote expiry, address routing, delivery math, human approval.
Phase 3 — assemblies: BOMs, multi-process parts, fastening, tolerances,
component sourcing, assembly work orders. Phase 4 — agent-native design:
same workflow over MCP so AI revises geometry/materials against
price/finish/delivery constraints. Not yet: a marketplace of fifty
suppliers — three deep integrations beat a directory.

Value prop: "Describe an object. See what it would cost to make. Have it
manufactured."

## Verification ledger (2026-10-09)

CONFIRMED: JLC API platform (PCB+Stencil+3DP+Parts, approval on order
history) + existing 28-tool open MCP; PCBWay partner API (PCB quote/
freight/place/pay/track + SMT quote + balance — PCB only, no 3D/CNC
endpoints listed). OPEN: Sculpteo order-to-address flow, RapidDirect /
Fictiv / Hubs / Xometry customer APIs, Seeed API. The brick WJP order
doubles as JLC API approval history — sequence it before applying.
