# Controlled custom — coats, hats, gift cards, MCP chain

> Status: LIVE scaffold (2026-10-02). **Controlled custom only.**
> Free-form mesh edits stay blocked. Agents pick from registries.

## Policy

`config.STUDIO_CUSTOM_POLICY`:

| Allowed | Blocked |
|---|---|
| `coat_color` (registry ids) | arbitrary mesh edits |
| `coat_pattern` (solid/spots/stripes/fairisle) | unlisted hats/patterns |
| `hat_id` (none/santa/xmas_hat) | free text decals (until live) |
| `line` · `qty` · `amount_cents` (gift card) | inventing SKUs |

## Prop library

| Kind | IDs | Assets |
|---|---|---|
| **Hats** | `none` · `santa` (OGA CC0) · `xmas_hat` (Khodrin) | `data/assets/hats/**` |
| **Coats** | none + cream/golden/chocolate/black/fawn/grey | material grade on texture |
| **Patterns** | solid · spots · stripes · fairisle | Blender shader presets (`scripts/coat_retexture.py`) |

Coat patterns are **retexture previews**, not print SKUs — multi-colour is a live farm quote.

## Product forms

| Line | Fulfilment | Props |
|---|---|---|
| `ornament` | print farm | santa / xmas_hat + coats + patterns |
| `keychain` | print farm | coats + patterns (no hat) |
| `gift_card` | digital | amounts £10 / £25 / £50 |
| `brick` | soon | — |

## API

| Method | Path | Does |
|---|---|---|
| GET | `/api/studio/props` | machine-readable hats/coats/patterns/lines + asset exists |
| GET | `/api/meshes/<id>/manifest` | machine-readable mesh view for agents |
| POST | `/api/products/personalise` | validate combo → stills + price |
| POST | `/api/products/order` | reserve order; `fulfil:true` → Shopify draft |

Shopify: `backend/shopify_fulfil.py` — client_credentials token + `draftOrderCreate`.
No card charge from our API. Creds in `.env` only.

## MCP (full chain)

```
figg_upload_photo → figg_start_mesh → figg_mesh_manifest
       ↓
figg_studio_props  (or figg_product_assets)
       ↓
figg_fullchain_personalise_order({line, coat, pattern, hat, qty, fulfil})
       ↓
order id + quote + optional Shopify draft
```

Also: `figg_studio_state` · `figg_product_personalise` · `figg_checkout`.

## Blender retexture

```bash
blender --background --python scripts/coat_retexture.py -- \
  --in data/uploads/chibi-figure-hook.glb \
  --out data/marketing/patterns \
  --coat chocolate --pattern spots --size 900
```

Outputs `data/productimg/prod/coat-<coat>-<pattern>-hero.png` when published.

## Hats

| Hat | Path | Licence |
|---|---|---|
| santa | `data/assets/hats/oga-santa/santa_hat.fbx` | CC0 (OpenGameArt) |
| xmas_hat | `data/assets/hats/khodrin-christmas/christmas_hat.fbx` | edit + redistribute |

Seat on measured skull before store gallery (`docs/oddhobb-custom-preview.md`).

## Next

- [x] Publish pattern stills to `/img/prod/` (partial — chocolate spots + golden stripes)
- [x] Coat × santa combo stills via r3d (cream/golden/chocolate/black) — **2026-10-03**
- [x] MCP `figg_studio_retexture` + `figg_studio_combos` + `GET /api/studio/combos`
- [ ] Gift card digital delivery (email code)
- [ ] Shopify draft scopes: `write_draft_orders`
- [ ] Coat multi-colour print quotes
- [ ] Santa seat: **geometry OK** (r3d proves brim on skull). Cycles product path still blooms the white brim — use r3d or fix lights before publishing Cycles santa stills
- [ ] P1 photoreal lipsync (pogtown) — not this path

## Retexture via MCP (live)

```
figg_studio_props()                          # registry ids
figg_studio_combos()                         # pre-rendered still sets
figg_studio_retexture({line,coat,hat,pattern})
  → stills + available combos + price
figg_fullchain_personalise_order(...)        # personalise + order
```

HTTP: `POST /api/products/personalise` · `GET /api/studio/combos`

Coat = preview grade. Santa hat = procedural seat on measured skull
(`scripts/santa_seat.py`, brim_r=0.022 at y=-0.107 z=0.145 on the
canonical dog). OGA FBX floats on this mesh — do not use for store stills.
Blender 4 torus: use `major_radius`/`minor_radius` (abso_* kwargs ignored).
