# Template engine — ours, with three adapters

> Status: LIVE (2026-10-10). Module: `backend/template_engine.py`.
> Tests: `tests/test_engine.py`.

One template = slots against OUR labels + one payload per provider.
Providers: Gelato fills named layers (`HeroFace`) by fileUrl;
Printify pins artwork into placeholder px; Prodigi takes an order asset
our scripts render. Full map: `docs/provider-templates.md`.

## Registry

- `wrap_solo` — 1 hero solo (min 800px) → WRAP-1-50X70 / blueprint 848
  front 5906×8268 / Gelato `HeroFace`.
- `trio_card` — 2 groups + 1 face (the funny template) → 5×7 card SKU.
- `photo_card` — 1 good solo → card SKU.

## Rules

- Fill walks the ranked pool best-first; `min_px` is print truth — too
  small falls through to the next candidate, never a silent upscale.
- Distinct photos across slots; `subjects` filter scopes every slot
  (shopping for Cathy → her family).
- Shortfalls honest (`face 0/1`, `too small for print (400x400)`).
- Artwork fileUrls stage until crops publish; coordinates exact today.
- Renderer: `render_trio` (PIL, 0 credits) proves the layout with real
  photos before any provider call.
