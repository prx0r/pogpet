# OddHobb Shopify app

> Native Shopify app (official Remix template) + the catalog sync that makes
> Shopify the canonical store — per `docs/GTM-STRATEGY.md` (read-only inspo,
> not vendored here).

## What this is

- **`shopify-app/`** — stock Remix template (`shopify app dev` / `deploy`
  work as documented), with two OddHobb additions:
  - `shopify.app.toml` scopes: `write_products,read_products` (read is
    needed so sync matches existing products by handle instead of duplicating)
  - `scripts/sync-catalog.mjs` (+ `npm run sync:catalog`) — pulls our public
    feed and upserts every product: title, description, vendor, type, tags,
    variant price, and the product image on first creation.

## Connect

> **Auth reference (no secrets):** `docs/shopify-auth.md` — Dev Dashboard apps
> don't show a copyable `shpat_` token; we exchange client_id + client_secret
> for a 24h Admin API token via `client_credentials`. `atkn_` tokens are
> CLI-only and cannot call Admin GraphQL.
 it (needs two values from the user)

1. **Store domain**: your `xxx.myshopify.com` (dev dashboard store 238339879).
2. **Admin API token**: Store settings → Apps → Develop apps → create app →
   scopes `write_products`, `read_products` → Install → **Admin API access
   token** (`shpat_…`). (Or link this project to a Partners app and use
   `shopify app dev`, which mints tokens via OAuth instead.)
3. Preview without touching the store:
   `SHOPIFY_STORE=x SHOPIFY_API_KEY=x SHOPIFY_API_SECRET=x npm run sync:catalog -- --dry-run`
   (reads our live feed, prints CREATE/UPDATE lines, changes nothing).
4. Run it: `SHOPIFY_STORE=… SHOPIFY_API_KEY=… SHOPIFY_API_SECRET=… npm run sync:catalog`
   (script mints a 24h admin token via client_credentials; no copyable token in the UI)

## Mapping (feed → Shopify)

| feed field | Shopify field |
|---|---|
| `title` | product title |
| `handle` | handle (idempotency key — existing handles are updated, never duplicated) |
| `body_html` | description |
| `vendor` | always `OddHobb` |
| `product_type` / `tags` | catalog section (cards/gifts/…) |
| `variants[0].price` | variant price, GBP (EST, same as storefront) |
| `images[0].src` | product media, added on first creation only |

EST prices sync as-is on purpose — the storefront shows identical figures,
so feed and shelf never disagree. When Prodigi SKUs go live, quotes flow
through automatically (feed prices come from the same source).

## Known limits

- Product images come from our public `/img/` URLs (no token). If an image
  fetch fails, the product is still created — check the script output.
- No order webhooks yet; the app is catalog-sync only. Orders/fulfilment is
  the next integration after this proves out.
- `shopify app dev` / `deploy` need Partner login + `client_id` in
  `shopify.app.toml` (run `shopify app config link`, or pass `--client-id`).

## Lightweight 3D previews on Shopify (researched 2026-09-30)

What the ecosystem actually does — and what we adopt (cheap end):

| Pattern | What it is | Weight | Verdict |
|---|---|---|---|
| **model-viewer + metafield** | `<model-viewer>` loads a GLB/USDZ URL from a product metafield (`custom.model_3d_url`); AR Quick Look (iOS) + Scene Viewer (Android) are built into the element | ~15 KB JS, CDN | **adopt** — Dawn ships this pattern; our feeds already give it public image URLs, next step is GLB on public R2 + the same metafield |
| Shopify **3D/AR media** (native) | Upload GLB/USDZ to Admin → Files, product gets a3D media card | zero code | adopt for SKUs we control; Shopify hosts the asset |
| `ecommerce-3d-mcp` (GitHub, MCP) | agent tool that emits the Liquid snippet + metafield setup + schema.org 3D metadata | MCP tool | pattern reference only (repo URL from search didn't resolve; snippet format is documented in the search results) |
| Theme App Extension 3D viewers (iJewel WebGI etc.) | replace Dawn's product-model.js wholesale with a custom WebGL engine | heavy | **skip** — maintenance trap for us |

**Repo read (cloned `brennan252/Immersive-Product-Display`, 520K):** the
Theme App Extension pattern is one Liquid snippet — `<model-viewer ar=""
ar-modes="quick-look scene-viewer webxr" camera-controls src=... ios-src=...>`
with a poster slot ("Load 3D Model") and an AR button slot, reading Shopify's
**native product 3D models** (`models[0].sources | where format == "usdz"`).
That is the cleanest public example: no custom WebGL engine, no paid SDK —
the viewer IS Google's model-viewer, AR modes are free. We adopt this exact
shape; our source is the Meshy-hung GLB (plus PNG poster from the same
Meshy task, already in `data/productimg/`).

**Our lightweight path (what the sync already enables):**
1. `sync:catalog` creates products with our public `/img/` images (done).
2. Next: upload the **hooked GLB** (`data/uploads/chibi-figure-hook.glb`) to public R2, expose via `/img/` or direct R2 URL — public, no token, same rule as product images.
3. Set metafield `custom.model_3d_url` per product (sync can write it via Admin API when we add `metafields` to the productCreate mutation).
4. Theme snippet: one `<model-viewer src="{{ product.metafields.custom.model_3d_url }}" ar camera-controls>` — iOS/Android AR free, no SDKs.

Muse/ChatGPT agents get the same surface already: `figg_catalog` returns the same products, `llms.txt` documents the feeds, MCP exposes print/measure. The3D viewer is a Shopify *presentation* concern — the contract stays identical.
