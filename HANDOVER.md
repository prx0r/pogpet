# HANDOVER — session 2026-10-02 (products · studio · P0 standup)

> **Status: CURRENT** — write-up of everything touched this session.
> **Focus going forward:** products, Blender assets, gift cards.
> Stage / live lipsync / standup video = **parked** (pogtown wedge, not oddhobb P0).
> Detail: `docs/studio.md`, `docs/etsy-p0-p1.md`, `docs/standup-p0.md`.

## Where we are (live)

| Surface | URL | State |
|---|---|---|
| Main site | https://oddhobb.com/ | Running · bridge :8797 · Flask :8798 · MCP :8799 |
| Studio (character select) | `/#studio` | White stage · 3-slot lineup · live GLB · loadout chips · assets grid |
| Products (Etsy tiles) | `/#products` | Lines: ornament · keychain · brick(soon) · one-click order |
| Cards & prints | `/#cards` | PNG mockup tiles (greeting card, mug, poster…) |
| Videos swipe feed | `/#videos` | Vertical scroll-snap feed · light stage bg · audio |
| Exact product photos | `/products.html` | Downloadable 2000px stills + GLB |
| Live stage (PARKED) | `/stage.html` | three.js jawOpen + set editor — **pogtown later** |

Repo: **github.com/prx0r/pogpet** · this session commits:
`a773a7e` studio/products/cards/videos · `0e55e2c` standup polish ·
`17465ee` jawOpen morph + stage · `d901ded` pose-bake video + set editor.

## What shipped (products-focused)

### Mesh → exact product stills (P0)
- Canonical mesh: `data/uploads/chibi-figure-hook.glb` (printed loop in the GLB).
- **`scripts/exact_product.py`** — `--exact` mode: **no props, no metal, no colour grades**.
- Outputs: ornament @ 80 mm + keychain @ 60 mm, white bg, 2000px, QC PASS.
- Public: `/img/prod/prod-*.png`, `/img/prod/kc-*.png`, `/img/prod/chibi-figure-hook.glb`.

### Coat library (P1, free Blender)
- **`scripts/p1_variants.py` / `coat_library.py`** — cream/golden/chocolate/black/fawn/grey.
- Published: `/img/prod/coat-<name>-{hero,front,side,back,loop}.png`.
- Coat = **preview grade** on existing texture — production multi-colour is a live quote.

### Santa hat
- OGA CC0 FBX in `data/assets/hats/oga-santa/`.
- Stills: `/img/prod/santa-*.png` (hero/front/side/back/loop/hang).
- **Publish rule:** only after seat QC on the measured skull (`docs/oddhobb-custom-preview.md`).
- Keychain line does **not** get santa (assets registry).

### Studio system (modular)
- Registry: `config.STUDIO_LINES` / `STUDIO_COATS` / `STUDIO_HATS`.
- Lines carry `assets.hats` / `assets.coats` per product (ornament→santa, keychain→coats only).
- API: `GET /api/studio`, `/api/studio/stills`, `POST /api/studio/customise|order`.
- Products API: `GET /api/products/studio`, `POST /api/products/personalise|order`.
- MCP: `figg_studio_*`, `figg_product_*`, `figg_checkout`.
- Orders table: `orders` → `pending_checkout` (**no charge** until Stripe/Shopify).

### UI
- **Studio:** Wii-style character select (arrows / side thumbs / centre live mesh). No prices.
- **Products/Cards:** Etsy-style tiles. Cards use PNG mockups (`/img/*_70edae28.png`).
- **Videos:** CSS scroll-snap + IntersectionObserver (light RAM). Warm white stage, not black.
- Floating chrome on store tabs (transparent topbar, icons on white).
- Studio **Assets** grid: star / rename / **AI tag people**.

## Stage / video / lipsync — PARKED (pogtown)

**Do not block oddhobb product work on this.**

| Finding | Detail |
|---|---|
| Freaktown no-GPU lipsync | `basic_body.py` emits **`jawOpen` morph**; browser Web Audio → `morphTargetInfluences` (`LipSync.ts`) |
| Our Meshy dog GLB | Had **0 morphs** — freaktown adapter would be `mode: none` |
| Injected morph | `scripts/add_jaw_morph.py` → `chibi-figure-hook-jaw.glb` (+ `/img/prod/`) |
| Live stage | `site/stage.html` — **three.js** GLTFLoader (model-viewer morph API was wrong) |
| Shareable mp4 | `scripts/pose_lipsync.py` — 9 jaw poses + envelope assemble → `data/videos/p0_standup.mp4` (~39s, in feed) |
| Set editor | stage.html lines/voice/name → `POST /api/standup/render` |
| GPU models | Wav2Lip / SadTalker need CUDA — not on this box. P1 later. |

**Decision:** standup/lipsync = **pogtown product** (edit your set → shareable clip). oddhobb keeps the video feed as a thin viewer + existing free video path. Next oddhobb energy = **products, Blender assets, gift cards**.

## R2 / secrets

- New CF token + S3 keys stored in `.env` only (0600, gitignored). **Never print, never commit.**
- Verified: `git check-ignore .env .token data` · staged diffs clean of secrets.

## Products / Blender / gift cards — next

1. **Gift card product line** — new `STUDIO_LINES` entry or cards catalog row; 2D PNG mockup + one-click order.
2. **Blender asset library** — modular props under `data/assets/` (hats, scarves, handhelds) wired into `STUDIO_LINES.assets`.
3. **Production quotes** — attach Prodigi/Makr3D SKUs so prices flip EST → LIVE (`GET /api/prodigi/check?sku=`).
4. **Listing pass** — `render_product.py --size 2000` into figg-studio before-after templates for Etsy/Shopify.
5. **Shopify `model-viewer`** — store token + metafield once Admin API is ready.
6. **Santa seat QC** — eyeball `/img/prod/santa-hero.png`; publish gallery only if it sits.
7. **Stripe/Shopify checkout** — flip `pending_checkout` orders.

## Gotchas

- **No Meshy spend** without asking; ledger `data/meshy_credits.jsonl`.
- **Exact product photos** = canonical mesh only — no metal hooks, no colour grades in the photo.
- **Coat ≠ print SKU** — preview grade; multi-colour is a farm quote.
- **Public MCP** needs bridge token (`.token`); Flask direct needs `API_TOKEN` from `.env`.
- **`/img/*`** serves from `data/productimg/` via bridge — not `site/img/`.
- **Videos feed** public route: `GET /api/videos/feed` (all owners, finished clips).
- **Disk ~90% full** — clean render frame dirs; don’t bulk-download models.
- **No GPU** on this box — Blender CPU only; neural lipsync is cloud/Kaggle later.
- Sibling repos (freaktown etc.) are **read-only**; all writes in figgsite.

## Commands

```bash
cd /home/ubuntu/figgsite
./serve.sh                          # bridge + Flask
set -a; . ./.env; set +a; python3 -m backend.mcp_server   # MCP :8799
cloudflared tunnel --config ~/.cloudflared/figgsite.yml run figgsite

# exact product stills (0 credits)
blender --background --python scripts/render_product.py -- \
  --in data/uploads/chibi-figure-hook.glb --out data/marketing \
  --size 2000 --bg white --shots exact --exact --scale-mm 80

# coat library
python3 scripts/p1_variants.py

# public checks
curl -s -o /dev/null -w '%{http_code}\n' https://oddhobb.com/#products
BTOK=$(cat .token)
curl -s "https://oddhobb.com/backend/api/products/studio?owner=anon&token=$BTOK" | head -c 200
```

## Money

- Meshy: 42 cr spent historically; live balance last seen ~1020. **Ask before every call.**
- Studio/products/orders: **0 credits**. Orders reserve intent only.
- Renders: Blender/CPU only.

## Read first

1. This file
2. `docs/studio.md` — studio + products contract
3. `docs/etsy-p0-p1.md` — Etsy P0/P1 + exact-photo rules
4. `docs/standup-p0.md` — lipsync research + **parked** stage path
5. `docs/oddhobb-custom-preview.md` — coat/hat/customise plan
6. `AGENTS.md` — money rules, sibling-repo boundaries
