# Factory as a developer product — OddHobb the middleman

Saved 2026-10-09. Parent vision: `docs/factory-vision.md`. Thesis: the
router OddHobb needs for itself is worth more sold to developers than the
figurines are. One normalized manufacturing API; OddHobb takes the spread
and the data.

## Why the middleman wins

Every developer integrating JLC/Sculpteo/PCBWay directly pays the same
three taxes: approval applications per supplier, per-supplier file/quote/
order dialects, and zero historical pricing to estimate against. OddHobb
already paid all three for its own catalogue. Reselling that as one API —
`factory.estimate → quote → compare → order → track`, over REST and MCP —
turns sunk integration cost into a take rate. JLC's own API tiers confirm
the shape: their Ordering API explicitly targets "3D printing trading
companies," i.e. middlemen. We would be the use case they wrote the tier
for.

The personalization compiler is the differentiator Craftcloud-style
compare engines don't have: they route files, we route *products* (locked
interfaces, material rules, proof gates, recipient data). A developer
sending "25 golf markers that say these names" gets manufactured goods,
not a quote form.

## Money

Three stacked revenues: per-quote fee (fractions of a cent at volume,
pays for the estimate tier), take rate on ordered value (the spread
between supplier price and developer price — aggregated OddHobb volume
pushes supplier tiers down while the developer price stays flat), and the
cost model itself (every quoted→ordered pair sharpens `estimated` pricing
until our estimates beat anyone's first quote; that data is the moat).
OddHobb's own shop is customer zero and the reference integration.

## What developers get (v1)

`factory.analyze` (manifold/walls/units/UVs/format verdicts),
`factory.estimate` (our cost model, labelled estimated, never orderable),
`factory.quote` (live supplier prices with expiry), `factory.compare`
(ranked by landed cost + delivery + capability match),
`factory.request_proof` (render/photo before production),
`factory.order` (human-gated, idempotent, file-hash pinned),
`factory.track` (production + shipping status). Auth: per-developer keys
with spend caps — the same `fagg_`-style key model the card MCP already
runs, extended with rate limits and per-order approval webhooks.

## Moat and risks

Moat, in order: quote-history cost model (compounds with every order
across all developers), verified DFM constraints per material
(`jlc_materials.json` + Xometry standards), the personalization compiler,
and Blender-plugin distribution (the designer never leaves their tool).
Risks, honestly: JLC approval gating (mitigated: pricing tier first,
brick order as history); failed-print liability (mitigated: proof gate +
quote-expiry + no-order-on-estimate rule); support burden from developers'
end customers (mitigated: developers own their buyers, our SLA is to the
developer); supplier ToS changes on API resale (mitigated: we are the
customer of record placing real orders, not scraping).

## Sequencing

Dogfood on our own catalogue (quote router live, Phase 1) → apply for JLC
pricing API with the brick order as history → developer beta on estimate+
quote only (no ordering, no risk) → ordering tier + take rate once JLC
approves → Sculpteo second lane → assemblies. Never build the fifty-
supplier directory; depth in three lanes beats breadth.
