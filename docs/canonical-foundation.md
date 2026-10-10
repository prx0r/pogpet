# Canonical foundation: cards → physical AI agents

Saved 2026-10-10. Rule: every product is a versioned recipe, every
supplier advertises capabilities, every order compiles into a fulfilment
plan. Start with the £2.99 card; end with custom agent-linked hardware —
same commerce/design/asset/ordering infrastructure throughout. Adjustment
adopted: Shenzhen is the SOLE consolidation hub for multi-component
products, NOT the production site for simple POD (Prodigi's network is
faster/cheaper direct; v4 API: lookup, quote, order, sandbox, callbacks).

## 1. Product ladder (complexity, not departments)

1. Cards + print (now) · 2. Single manufactured gifts (now/next) ·
3. Curated gift collections (next) · 4. Project packs (next) ·
5. Custom assemblies + Tiny Worlds (expansion) · 6. Interactive physical
(hardware) · 7. Agent devices + robots (endgame). Each stage adds ONE
manufacturing primitive. Milestone 1 = stage 3: unrelated products, one
personalised box.

## 2. Seven canonical objects → our modules

| Object | Ours | Gap |
|---|---|---|
| Asset | photos/meshes/GLB/PDF + rights | STEP/Gerber coverage |
| Component | components.py registry | dims/weight/lead-time per line |
| Capability | suppliers.py + project_check lanes | quoted-vs-verified flags |
| Recipe | RECIPES/GIFT_RECIPES + run-states | version freezing, revision field |
| Configuration | template fills + Personalisation | occasion/budget ranking pass |
| Fulfilment plan | delivery.py + quotes/compare | Mixam live client |
| Instance | backend/objects.py (rooms/podiums) | QR/NFC print + owner transfer |

Gift collections nest recipes (Christmas box → card + ornament + grimoire
pack). Lifecycle enforced: concept → design_validated → supplier_quoted
→ sample_tested → production_approved → purchasable (rights + validation
gates in code, not AI judgement).

## 3. Routing (delivered-cost equation lives in delivery.py)

Delivered = parts + inbound + assembly + packing + outbound + duties +
risk. Slowest part sets the schedule — computed BEFORE Shopify checkout.
Integrations grow per stage (cards: Prodigi+Shopify … robots: PCB +
testing + certification).

## 4. Committed stack

Storefront + Shopify (existing) · Postgres later (SQLite now) · Python +
versioned JSON schemas · InvenTree later (registry now) · pogpet
personalisation · Blender + build123d · SVG/PDF templates · per-supplier
adapters behind one API · MCP + REST/OpenAPI agents · GLB + manifests +
optional Atlas splats · ESP32-class hardware later. Compiler = separate
service eventually; IP = verified-design/component/supplier/assembly/
result relationships.

## 5. Agent APIs (ours mapped)

Shopping: recommend (guide funnel) · list types (products/studio) ·
configure (templates/fill) · preview (triptych/render) · quote
(quotes/compare) · checkout (checkout endpoints) · track (orders/track).
Creation: capabilities (suppliers) · templates (registry) · validate
(design/validate + feasibility) · compile (projects/check, gifts/compile)
· quote/prototype/approve/publish (staged: approval + spend gates).
Robots later: validate_electronics, compile_firmware, test plans,
provisioning. No autonomous spend on general instruction — explicit
limits, permissions, prototypes, approvals.

## 6. Podium verdict (adopted)

No podium needed to place AR (ARKit plane detection does tables). The
podium must earn itself: persistent identity + defined stage + giftable
object + optional ambient electronics. Default: any OddHobb product can
be an AR anchor (OddHobb Anchors: ID via QR/NFC + dimensions + coordinate
frame + scene ref). Podium = one product on the platform. Tiers: passive
£9–19 → light £25–39 → live £49–89. Launch: Podium 001 passive,
deterministic CAD (never splat→print), JLC prototype, phone recognition
proof, then messages/visits/voice.

## 7. Foundations A–F → status

A canonical assets/products: site + Shopify + GIFT_RECIPES nesting.
B supplier capabilities: 27-entry registry, quoted-vs-verified next.
C executable recipes: cards/ornaments/collections one schema.
D pricing + jobs: destination quotes, idempotent runs, tracking live.
E assembly packs: BOMs, booklet PDFs, packing sheets, QA checks.
F persistent instances: backend/objects.py + resolve + event states.
Milestone: £2.99 card as canonical recipe + sandbox order against the
Shopify order → ornament second route → Christmas collection combining
both (direct vs consolidated correctly routed).

## 8. Endgame

Discover (people/occasions) + Make (components/CAD/costs/assembly/Shenzhen)
+ Worlds (objects/spaces/AR/twins). Brands as customers. Ladder: cards →
objects → collections → kits → rooms → devices → robots. Immutable now:
recipes, capabilities, instances. Podium 001 + remembered-place pilots
when Phase-0 exits.
