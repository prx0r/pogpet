# OddHobb: invention, personalisation and fulfilment engine

Not a shop selling manually-designed things. Two complementary
businesses on the same Shenzhen supply chain:

1. **OddHobb Originals** — we invent new products, test whether suppliers
   can manufacture them economically, and list the successful ones.
2. **OddHobb Personalised Packs** — AI composes existing products, craft
   materials and bespoke components into a gift for a specific person.

## The complete model

Product invention (AI designs object/kit/gadget) → gift personalisation
(AI learns interests, composes gift) → Product Compiler (validated
designs, component recipes, costing, packaging, illustrated instructions)
→ Shenzhen manufacturing and fulfilment (JLC, Elecrow, Makerfabs, Seeed,
1688, kitting partner) → one beautiful box.

Unlocks: curated gift boxes (grimoire set from interests), personalised
creative projects (bespoke pack + guide), original manufactured products
(agent-designed desk light/gadget — CAD, electronics, costs and assembly
checked before production).

## Engineering decision: component first, product second

Greeting cards, figures, ornaments, keychains, Croc charms are all
eligible components in larger packs — as are third-party parts. Example:

```
gift: "The Little Witch"
recipient: {interests: [cats, tarot, journaling]}
components: [blank_journal, custom_cat_emblem, decorative_charms,
  botanical_art_cards, paper_and_binding_materials,
  personalised_instruction_booklet]
fulfilment: {hub: shenzhen, packaging: oddhobb_gift_box, shipping: consolidated}
```

Every component needs supplier, landed cost, stock, dimensions, weight,
lead time, packing. The compiler decides viability — a £30 gift with £8
materials but £22 postage is NOT viable, however good it looks.

## Sequence

1. Shenzhen component registry (source + cost) — live: backend/components.py
2. Gift recipe compiler (stocked + bespoke) — live: recipes + postage rule
3. Supplier quote adapters (validate feasibility) — live: prodigi/slant,
   staged: gelato/printify
4. Branded box assembly (one parcel) — staged: partner RFQs
5. Personalised booklet generator — live: scripts/booklet_preview.py
6. Product invention pipeline (feasibility score gates agents) — live:
   backend/feasibility.py

Start: three verified recipes (Charm Lab, Grimoire Maker, Tiny Room
Starter); personalisation varies only across compatible, sourceable
components. Internal feasibility score rates manufacturing cost,
availability, assembly, safety, shipping and margin — agents explore
without auto-publishing impractical designs. Long term: creator/agent
says "manufacture 20 kits from these files" → quotes → tested prototype
→ production after approval. Christmas kits fund the robotics vision —
same suppliers, inventory and compiler throughout.
