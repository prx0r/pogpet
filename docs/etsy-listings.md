# Etsy listings — packs + sizing

> Patterns from **prx0r/oddhobbies** (`shop/ETSY-SETUP.md`, `docs/KILLER-PRODUCTS.md`,
> `docs/ALL-PRODUCTS.md`) applied to OddHobb pet products.
> Source of truth: `config.ETSY_LISTINGS` · cards: `config.PERSONAL_CARDS` ·
> sizes: `config.CARD_SIZES` + `docs/balance.md`.

## Listing formula (from oddhobbies)

```
Personalised X | Custom Y | Gift | Accessory | Use-case
```

Photo slots (adapted from ETSY-SETUP 10-slot strategy):

1. Hero 2. In-use 3. Scale 4. Variants 5. Detail  
6. Packaging 7. **Size diagram** 8. Personalisation example 9. Bundle 10. Mesh/3D still

## Our SKUs

| Product | Price | Size | Etsy title pattern |
|---|---|---|---|
| Ornament | £12.99 | 80 mm · loop 5.0 mm | Personalised Pet Ornament \| Custom Dog Christmas Bauble \| … |
| Keychain | £14.99 | 60–80 mm · hole 4.0 mm | Personalised Pet Keychain \| Custom Dog Keyring \| … |
| **Croc tag** | £8.99 | **28 mm** · pin stem 12 mm | Personalised Pet Croc Charm \| Crocs Tag Pin \| … |
| Gift card | £25+ | digital | OddHobb Gift Card \| eGift Card \| Instant Delivery |
| Xmas card | £3.99–9.99 | A6 / 5×7 / A5 | Personalised Pet Christmas Card \| Custom Dog Xmas Card \| … |

## Sizing (print truth)

| SKU | Height | Hardware | Weight (est) |
|---|---|---|---|
| Pet core | 80 mm | — | 50–120 g |
| Ornament | 80 mm | loop ID 5.0 / wire 2.4 | 50–120 g |
| Keychain | 60–80 mm | hole 4.0 + printed ring | 30–80 g |
| **Croc tag** | **28 mm** | printed pin stem Ø12 mm | 3–8 g |
| Brick | 75 mm | — | 80–150 g |
| Cards | A6 105×148 · 5×7 127×178 · A5 148×210 | — | — |

Details: `docs/balance.md` LOCKED production sizes.

## Cards (personal)

Templates in `config.PERSONAL_CARDS`:

| Id | Message | Source |
|---|---|---|
| merry_xmas | Merry Xmas | mesh still + text |
| happy_holidays | Happy Holidays | mesh |
| thank_you | Thank you | mesh |
| happy_birthday | Happy Birthday | mesh |
| real_photo | Merry Xmas | **customer PNG/JPEG** |

Preview: `python3 scripts/xmas_card_preview.py --template merry_xmas --size 5x7`

## API (planned / partial)

| Endpoint | State |
|---|---|
| `GET /api/etsy/listings` | planned — return `config.ETSY_LISTINGS` |
| `GET /api/etsy/listing/<id>` | planned |
| MCP `figg_etsy_listing` | planned |
| Products tab sizes | partial — on studio lines; cards need UI |

## Shopify

- Catalog sync: `shopify-app/scripts/sync-catalog.mjs`
- Orders: `POST /api/products/order` `fulfil:true` → draft order
- Listing titles/tags can feed Shopify product upsert later

## Listing factory (subjects x lines -> packs)

`scripts/listing_factory.py --fixture demo --line ornament` (or `--all`)
compiles `data/listings/<line>/<fixture>/` with a 10-slot pack
(hero, before_after, lifestyle, detail, scale, variants, process,
measurements, second_person, packaging) + `listing.json` + `listing.md`.
Slots without source imagery record `todo` with a reason — draft media,
never fake media. `--publish` refuses unless `production == verified`.

Fixtures live in gitignored `data/fixtures/<name>/photos` (real people need
real permission — never commit photos). `dad`/`mum` await owner photos;
`demo` proves the pipeline. Recipes: `backend/listings.py` (method must
equal the line's real personalization method). Preview API:
`GET /api/products/<line>/preview?subject=` — same images power the site
tile, Etsy, Shopify and agent previews.

Status is split: `status` (catalog visibility) + `production`
(sample_pending/verified) + `etsy` (draft/live). Etsy-live requires
verified fit/manufacturing; drafts allowed before.
