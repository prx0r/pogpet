# Provider template stacks — placeholder ↔ label-slot map

> Status: SPEC + staged clients (2026-10-10). Research verdict: Gelato is
> this idea natively; Printify fills via blueprint placeholders; Prodigi has
> NO template/mockup API (dashboard only) so our renderers ARE the stack.
> Provider routing verdict (verified live 2026-10-10): YES, both route.
> Printify lists 2–8 print providers per blueprint (mug: Printify Choice +
> Printed Mint; tee: 8 incl. Choice auto-router) and fills per provider.
> Gelato routes automatically — our US wrap quote fulfilled from its US lab
> via USPS. Our delivery picks are policy on top of their routing.

## The pattern (all three)

Provider template = named slots. Our labels = ranked candidates per slot.
Fill call pins a fileUrl per slot; mockups render provider-side.

| Provider | Template unit | Slot unit | Fill call | Mockups | Client |
|---|---|---|---|---|---|
| Gelato | product template (dashboard) | named image layer, e.g. `DadFace` | `products:create-from-template` + `imagePlaceholders:[{name, fileUrl, fitMethod}]` | background, auto | `backend/gelato.py` |
| Printify | blueprint + provider + variant | placeholder (position + px) | `createProduct` + `print_areas` | API-side, rate-limited | `backend/printify.py` |
| Prodigi | — (none on API) | print area (SKU lookup) | order asset URL at fulfil time | dashboard image editor only | our renderers (`mockup.py`, `wrap_preview.py`, `xmas_card_preview.py`) |

## Slot map (convention — use these names in dashboards)

| Our slot | Gelato layer name | Printify placeholder | Prodigi asset |
|---|---|---|---|
| `face_1` (hero face) | `HeroFace` | front/center at placeholder px | face-box-centred crop |
| `group_1..n` | `Group1..n` | front full-bleed | full photo |
| `solo_1` | `SoloSubject` | front | tile source (wrap) |
| text (name/message) | personalisable text layer | Product Creator text (dashboard) | baked in renderer |

`fitMethod: slice` fills the slot (wrap-style); `meet` keeps the whole
photo (card-style). Face crops ship at ≥800px short edge; wrap sheets at
print-area px (`prodigi.print_area`).

## To go live per product

1. Gelato: build template in dashboard → copy templateId → set
   `GELATO_STORE_ID` → call `fill_from_template` with candidate fileUrls.
2. Printify: pick blueprint/provider → `placeholders()` for px →
   `upload_image` artwork → `create_product`. Needs `PRINTIFY_SHOP_ID`.
3. Prodigi: render with our scripts → order asset URL at fulfil time.
   Carousel on oddhobb.com cycles the same ranked candidates.
