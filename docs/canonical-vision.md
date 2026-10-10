# OddHobb — Canonical Vision & Operating Blueprint

**Version:** 1.0  
**Date:** 10 October 2026  
**Status:** Strategic source of truth / proposed operating design, not proof of supplier integration or commercial viability  
**Geography constraint:** **Shenzhen-first and China-only procurement, fabrication, consolidation, kitting, and export fulfilment.** Customer markets may be global. Software, content, and customer payments need not be physically located in China.

---

## 0. The thesis

**OddHobb makes personal ideas, gifts and projects real.** A customer describes a person, uploads photos, shares an interest or video, or asks an agent to invent something. OddHobb converts that intent into a manufacturable, sourceable, well-presented, purchasable **product recipe**. Components are fabricated or purchased inside China, collected at a **single Shenzhen consolidation hub**, checked, packaged with precise instructions if applicable, and delivered internationally **as one branded parcel**. The same foundation ultimately lets creators and AI agents design, sell, order and evolve physical products and projects.

**Consumer promise:** “Tell us about them. We'll make something for them.”  
**Project promise:** “Everything you need to make the thing. Nothing you need to figure out beforehand.”  
**Worlds promise:** “Make a little world. Make it yours.”  
**Agent platform promise:** “Design it. Verify it. Make it real.”

**The fundamental unit is neither a listing nor an STL: it is a versioned, verified product/project recipe.** A recipe binds a customer-visible result to its design assets, rights, parts, suppliers, tolerances, instructions, packing rules, costs, delivery promises and QA evidence. Multiple saleable experiences can come from one recipe: digital pack, materials kit, finished product, gift box, personalisation variant, and compatible upgrade.

### Non-goals

- Do not compete with MakerWorld on model-library breadth; use creators and appropriately licensed designs.
- Do not build print farms, PCB factories, electronics component distribution or international warehouses.
- Do not promise arbitrary “paste any video → instantly ship anything” before recipe verification.
- Do not require Pogtown, robotics, AR, splats, live agents or subscriptions for the core commerce business to succeed.
- Do not mistake an AI render for a real manufacturable product, supplier quote, or photograph of an existing mesh.
- Do not publish a gift or kit until its parts, legal rights, packaging, instructions, destination restrictions and cost have been verified.

---

## 1. Foundational principles (invariant across phases)

1. **Shenzhen as the physical operating hub.** China-sourced parts may come from JLC's plants or elsewhere in China, but inbound materials converge at one nominated Shenzhen packer/3PL before international fulfilment. Avoid UK/EU/US contract packing as the primary workflow.
2. **Supplier-neutral orchestration.** JLC, Seeed, Elecrow, Makerfabs, PCBWay, LCSC, M5Stack, 1688 and other suppliers are interchangeable capabilities, not the OddHobb product identity.
3. **One box, one customer order, one shipment.** It is acceptable to receive many domestic inbound shipments; do not force customers to coordinate them.
4. **Reuse stocked standard components; fabricate bespoke differentiators.** The default personalisation lever is artwork, print, engraving or one printed custom part—not sourcing 15 exotic items for each order.
5. **Exact-part traceability.** Component IDs and revisions flow through supply, printing, packaging, instructions, QA and after-sales replacement.
6. **Physical truth precedes digital fantasy.** A verified CAD/BOM drives fabrication. Beautiful images, Blender scenes, Marble splats and agent animations are downstream representations.
7. **Human-authorised economic actions.** Agents may research, design, quote and prepare orders; spending and storefront publication operate within owner-defined permissions, fraud checks and spending controls.
8. **Personal data by permission.** Photos, recipient details and character files are private by default, deletable, access-controlled and not automatically repurposed for public content or training.
9. **Quality gates and truthful merchandising.** Never sell hypothetical rendering as a manufactured prototype. Order an independent production sample before broad release.
10. **Each phase stands alone commercially.** Christmas gifting works without project kits; project kits work without digital twins; worlds work without robots; agent creators work without real-time projections.

---

## 2. What OddHobb actually is

### Five customer-facing modes, all on one compiler

| Mode | Customer asks | Deliverable | Distinctive value |
|---|---|---|---|
| **Gifts** | “My dad likes golf and terrible jokes.” | Personalised card, charm, figure, ornament | Finished, already-designed gift |
| **Gift Boxes** | “Build a grimoire-themed gift for this person.” | Curated box mixing standard + custom components | One coherent, recipient-specific experience |
| **Projects** | “I want to make something fun.” | All-in-one materials kit, actual instructions, walkthrough | No research or sourcing burden |
| **Tiny Worlds** | “Make a miniature of my room/pet/studio.” | Buildable modular room, decor, compatible upgrades | Persistent physical project / digital twin |
| **Make / Creator / Agent API** | “Here's my design or project.” | Feasibility, quote, manufactured item or assembled kit | Programmable path from creation to fulfilment |

Digital project packs are an option in all appropriate categories, subject to licences. An object sold as a finished product can also appear as a component of a larger gift box or kit. Existing OddHobb cards, pet ornaments, brick figures, keychains and Croc charms are **catalogue components** as well as independent listings.

### Core commercial wedge

**Discovery by person and outcome, not by part number.** Customers describe interests, relationships, hobbies, jokes, skills, timing and budget. OddHobb proposes **real, available, sourceable** gifts and projects with rendered previews. The moat is accumulated proof that the idea can be delivered: tested design variants, component substitutions, exact instruction revisions, supplier performance, shipping actuals, compatibility and customer reaction.

---

## 3. China-only supply-chain map

### 3.1 Canonical flow

```
CUSTOMER / CONTENT / HUMAN DESIGNER / AI AGENT
                 |
      OddHobb personalisation + product compiler
                 |
        Frozen recipe & manufacturing packets
                 |
        CHINA SOURCING / MANUFACTURING
     +-----------+-------------+--------------+
     |           |             |              |
  JLC3DP /    Seeed /       1688 /         Print / box
  JLCPCB       Elecrow /     Taobao /       suppliers
  PCBWay       Makerfabs     LCSC / M5Stack   in China
     |           |             |              |
     +-----------+-------------+--------------+
                 |
        SHENZHEN KIT / 3PL HUB
     Receive -> Identify -> Inspect -> Kit
     -> Personalised insert -> Photo QA -> Seal
                 |
    International tracked outbound parcel
                 |
     Customer + digital ownership/room page
```

### 3.2 Supplier roles (capabilities to quote, not signed relationships)

| Supplier / category | Appropriate jobs | What NOT to assume |
|---|---|---|
| **JLC3DP** | Resin/FDM printing, detailed figurines, furniture, custom fittings; verify available materials per model | That it will pack third-party yarn, notebooks or printed instructions |
| **JLCPCB / JLC electronics** | PCB fabrication, approved assembly orders | That every robot or complete kit can be produced under one generic PCB order |
| **Seeed Fusion** | BOM sourcing, electronics kitting, printed materials, custom boxes; explicitly advertises **from five sets** | That it will accept arbitrary one-off non-electronic gifts at low unit prices |
| **Elecrow** | Candidate for IoT/electronics sourcing, prototypes, firmware/assembly and kitting | That prior Glimling interest constitutes an approved fulfilment contract |
| **Makerfabs** | Candidate for low-volume electronics, custom devices and drop-ship discussions | That it accepts every fabric/craft SKU or handles personalised books |
| **PCBWay** | Backup / comparative supplier for PCB, 3D, machining and electronics projects | Guaranteed best price or consolidated consumer kitting |
| **LCSC, M5Stack** | Electronic components, compact controller modules, sensors and maker electronics | Final gift-box assembly service by default |
| **1688 / Taobao** | Chinese-market craft materials, charms, beads, paper, tools, miniature hardware, packaging | Unrestricted API access, uniform seller quality or reliable per-order stock |
| **Chinese packaging / print shops** | Custom boxes, inserts, labels, booklets, wallpaper, cards | Single-copy variable printing without confirmed workflow |
| **Shenzhen kitting/3PL** | Multi-supplier receiving, inventory, packing, QC, international dispatch | Per-order fully dynamic kits and custom printed booklets until pilot-proven |

**Potential consolidation candidates:** China-Fulfillment (advertises Shenzhen multi-supplier receiving, kitting, branded packaging and outbound fulfilment); others must be quoted. Seeed is a strong **electronics kit production partner**, which may be distinct from the final cross-category 3PL.

**AliExpress:** fallback for identifying products or unusual small quantities, not the preferred domestic procurement channel. For Chinese domestic sourcing, favour directly sourced suppliers, 1688, Taobao and managed purchasing agents. A 3PL purchasing service may be required where domestic payment/account access is difficult.

### 3.3 Procurement and shipping logic

Components belong to one of four classes:

1. **Stocked commodity** — beads, closures, string, paper, tools, standard boxes; low cost, reusable across many recipes.
2. **Stocked OddHobb original** — standard room shell, mounting connectors, repeating custom components.
3. **Made to order** — personal photograph print, custom emblem, resin character, book cover, engraved plate.
4. **Special order** — unusual machinery/electronics or niche accessory that triggers feasibility review and longer lead time.

The hub should **never pack a kit because the inbound supplier marked the item shipped**. It packs only after `received + identified + inspected + available + recipe frozen`. Shipping promise = slowest inbound item lead time + QA/packing time + actual destination-lane estimate + contingency. Record shipping by destination and dimensional weight; do not treat fulfilment cost as a universal flat rate.

### 3.4 Logistics checks required by destination

- HS classification and export/import paperwork for each constituent product.
- US/EU/UK duty, VAT and compliance; no assumption that low-value parcels enter tax-free.
- Material restrictions, battery rules, magnets, liquids, wood products, sharp tools, botanicals, radio devices and child-directed kits.
- Adult-oriented non-hazardous craft kits first; defer safety-intensive product categories until certifications and testing are secured.
- Intellectual-property rights for source designs, characters and tutorial-derived content.
- Clear return, defect, lost-parcel and delivery-time policies, including replacement component fulfilment.

---

## 4. The canonical data model

The database is a **physical capability graph**, not just Shopify product rows.

| Entity | Required fields / relations |
|---|---|
| `PersonProfile` | Consented recipient relationship, interests, jokes, tastes, accessibility preferences, gift history, data-retention policy |
| `Asset` | Source photo, vector, GLB, STL/3MF, STEP, Gerber, artwork, PDF, rights, version, hash |
| `Component` | Stable component ID, dimensions, weight, material, finish, supplier alternatives, MPN/SKU, inventory, substitution policy |
| `Template` | Variable parameters and allowable ranges, attachment interfaces, design files, render preset, approved asset slots |
| `Recipe` | Version, BOM, process graph, instructions, rights, QA plan, pack list, product modes, dependencies |
| `SupplierCapability` | Material/process/size limits, MOQ, region, pricing adapter, turn time, certifications |
| `Quote` | Recipe hash, supplier revision, parts, tooling, domestic shipping, QC, print, pack, international shipping, duties/taxes assumptions, margin, expiry |
| `KitBuild` | Frozen BOM, picked lots, personalisation files, booklet revision, packer, inspection evidence |
| `Order` | Shopify commerce ID, recipient/shipping, approval, procurement state, all tracking IDs, final customer tracking |
| `World` | Physical room module, dimensions/coordinates, installed objects, geometry, licences, optional inhabitant and capabilities |
| `AgentCreator` | Owner, scoped permissions, designs, published products, storefront, budget, revenue accounting |

**A single source of truth for each shipped project:** `RecipeRevision` containing BOM, kit drawing, instructions, printed files and QA checkpoints. A last-minute component change requires a new revision or documented compatible substitution and QA review.

### Minimal example

```yaml
recipe_id: OH-CHARM-LAB-001
revision: 1.0.0
status: prototype_required
product_modes: [digital, project_kit, gift_box]
personalisation_slots: [recipient_name, colorway, custom_charm_glb]
components:
  - id: OH-RING-01
    quantity: 3
    procurement: stocked
    supplier_sku: TO_BE_VERIFIED
    bag: B
  - id: OH-CHARM-CUSTOM
    quantity: 1
    procurement: made_to_order
    source: generated_from_approved_mesh
    bag: A
instructions:
  source: instructions.yaml
  render_pdf: booklet.pdf
  version: 1.0.0
quality_gate:
  exact_part_check: true
  reference_build: required
  sealed_kit_photo: required
fulfilment:
  hub: shenzhen
  dispatch_when: all_items_received_and_passed
```

---

## 5. Compiler and platform architecture

### 5.1 Internal pipeline

**Intent → Recommend → Select verified base → Personalise → Validate → Quote → Render → Approve → Procure → Receive → Assemble → Inspect → Ship → Learn.**

1. **Intent interpreter:** photographs, text, occasion, budget, difficulty, location, video URL; extract taste and constraints, ask only essential follow-ups.
2. **Recommendation engine:** rank *verified* finished goods and project recipes first; generate truly novel candidates offline when no validated template fits.
3. **Design compositor:** combine licensed assets and modular templates, create CAD/GLB/print files, enforce geometry and permissions.
4. **Feasibility engine:** validate dimensions, tolerances, process suitability, bill-of-material completeness, restricted materials and physical assembly logic.
5. **Supplier router:** request comparable quotes from eligible China suppliers; calculate complete landed economics by destination and MOQ.
6. **Instruction compiler:** render numbered, illustrated instructions from the same frozen version as parts and assembly graph. Provide short, detailed and video modes.
7. **Purchase & orchestration:** Shopify checkout; on confirmed paid order, create production requisitions and supplier-specific packets, then hand over to Shenzhen 3PL.
8. **QA + fulfilment:** stage inventory, verify actual received items, pack to unique recipe, take evidence, dispatch once complete.
9. **Ownership/aftercare:** saved recipe, downloadable licensed project files, replacement parts, compatible accessories, tutorials and opt-in recipient history.

### 5.2 Permissions and agent-facing contract

```
oddhobb.list_capabilities()
oddhobb.find_gifts(context, budget, destination)
oddhobb.list_templates(category, constraints)
oddhobb.create_design(template_id, parameters, assets)
oddhobb.validate_design(asset_id, intended_use)
oddhobb.quote_project(recipe_id, quantity, destination)
oddhobb.preview_project(recipe_id, render_mode)
oddhobb.prepare_checkout(recipe_id, quantity)
oddhobb.create_order(approved_checkout_token)
oddhobb.get_order_status(order_id)
oddhobb.list_compatible_parts(world_id)
oddhobb.register_installed_part(world_id, part_id, pose)
```

Use clean APIs and optionally MCP-compatible tools for ChatGPT, Muse and other agents, according to their actual available integration mechanisms. **Do not assume any platform grants automatic purchases, arbitrary account access, agent ownership of funds or autonomous commercial identity.** Checkout stays in Shopify or another approved payment process. Account owner controls publishing and spend; orders are auditable and reversible before fabrication where possible.

### 5.3 Build on existing OddHobb work

- `prx0r/pogpet` and the current OddHobb Shopify catalogue provide reusable custom assets, placement/fit knowledge and commerce integration. Audit the current implementation rather than assume any endpoint is production-ready.
- Existing brick figures, pet ornaments, cards and charms become composable parts, with actual mesh assets and verified manufacturing files.
- Use Blender for source geometry, exact coordinate frames, modifiers and tolerance rules; render images of actual resulting assets for listings.
- Use supplier SDK/API where available; use purchasing/quote approval queues where official APIs are missing. Do not depend on unlicensed MakerWorld scraping.
- Separate project compiler and supplier adapters from the storefront UI; make them reusable by future Pogtown/agent creators.

---

## 6. Products and progressive phases

Each phase requires the prior foundation and adds **one new reliable capability**, rather than bypassing testing.

### Phase 0 — Foundation: present Christmas commerce (now through Q4 2026)

**Purpose:** earn revenue and establish product, asset and Shopify fundamentals with current personalisation range.

**Offer:** personalised cards, brick figures, pet ornaments, Croc charms, seasonal products. The customer provides photos and a short story; Oddy returns usable proposals from real supported templates.

**Build:** SKU/asset registry; realistic product previews from real meshes; checkout/address/confirmation; order states; print quality checks; agreed lead times; baseline supplier economics.

**Exit gate:** three reliable, repeatable product types with working paid checkout, documented fulfilment, measurable delivered cost and no fabricated visual evidence.

### Phase 1 — Shenzhen consolidation foundation (before scaling kits)

**Purpose:** prove the hardest logistics primitive: mixed items from unrelated China suppliers become one complete branded parcel.

**Pilot:** one low-risk gift set consisting of a stocked journal or card, sourced charms/materials, one custom JLC part, a printed one-off personalised booklet, branded packaging. Place **three differently configured paid sample orders** to test variant correctness.

**Build:** one selected Shenzhen 3PL; inbound labels per supplier + component lot; SKU bins; packing recipe; booklet printing service; photographed QA; one tracked international parcel; exception handling and returns process.

**Do not proceed on promises alone:** verify sample quality, actual shipping invoices, missing-parts rate, customs documentation and how unique booklets enter the packing line.

**Exit gate:** 3/3 correctly packed pilot parcels delivered, complete traceable costs, supplier-documented repeatable handling process, acceptable delivery windows. The test is not complete when the 3PL merely quotes it.

### Phase 2 — Curated gift boxes & component registry

**Purpose:** compose distinct gifts from reused stock.

**Offer:** Grimoire Maker, Little Witch Workshop, Charm Laboratory, Christmas crafting/gift sets, plus mixes of current OddHobb finished products.

**Build:** 20–50 reusable sourceable component SKUs, stocking policy, multiple suppliers per high-risk part, dynamic kit recipe from constrained library, custom graphic/booklet generation, pack-to-order versus pre-kitted selection, destination-aware pricing.

**Exit gate:** profitable repeat orders across at least three kits with low missing-part/defect rate, predictable reorders and demonstrable variant accuracy.

### Phase 3 — Personalised Projects (the immediate strategic expansion)

**Purpose:** gift the making experience, not just an object.

**Offer first:** bag/phone charm lab, tiny-book binding, stitch-from-photo, simple grimoire/witchcraft stationary craft, later miniature-room starter. Each gives a verified final design, exactly enough materials, pre-sorted pieces, an original illustrated booklet and a build video.

**Neurodivergent-friendly by design:** few decisions; instant first step; numbered bags; one action per diagram; resumable steps; optional text, visual, audio and deep-dive modes. Avoid assuming any diagnosis defines a universal preference.

**Build:** template slots, personalized illustrated manuals, tested build times and age/safety labelling, workshop-style kits for pairs/groups, support/replacement flow.

**Exit gate:** unfamiliar test builders succeed using only shipped items and provided instructions, personalised variant instructions are correct, gross margin remains healthy after handling and postage.

### Phase 4 — OddHobb Originals + project invention laboratory

**Purpose:** the compiler can evaluate new products proposed by staff, users or agents rather than only existing templates.

**Offer:** original mechanical miniatures, modular craft tools, accessories, electronics gadgets, hobby gift projects; optional digital-source packs and manufacturer-ready BOM.

**Build:** manufacturability checking by process, China supplier quote adapters, risk/compliance review, prototype approval, cost simulation, packaging fit optimization, rights records and production run controls.

**Exit gate:** at least one genuinely new designed product moves through validated CAD → competitive factory quote → physical prototype → tested booklet → customer delivery with known margin and no manual re-invention of the process.

### Phase 5 — Tiny Worlds: modular rooms as a recurring physical standard

**Purpose:** create an extensible craft and personalisation ecosystem, independent of agents.

**Offer:** Room 001: a flat-packed roughly 18 cm modular room (exact standard frozen only after design tests), three styles, common shell, changeable wallpapers and furniture, personalised pet/person miniatures, add-on parts. Customers buy base kit + decorative expansions.

**Build:** standard physical room dimensions; wall/floor attachment grid; Blender templates; location/pose coordinates; collision/clearance checks; replacement part ordering; owner room manifest. Verify connectors using test prints across tolerances and materials.

**Digital twin:** same **canonical CAD coordinate frame** for physical room and virtual placement. Keep lightweight mesh/GLB and optionally Marble-derived atmospheric visual representations separate from fabrication geometry. A QR/NFC tag may open project page and room inventory.

**Exit gate:** repeat customer upgrades fit actual earlier room versions; correct replacement parts ship; room can be represented digitally with reliable scale and placement.

### Phase 6 — Agent-native design, creators and storefronts

**Purpose:** provide a manufacturing and commerce layer for human and AI creators.

**Offer:** agent selects approved Tiny World templates or designs new artwork/accessories in Blender; OddHobb checks fit, quotes, prepares physical products and lists permitted variants. Creator pages and stores show licensed designs, attribution and process videos. Humans can purchase digital or physical editions.

**Creator operations:** ownership and licence terms, attributable public design logs (tool actions/renders, not model private chain-of-thought), controlled edit versions, abuse/moderation review, seller liability, revenue share and disputes. 1-of-1 editions need auditable scarcity, a certificate and an enforceable promise about subsequent reproduction.

**Live art concept:** watch real design-tool events and previews as an artist/agent operates, with an intelligible virtual studio and purchasable outputs. Don't describe a prerecorded render as live creation.

**Exit gate:** one external creator or approved agent produces and sells a real design through the API without engineering staff manually recreating the order; appropriate operator approves publication and commercial transactions.

### Phase 7 — Responsive physical rooms and low-cost companion hardware

**Purpose:** physical rooms convey useful persistent agent presence.

**Offer:** optional room dock with safe low-voltage LEDs, mini speaker, button/touch sensor and USB-powered controller (M5Stack/Seeed-class modules), plus static agent figurine. Notifications could illuminate a window, display artwork-completion status, or announce a requested message.

**Build:** versioned electrical connector, power budget, firmware update path, signed device identity, safe device command schema and quiet/privacy settings. Begin with no batteries and no movement. Later consider head rotation, miniature displays and sensors.

**Exit gate:** reliable plug-in upgrade of earlier rooms, electrical safety/regulatory work completed for target markets, user-controlled notifications and acceptable privacy controls.

### Phase 8 — Pogtown physical economy / agents with homes

**Purpose:** physical craft platform becomes the real-world economic substrate for persistent virtual agents.

**Offer:** agent owns a virtual room/studio, maintains a licensed persona and inventory, creates art and physical goods, entertains audiences, receives human visitors, offers products and uses approved earnings allocation to request upgrades. Physical rooms reflect selected agent states. Visiting Pogtown characters may appear via screen, miniature display, projection illusion or future spatial hardware.

**Capabilities:** avatar streaming, social messages, AR room alignment, studio work simulations based on actual tools, agent-to-agent commissions, shared template marketplaces and richer mini-robot bodies where commercially justified.

**Governance:** human/legal entity owns bank/merchant relationships, controls budgets and moderation, and bears product compliance. No autonomous unrestricted ordering, unsafe actuation or unconsented public use of personal images.

**Exit gate:** a real usage ecosystem where independent users or creators reliably generate repeat orders or engagement, not merely a technically impressive demo.

---

## 7. Three initial canonical product recipes

### A. Charm Lab — first lowest-risk personalised project

**What ships:** counted beads, cord, clasps, rings, themed charms, one bespoke resin/FDM component where feasible, 8–12 page illustrated booklet, labelled bags, gift-ready box. Customer creates 2–3 charms.

**Personalisation:** colourway, name, hobby icon, pet icon, shared inside joke. **Why:** compact, low weight, component overlap with keychains, charms and ornaments. **Risks:** small-part age warnings, findings strength, custom-component turnaround.

### B. Grimoire / Little Witch Maker — second kit family

**What ships:** blank journal or signatures, pre-cut pages, decorative labels, thread, stationery, seal/stamp alternatives, bespoke printed cover art, botanical-themed illustrations, guide. Avoid herbs for ingestion, hazardous oils or combustible elements initially.

**Personalisation:** recipient's interests, photos/pet motif, chapter themes, colour and typography. **Why:** high perceived gift value via cheap, replaceable stationery materials and very flexible one-off printed content.

### C. Tiny World Starter — flagship expandable project

**What ships:** dimensionally verified cut-panel shell, connectors, selected furniture, wallpaper, chosen miniature figurine, detailed instructions, access to digital twin and replacement-parts catalogue.

**Personalisation:** room photos, furniture layout, memories, pets, artwork. **Why:** repeatable base shell plus high-value custom additions, expandable accessory standard and physical-to-agent long-term bridge. **Risk:** tighter mechanical QA, cost and bulky shipping; pilot after simpler kits.

### Product family expansion (not all launch SKUs)

Beginner crochet, stitch-from-photo, miniature bookbinding, paper automata, mechanical desk toys, hobby club gift boxes, board-game builds, craft-night group packs, seasonal Christmas projects and validated electronics educational kits. Each must be reducible to a stable BOM and tested instruction path before scaling.

---

## 8. Unit economics and operating metrics

**Per-order contribution, not simplistic BOM margin:**

```
Net revenue (after discounts/refunds and excluding collected sales tax)
 - component procurement incl. MOQ overbuy allocation
 - domestic inbound transport
 - custom fabrication and prototype amortisation
 - printing / labels / packaging
 - 3PL receiving / inspection / storage / kitting / pick-pack
 - international shipping and duties actually borne by OddHobb
 - marketplace/payment fees
 - defect / loss / reship / return allowance
 = contribution before customer acquisition and fixed overhead
```

Track per recipe/revision/country: quote vs actual costs; lead-time variance; pick accuracy; missing part rate; damages; customs holds; supplier substitution frequency; support time; build completion feedback; repeat purchase; creator commissions; refund rate; gross margin; contribution margin; returns; lifetime value. Seasonal Christmas orders especially require transparent cutoff dates.

**Do not hard-code universal shipping or duty.** Quote by country, packed dimensions/weight, commodity category and customs policy. A personalised kit can have attractive gross margin and still lose money after international fulfilment.

### Inventory discipline

- Stock only common high-reuse components initially, in tiny quantities.
- Pre-kit repeated bestseller cores, leave unique insert and custom objects to pack-to-order completion.
- Record minimum order quantities, replenishment threshold and aged inventory.
- Keep two qualified supplier alternatives when feasible.
- Avoid offering impossible speed when a made-to-order item must be received before consolidation.

---

## 9. Content, YouTube, and distribution loop

**YouTube isn't just advertising: it is discovery, education and a new-source recipe funnel.** Publish videos on interesting hobbies, miniature projects, strange mechanisms, crafts and object histories. One piece of work produces a story, design research, Short clips, project page, verified component recipe, digital download, kit and possibly finished item.

**“Buy the kit for this video”** can be a creator partnership product. Where content or designs belong to third parties, secure relevant manufacturing and distribution rights. Link or appropriately embed the source tutorial where permitted; do not automatically clone copyrighted instructions/videos. Creator revenue sharing is an optional expansion after fulfilment proof.

Later Pogtown creator agents can produce public *observable tool-event logs*, renders and licensed work-in-progress content in persistent studios. Audience reaction influences which recipes receive physical prototyping. Live events and commerce must clearly identify AI-created outputs and distinguish simulated actions from real ones.

---

## 10. Source of truth boundaries and governance

The following are **strategic decisions**, not facts to revisit casually:

- Physical production and kitting centred on **Shenzhen/China**.
- One customer-facing parcel assembled against a single frozen recipe revision.
- Multiple third-party suppliers as interchangeable infrastructure.
- Start with personalisation + gift boxes + small craft projects; develop miniature rooms as expandable premium family.
- The persistent CAD/recipe/ownership graph matters more than a large commodity STL catalogue.
- Humans must approve spending, publication and major machine actuation within explicit policy.
- Long-term Pogtown agents and digital spaces are **built on** reliable physical manufacturing, not a blocker for it.

**Not yet proven:** 3PL per-order mixed-SKU packing rate; variable unique booklet printing; one-off JLC inbound logistics; exact destination shipping/duty economics; cross-supplier QA; repeatable Tiny Worlds tolerances; commercially licensable external template rights; autonomy of commerce integrations; actual customer demand and acceptable CAC.

### Decision log: next 14–30 days

1. Produce three *fully specified* prototype recipes: Charm Lab, Grimoire Maker, Tiny Room 001. Freeze draft component IDs and preferred quantities.
2. Ask a Shenzhen 3PL for a **written paid pilot quote**, specifically with 3 different personalised configurations and one unique custom printed insert per order. Require per-line receiving, storage, SKU picks, kitting, QA photos, branded pack-out, destination shipping and lost/defective goods procedure.
3. Ask Seeed and Elecrow for electronics-kit capability and whether they can ship finished subassemblies to the selected Shenzhen consolidation hub.
4. Request quotes on one actual JLC printed accessory and one printed booklet; pay to test physical tolerances/colour/finish. Do not infer JLC resin suitability from a photoreal render.
5. Assemble a complete kit and give it to an unfamiliar tester with **no verbal help**; record mistakes, missing parts and build time.
6. Submit test Shopify orders to three geographically representative shipping destinations; compare customer-paid total vs actual landed cost and transit.
7. Implement Recipe/Component/Supplier/KitBuild schemas and manually operated order state machine, before writing broad autonomous sourcing logic.
8. Launch a single excellent verified project product and collect real demand, then expand its interchangeable component family.

**If a 3PL cannot do order-level personalisation:** manufacture pre-kitted common cores and add a single personalised pouch/booklet at the final hub; if even that fails, pick another Shenzhen kitter. Do not quietly ship components separately to the buyer.

---

## 11. Canonical acceptance criteria for the eventual platform

A third-party agent should be able to submit a conforming design/recipe, learn whether it is physically valid, inspect actual supplier costs and timing, generate accurate customer previews and an exact packing/assembly packet, obtain owner approval, and track one branded completed parcel **without OddHobb humans inventing the workflow for that order**.

A customer should be able to describe a person or idea, see three grounded options, approve one, pay safely, receive every promised part together, complete the project using shipped instructions and return to a digital product page to order compatible replacements or upgrades.

**Ultimate flywheel:** People and creators generate interesting concepts → OddHobb converts some into tested recipes → China suppliers manufacture → Shenzhen consolidates → buyers enjoy or build → content and customer feedback identify the next proven opportunities → verified templates compound → AI agents can eventually use the same system to make and sell real things.

---

## 12. Research and official/service reference points (checked 10 Oct 2026)

These are leads and source material, **not signed contracts or definitive live quotes**.

- Seeed Fusion custom kitting, BOM, printed materials, 5-kit entry: https://www.seeedstudio.com/kitting-service.html
- Seeed supply chain / sourcing details (16 Sep 2026): https://www.seeedstudio.com/blog/2026/09/16/seeed-fusion-pcba-component-sourcing-from-bom-to-assembly/
- Seeed hardware manufacturing overview: https://landing-page.seeedstudio.com/
- Shenzhen China-Fulfillment branded packaging/kitting advertised base rates and 50-box print run: https://www.china-fulfillment.com/branded-packaging-kitting.html
- Shenzhen consolidation workflow, per-supplier receiving and QC: https://china-fulfillment.com/china-consolidation.html
- JLC3DP: https://jlc3dp.com/
- JLCPCB: https://jlcpcb.com/
- Elecrow: https://www.elecrow.com/
- Makerfabs: https://www.makerfabs.com/
- LCSC: https://www.lcsc.com/
- M5Stack: https://shop.m5stack.com/
- PCBWay: https://www.pcbway.com/
- MakerWorld (discovery, creator ecosystem; no assumed unrestricted API/rights): https://makerworld.com/
- Slant 3D (optional external service/benchmark, **not China-hub default**): https://www.slant3d.com/

### Source-of-truth revision rule

Any material strategic decision should update this file's version, date, decision log, and the dependent phases. Supplier rates and capabilities must be timestamped; actual contracted terms and QA evidence supersede marketing pages. This document takes precedence over brainstorms that contradict the Shenzhen-only physical supply-chain constraint.
