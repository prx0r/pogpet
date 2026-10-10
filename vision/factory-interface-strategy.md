# Factory interface strategy (founder, verbatim 2026-10-10)

> The priority isn't winning the AI gadget market with our own products.
> It's becoming the manufacturing infrastructure that AI gadget developers
> use to turn prototypes into sellable products. GlowBase and Living House
> are reference designs proving the pipeline, not the entire business.

## The strategy: build the factory interface, then watch demand emerge

Three parallel operations:

| Operation               | What we build                                                              | Why it compounds                                              |
| ----------------------- | -------------------------------------------------------------------------- | ------------------------------------------------------------- |
| Shenzhen supply network | Verified manufacturers, assembly partners, component suppliers, fulfilment | Every completed order improves pricing and reliability        |
| OddHobb Studio          | Design → simulate → validate → quote → manufacture                         | Makes suppliers accessible to agents and developers           |
| Hardware intelligence   | Track GitHub, Hackaday, Muse gadgets, ESPHome and emerging projects        | Finds proven demand and opportunities for compatible products |

The third operation runs on the Data Gardens pattern: raw snapshots →
normalised facts → changes → opportunity signals.

## 1. Five Shenzhen capabilities first (verified services, not accounts)

| Priority | Capability                                             | Initial partners                        |
| -------- | ------------------------------------------------------ | --------------------------------------- |
| P0       | 3D printing, resin, colour, CNC                        | JLC3DP                                  |
| P0       | PCB fabrication, assembly, component sourcing          | JLCPCB / LCSC                           |
| P0       | Complete electronics integration and programming       | Makerfabs / Elecrow                     |
| P0       | Custom one-off packing, consolidation and shipping     | Shenzhen fulfilment partner             |
| P1       | Specialist optics, acrylic, LEDs, displays, mechanisms | Vetted Shenzhen component manufacturers |

For each partner: can they accept a unique single-custom-part order, what
are minimum quantities, how do they handle defects. A supplier API is not
a supplier relationship — the relationship starts at the first correct
prototype at expected cost and quality. Keep a supplier qualification
ledger: capabilities/materials/MOQs, API/quote/order methods, real costs,
cross-supplier receiving, assembly/flashing/QC ability, rework/refund
policy, known failure modes.

## 2. Hardware-opportunity radar

Monitor developer ecosystems for projects moving from experiment toward
demand (GitHub, Muse SDK, Hackaday, ESPHome, Reddit → stars, forks,
releases, build logs, issues → parts identified, manufacturing friction,
community demand, commercial permissions → supplier match with landed
cost/MOQ/complexity → compatible accessory, creator partnership,
manufacturing template, or ready-to-assemble kit). Example: ten developers
building Muse desktop pets around one Waveshare board → validate a
standard manufacturing template (mounts, speaker chamber, display
opening, enclosure spec) and offer the workflow. Never copy assets or
commercialise without permission — partnerships, accessories, licensed
designs only.

## 3. Business model

1. Standard modules/components (validated cores, light modules, mounts,
   sensor assemblies — reusable inventory, lower friction).
2. Manufacturing as a service (validation, sourcing, fabrication,
   assembly, packaging, delivery for a fee; creator owns/licenses design).
3. Marketplace fulfilment later (validated products, OddHobb produces and
   ships for a transparent fee). Start with 1+2; marketplace after
   suppliers and economics are tested.

## 4. 30-day objective

- Week 1: supplier qualification (JLC, Makerfabs, Elecrow, consolidation;
  API access + assembly/packing terms).
- Week 2: one reference hardware standard (GlowBase mechanical interface,
  BOM, simulator, reproducible manufacturing files).
- Week 3: real quotes + first prototype orders with written QC checklist.
- Week 4: opportunity radar + creator outreach (prototype manufacturing,
  compatible accessories).
- Success = one responsive fabricator, one assembly partner for small
  quantities, one consolidation partner receiving multi-factory parts, one
  manufactured + tested reference product, one true delivered-unit-cost
  quote, one pipeline a creator reuses without custom engineering.

## 5. The fal.ai reference-image transformation pipeline (founder, verbatim)

> we should also allow for pipelines where we can run an image through a
> fal.ai image gen imagine u have an image uploaded, we have the face
> already categorised, we take that face and run it through fal.ai
> reference image to image and then we can have a huge list of reuseable
> prompts to turn it into custom cards and graphics for products e.g. one
> might be make into santa (which would be for wrapping paper) this is the
> true unlock right.. so then we have fal or alibaba and then prompt
> libraries with prompts acting as transformations to give our own
> custom tastefully made products.. then a insane endgame is the user can
> make final edits to the product like make it brown paper or something
> then we use a fal.ai or alibaba image edit... they use their oddhobb
> credits for this which they can get more of by interacting with our
> funnier flow

Design, distilled:

- **Inputs**: uploaded image → categorised face (faces + embeddings we
  already store) → fal.ai (or Alibaba) reference image-to-image.
- **Prompt libraries as transformations**: a huge reusable list where each
  prompt is one tasteful transformation (`make-into-santa`,
  `ornament-badge`, `nice-list-masthead`, …) producing custom cards and
  product graphics in house style.
- **Final edits as image-edit calls**: "make it brown paper" → fal.ai /
  Alibaba image edit on the generated graphic, same pipeline.
- **Credits**: every generation/edit spends OddHobb credits; earn more via
  the funnier flow. Generation is the credit sink that funds itself.
- This is the same engine as cards/prints (face → bounded AI asset →
  deterministic surface) with the generator promoted from ingredient
  supplier to transformation library.
