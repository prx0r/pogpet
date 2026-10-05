# Vision — products as AI design contracts

Our listed products are not inventory. They are **templates with rules** —
the motif structures an AI designs inside of. Every product declares what is
non-negotiable (interface geometry, fit, scale, printability) and what is
personalizable (name, face, motif, colour, message), and the AI creates
within exactly that space.

## The contract (all JSON, machine-readable)

```text
product
├── non_negotiable   interface + fit + scale (the engineering that must hold)
├── personalizable   zones + methods + limits (where love goes)
├── suppliers[]      cost + shipping + materials per farm, per country
└── recipient        who it's for, what they love, budget, deadline
```

Example — clog charm:

```json
{
  "product": "clog_charm",
  "non_negotiable": {"post_dia_mm": 5.0, "retention": "Jibbitz-fit",
                     "max_dims_mm": [30, 30, 12]},
  "personalizable": {"zones": ["top_face"], "methods": ["relief", "text"],
                     "max_chars": 10},
  "suppliers": [{"farm": "makr3d", "material": "PETG", "unit_cost": 1.20,
                 "ships": ["UK"], "colours": 40}],
  "recipient": {"name": "Dad", "interests": ["golf"], "budget_cents": 1000}
}
```

The AI never guesses what fits, what it costs, or who it's for. It designs
the perfect gift inside true constraints: supplier capabilities, real
shipping, available materials, the loved one's profile, the budget.

## Why this wins

- **Design freedom with guardrails:** infinite personalization, zero
  unprintable outputs. Validation is the same gate as manufacture.
- **Supplier-aware creation:** costs and shipping per farm per country are
  inputs to design, not surprises at checkout. The customer sees true
  landed cost before anything renders twice.
- **Recipient-aware creation:** interests pick motifs, occasions pick
  products, budgets pick scope. Every output is already *for someone*.
- **Compounding catalog:** each template makes every future gift better.
  Twenty templates today is twenty thousand gifts by Christmas.

## Status

Live in parts: canonical format v1 carries dims/weight/material/supplier
(`backend/config.py`, `factory_registry.json`); supplier registry with
landed estimates (`backend/suppliers.py`); multi-supplier live quotes next.

## House rules (2026-10-05)

- **Suppliers stay invisible.** No farm name ever reaches the storefront —
  the API serves capability summaries (materials, colours, dispatch range),
  routing happens server-side. Shoppers customise freely; we pick the optimal
  physical implementation and propose adjustments ("make it this big") when
  close to a better fit.
- **Remix pays $1, always.** Designing with someone else's mesh adds a flat
  $1 royalty to the original designer at checkout. The bank of community
  designs accrues from these — provenance-gated before anything prints.
- **Consumer-first.** Most people never touch Blender and never should. The
  parametric/advanced path exists for agents, Dots and power users via MCP;
  everyone else gets ramble → packs → checkout.
- **No-commitment ordering.** Every farm takes qty 1 with no relationship —
  API to demand, they ship. Verified per supplier (`can_single_order`).
- **Creators submit, we accept.** Community products arrive with provenance,
  we accept or reject, royalties flow at $1. Simple core catalog stays
  designed in-house; the bank grows by curation, not by upload firehose.
