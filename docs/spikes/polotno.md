# Spike: Polotno SDK vs card_service (2026-10-11, ~30 min)

## Result: keep our renderer. Revisit if visual template design bottlenecks.

## Proven (headless, polotno 4.15.3 from npm)

- Store JSON round-trip works with zero browser: create page (1270x1780 =
  5x7 @10x), add `headline` / `punchline` / `inside_message` text
  placeholders, substitute approved joke values, read back valid JSON.
- Integration shape fits `card_service`: Polotno JSON is template data,
  slot values are service data. Pin the JSON + values to the revision;
  checkout flow untouched.

## Costs found

- License: 60-day eval free, then subscription required for ANY production
  use (even internal tools). Pricing is quote-only ("low hundreds to
  20-30k+"), monthly/annual. No self-serve tier.
- Render path: print-size export needs browser canvas or Polotno cloud
  render (extra). Our `impose.py` already emits Prodigi-size masters.
- Our P0 need is 3 text fields on fixed art — served today by the
  deterministic renderer + `set_slot`. Polotno buys a visual editor we
  don't need until non-technical staff design templates.

## Revisit when

- Template design (not joke writing) becomes the bottleneck, or
- a visual admin editor is requested by name.
