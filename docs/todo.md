# OddHobb — the 10 (Round 9 · 2026-10-03)

> **Focus:** Etsy P0 listings online · pack downloads · brick line shelf.
> **Paused:** golf props (`docs/props-workbench-golf.md`) · stage/lipsync (pogtown).
> **Brand:** oddhobb only.

## The 10

| # | To-do | Status | Notes |
|---|---|---|---|
| **9-1** | **Etsy P0 stills 2000px: ornament + keychain + brick** | **in progress** | Blender chain running → `data/marketing/` + `data/marketing/brick/` |
| **9-2** | **Etsy pack zip + /img/etsy/** | pending on 9-1 | `scripts/etsy_pack.py` maps orn/kc/brick → pack |
| **9-3** | **Brick on products.html + studio page** | **done** | studio lineup dog+brick · Use brick button · products section + GLB |
| **9-4** | **ETSY_LISTINGS.brick copy live** | **done** | config.py · £19.99 · 75 mm · tags/title |
| **9-5** | Brick GLB public at `/img/prod/brick-figure.glb` | pending | copy after stills QC |
| **9-6** | Coat/santa **template library** (dog variants) | queued | stills already in `/img/prod/coat-*` + `santa-*` — need listing wiring |
| **9-7** | Brick variant templates (props like golf) | parked | `docs/props-workbench-golf.md` |
| **9-8** | Gift-card tier mismatch (£10/25/50 vs Etsy £25/50/100) | open | align config before live gift-card listing |
| **9-9** | Shopify customer checkout URL | open | drafts work; link missing |
| **9-10** | Commit batch when owner says push | open | figgsite working tree only |

## Etsy P0 — what “online” means here

1. **Listing assets ready** — 2000px white stills + zip under `/img/etsy/` on oddhobb.com.
2. **Machine-readable listing pack** — `GET /api/etsy/listings` (titles, tags, sizes, photo slots).
3. **Human upload** — owner pastes into Etsy (or we wire an API later). We do **not** have Etsy OAuth on this box; P0 = assets + copy ready to paste.

### Shot contract (unchanged)

| Line | Mesh | Size | Hardware in photo |
|---|---|---|---|
| Ornament | `chibi-figure-hook.glb` | 80 mm | printed loop; hang shots may show printed S-hook prop |
| Keychain | same, smaller | 60–80 mm | printed ring only — **no metal** |
| Brick | `brick-figure-01a0feb8-….glb` | 75 mm | **exact — no props** |

### Commands

```bash
# already kicked off (see /tmp/opencode/render_*_2k.log)
blender --background --python scripts/render_product.py -- \
  --in data/uploads/chibi-figure-hook.glb --out data/marketing \
  --size 2000 --bg white --shots marketing --sat 1.45

blender --background --python scripts/render_product.py -- \
  --in data/uploads/chibi-figure-hook.glb --out data/marketing \
  --size 2000 --bg white --shots keychain --variant keychain --sat 1.45

blender --background --python scripts/render_product.py -- \
  --in data/uploads/brick-figure-01a0feb8-7c26-7796-be37-b6fddb09d772.glb \
  --out data/marketing/brick --size 2000 --bg white --shots exact --exact --scale-mm 75

# after renders
cp data/marketing/brick/prod-*.png data/productimg/prod/brick-*.png  # rename below
cp data/uploads/brick-figure-*.glb data/productimg/prod/brick-figure.glb
python3 scripts/etsy_pack.py
curl -s "https://oddhobb.com/api/etsy/listings?token=$BTOK" | head
```

## Tab contract (locked)

| Tab | Owns | Does not own |
|---|---|---|
| **quick** | Mic ramble → confidence → paths | Product shelf UI, paper cards |
| **products** | Studio 3D + gift card + prints/gifts + mesh inherit + one-click Shopify | Ramble/Quick funnel UI |
| **cards** | **Paper stationery only** + personal card form | Mugs, cushions, 3D figures |
| **upload** | Photo → mesh → active star | Commerce |
| **studio** | Character select / loadout | Checkout |

## Money / agent

- Meshy spend: human must approve. P0 Etsy stills = **0 credits**.
- Orders: `POST /api/products/order` `{fulfil:true}` → Shopify draft (no card charge from API).
- MCP: `figg_etsy_listing` · `figg_fullchain_personalise_order`. Show price first.

## Delegation (how we split next)

| Track | Do now | Later | Blocked on |
|---|---|---|---|
| Etsy P0 assets (orn/kc/brick stills + zip) | **this session** | — | Blender CPU time |
| Listing copy/API | config + `/api/etsy/listings` | Etsy OAuth if we automate | owner shop access |
| Template library (coats × hats × brick props) | after P0 pack live | registry IDs + still grids | P0 done |
| Golf props polish | parked | one QC pass | `docs/props-workbench-golf.md` |
| Live Etsy paste/upload | owner | — | pack zip on site |

## Done this round

- [x] Brick line status → live · mesh installed from R2 `svatantrya`
- [x] R2 credentials verified (already in `.env` + rclone `r2:`)
- [x] `ETSY_LISTINGS.brick` added
- [x] `scripts/etsy_pack.py` rewritten for orn/kc/brick + zip
- [x] `products.html` brick section + Etsy pack UI
- [x] **Brick on studio page** — lineup dog + brick-demo · portrait · GLB · “Use brick figure” installs `style:brick-figure`
- [x] **Brick on shop** — products/studio returns live brick line + stills + `glb_url`
- [x] Public assets: `/img/prod/brick-figure.glb` · `/img/prod/brick-hero.png`
- [x] Golf props process documented (paused)
- [ ] 2000px Etsy stills finished (orn/kc/brick renders running)
- [ ] Pack zip published + verified over tunnel
