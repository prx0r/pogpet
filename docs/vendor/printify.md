# Printify API — imported 2026-10-10

Token: `PRINTIFY_API_TOKEN` in `.env` (verified live: 2,779 blueprints
listed). Client: `backend/printify.py` (staged until `PRINTIFY_SHOP_ID` +
blueprint/provider choice). Base: `https://api.printify.com/v1`, auth
`Bearer`, `User-Agent` required. Rate limits on product/mockup calls
(200/30min). Sources: developers.printify.com, help.printify.com
(Product Creator), OpenAPI (api-evangelist mirror 404 — use official docs).

## What exists

- Catalog: `GET /catalog/blueprints.json` → blueprint {id, title};
  `.../{id}/print_providers.json` → providers; `.../print_providers/{pid}/
  variants.json` → variants with `placeholders[]` {position, width, height
  px} — the fill contract. No separate mockup endpoint: mockups generate
  on product creation (`product.images`).
- Artwork: `POST /uploads/images.json` {file_name, url|contents} →
  media library id. Up to 20 layers per print area (stickers 20);
  low-res uploads auto-enhanced before production.
- Product: `POST /shops/{shopId}/products.json` {title, blueprint_id,
  print_provider_id, variants[], print_areas[]} → sellable product +
  mockups. Publishing endpoint separate.
- Product Creator (dashboard): layers, text editor, all-over-print repeat,
  fit/fill, CMYK preview — the human counterpart of our renderers.

## Wrap findings (live catalog reads)

| Blueprint | Provider | Variants | Placeholder px |
|---|---|---|---|
| 848 Gift Wrapping Paper Sheets | 69 'Prodigi' | 76531 20×28" satin single; 76532 30×36" satin single | front 5906×8268 / 8858×10630 |
| 845 Rolls / 1100 / 1367 | — | — | check per provider |

Printify wrap currently routes to a Prodigi provider — same farm as our
direct SKU. Artwork must ship at placeholder px (~300dpi): our wrap
renderer outputs Prodigi's 2952×4133 (~150dpi), so render `sheet300`
(5906×8268) for Printify and downscale for Prodigi. Variant print costs
are provider-side (need shop context) — pricing staged, catalog verified.
