# Multi-brand: one codebase, many storefronts

Date: 2026-10-02 · Definitive brands: **oddhobb · grimoirer · stonedoorway**

> Commerce truth: `/root/oddhobbies` · Identity graph: `/root/bgraph`  
> Link map: `/root/oddhobbies/docs/commerce/SITE-LINK.md`

## Why

oddhobb.com is live. New brands use the **same** Flask app + bridge + MCP + premesh.
Brands are a config map + Host resolution — not a fork.

## Definitive brand map

| store_id | Primary host | Alias / note | Commerce packs | bgraph |
|----------|--------------|--------------|----------------|--------|
| **oddhobb** | oddhobb.com | pog.pet | oddhobbies/stores/oddhobb | registry/brands/oddhobb.json |
| **grimoirer** | grimoirer.com | ochema.co (alias) | oddhobbies/stores/grimoirer | registry/brands/grimoirer.json |
| **stonedoorway** | stonedoorway.com | scaffold until thesis | oddhobbies/stores/stonedoorway | registry/brands/stonedoorway.json |

`BRANDS` in `backend/config.py` now includes `store_id`, `commerce_pack`, `bgraph`
so site ↔ commerce ↔ organiser share one key.

## The seam

```
backend/config.py
  BRANDS = { host → { brand, store_id, support, commerce_pack, … } }
  def brand_for(host) -> dict

backend/server.py
  GET /api/brand
  premesh.normalize(..., zone=brand_for(host)["host"])

site/index.html
  window.__BRAND__ + applyBrand()  # boot fetches /api/brand
```

## Domain / tunnel checklist (new brand)

1. Cloudflare zone + NS (done for all three on account `954612…`)
2. Email Routing hello@ / orders@ → Gmail (done)
3. CNAME host + www → figgsite tunnel, proxied
4. Tunnel ingress in `~/.cloudflared/figgsite.yml`
5. `BRANDS` entry in config.py (done for grimoirer + stonedoorway)
6. oddhobbies `stores/<id>/store.json` + packs
7. bgraph `registry/brands/<id>.json`

## Shopify + feeds

- Feed: `GET /backend/api/feeds/shopify.json` (mesh/personalised products)
- Sync: `shopify-app/scripts/sync-catalog.mjs`
- Commerce packs (15 SKUs) sync via `oddhobbies/shop/push_listings.py`
- Unify SKUs later — see SITE-LINK.md

## Money rules

Meshy/paid API always asks first. Ledger `data/meshy_credits.jsonl`.
