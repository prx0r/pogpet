# HANDOVER — next session: companion launch + Dot standup shareables

> **Status:** companion ingestion shipped (`9cdc3ea`). Screenshot sources,
> multiview clients, print split, rig spec, dot_standup preset all live.
> Watermark-domain bug fixed (was 500ing every video).

## Next steps

1. **"Bring your AI to life" onboarding** — screenshot upload UI copy +
   flow (upload → meet in 3D → Pogtown vs physical choice). Backend ready.
2. **First companion mesh** — needs Meshy spend approval: multiview
   prototype (6cr) → multi-image build (30cr) on a real Dot/Muse screenshot.
3. **Dot-standup distribution** — share links + watermarked feed clips;
   pogtown performer binding per `docs/character-rig.md`.
4. **Print side** — repair API call before `export_print_bundle`; first
   jibbit/keyring from a companion mesh; MAKR3D sample per thesis rule.
5. **Still open from before** — first splat (comedy night) needs
   `MARBLE_API_KEY`; wind indicator geometry; HF_TOKEN for Qwen voices.

---

# HANDOVER — next session: first splat (comedy night)

> **Goal:** generate the first Marble room (comedy night) and wire it as the
> greeting/episode venue. Then, in order: presidential speech, sports press
> interview, red carpet, talkshow.

## Prereqs (nothing stored yet)

- `MARBLE_API_KEY` (platform.worldlabs.ai, NOT the Marble app). $5 min pack.
  Ask-first + `data/marble_credits.jsonl` ledger per `backend/marble.py`.
- Client: `backend/marble.py` already speaks generate/poll/export/balance.
- Docs mirrored: `~/marble-docs/` (pricing, generate/get/export, SPZ scale
  formula, Blender import via KIRI/Reshot).

## Room queue (one $1.20 gen each, plain marble-1.1, text prompt)

1. **comedy night** — brick wall, spotlight cone, mic stand, empty stool.
2. **presidential speech** — curtain, generic flags, wooden podium (parody-safe).
3. **sports press interview** — sponsor wall (ODDHOBB/MAKR3D/PET FC), table edge.
4. **red carpet** — step-and-repeat wall, rope barrier, flash glow.
5. **talkshow** — desk, two chairs, warm practicals, skyline backdrop.

Draft ($0.15) first for composition, full build once, reuse forever.
Metric scale metadata → seat meshes at true size (formula in marble-docs).

## Wire-up after generation

- Backdrop PNG into `data/rooms/<id>.png` (rooms endpoint reports live).
- Splat via KIRI/Reshot into Blender for mesh-inside lighting tests.
- Greetings/episodes take `room=` already — no API changes needed.

---

# HANDOVER — session 2026-10-04 (wearables engine · masters hunt)

> **Status: CURRENT** — wearables v2 engine installed + proven; masters are
> the blocker. Prior session below (2026-10-02) is background.
> **Focus going forward:** premium santa/jacket masters → v2 product proofs.

## Wearables engine (installed from R2, additive only)

- Source: `r2:blog-video-assets/uploads/oddhobb-wearables-engine.zip` (28 KB,
  reviewed module-by-module: clean, no network/secrets in runtime path).
- Installed at repo root: `wearables/` (target/headwear/garment/prop/
  hardware/QC/compiler/runner), `scripts/wearables_{cli,register,seed_demo}.py`,
  `tests/test_manifest.py`, `docs/wearables-engine.md`, `INTEGRATION_SNIPPET.py`.
  Its pytest passes; brick + demo-candle + cake-spikes smoke compose works.
- Two engine bugs fixed in-tree: garment solver pushed shells 5–30 mm INSIDE
  (hull winding + added normal-free clearance guarantee in
  `wearables/garments.py`); engine's own head socket sat on the forehead, so
  `data/anchors/chibi-figure-hook.wearables.json` carries our proven seat
  (ring z≈0.196, rest +7.3 mm).
- Proven end-to-end (`/tmp/opencode/oddhobb-xmas-v2.glb`): hat PASS (rest
  +8.6 mm, sunk 0.4%, 0 poke), jacket PASS (0.15% inside). Renders confirm.

## Masters hunt — hat: yes (flawed) · jacket: nothing free found

- **Santa hat: OpenGameArt CC0** (Lucian Pavel) downloaded direct, cleaned,
  registered at `data/assets/wearables/santa_hat/master.glb` (procedural
  master backed up to `/tmp`). Verdict: wrong proportions for the dog
  (tall floppy cone towers) + imperfect texture — usable placeholder, NOT
  premium. Meshy gallery (Santa Hat 67 etc.) is auth-walled; Poly Pizza is
  bot-walled.
- **Jacket: no free isolated dog garment exists** after searching Meshy,
  Poly Pizza, OpenGameArt, CGTrader (paid), Gumroad (email checkout),
  Sketchfab (account), itch.io, Tripo (AI-gated). Realistic routes only:
  (a) owner browser-downloads a Meshy CC0 hat/garment, or (b) approve Meshy
  API generation spend (box key present, balance last seen 942, untouched).
- **Key hygiene:** a Meshy key + R2 credentials appeared in chat. Neither was
  stored (verified: no history file, no /tmp strays, nothing in git). One
  stale Oct-3 `/tmp` key backup from a prior session was found and deleted.
  Data masters + overrides live under gitignored `data/`. Rotate any
  chat-pasted credentials in their dashboards.

## Still live from before

- Fit editor (`site/fit.html` + `/api/fit/placement`) and all 16 fixed
  cream-era product GLBs from the rollout remain live; suite 77/77.
- Stale product stills PNGs + same-URL browser cache items from
  `docs/fit-problems.md` are unchanged.

## Next

1. Land premium santa + jacket masters in `data/assets/wearables/`.
2. Re-run engine compose → verifier → renders.
3. Then: re-render stale stills, `?v=` cache-bust, retire procedural masters.

## Update 2026-10-04 (OGA santa master fitted)

- OGA CC0 hat cleaned (correct `UVMap` layer + texture), registered as
  `santa_hat/master.glb`, `fit.ease` solved to 0.70 for uniform 0.35 scale,
  socket z 0.187 in the chibi override. Engine composes it cleanly.
- Product `/tmp/opencode/oddhobb-xmas-v4.glb` is CORRECT in 4 rendered
  angles (hero/side/back/top): floppy cone, brim on crown, pompom attached.
- Caveat: verifier hat-mode FAILs it (ring-band heuristics assume a torus
  brim; floppy geometry breaks them). Poke-through count is 0 and all
  angles are clean — metric needs a floppy-hat update, product is good.
- Jacket master still open (procedural shell passes; no free premium
  garment found — Meshy gen or owner download).
- **Cribbage pegs (BOARDGAME-PIECES-SET): full mesh hunt exhausted.**
  Thingiverse/Printables/Cults/Sketchfab need logins, yeggi/3dgo/3dsearch
  bot-wall, CGTrader is paid, Gumroad needs email checkout, OGA has nothing.
  Verdict: pegs are lathe-profile hardware — generated 3 exact-spec masters
  in Blender instead (shaft O3.0–3.2 mm sliding fit for 1/8 in holes, all
  manifold, print-ready): `peg_classic` (taper+collar+ball),
  `peg_ball` (oversized ball), `peg_topper_mount` (10 mm cup for a mini pet
  bust = the personalisation slot). Registered as wearables `hardware` via a
  new generic `static_master` generator (`wearables/hardware.py`), proven in
  a dog+santa+peg compose. No free isolated dog jacket exists anywhere
  reachable — jacket master still needs Meshy gen (spend approval) or an
  owner browser download.

---

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

1. **Controlled custom (IN PROGRESS)** — coat colour + pattern, hat ids, gift card
   form, MCP full chain. Spec: `docs/studio-custom.md`.
2. **Gift card** — live line `gift_card` (£25 default; £10/£25/£50). Digital fulfilment.
3. **Blender asset library** — hats already: OGA santa + Khodrin xmas_hat under
   `data/assets/hats/`. Patterns via `scripts/coat_retexture.py` (spots/stripes/fairisle).
4. **Production quotes** — attach Prodigi/Makr3D SKUs so prices flip EST → LIVE.
5. **Listing pass** — `render_product.py --size 2000` into figg-studio templates.
6. **Santa seat QC** — eyeball `/img/prod/santa-hero.png`; publish gallery only if it sits.
7. **Shopify checkout** — draft orders via `POST /api/products/order` `fulfil:true`
   (`backend/shopify_fulfil.py`). Creds already in `.env`; needs `write_draft_orders`.
8. **Pattern stills** — `coat-chocolate-spots-hero.png`, `coat-golden-stripes-hero.png`
   published under `/img/prod/`.

## MCP full chain (agents)

```
upload photo → start mesh → figg_mesh_manifest (machine-readable mesh + props)
→ figg_studio_props / figg_product_assets
→ figg_fullchain_personalise_order({line, coat, pattern, hat, qty, fulfil})
→ order + optional Shopify draft
```

Custom is **controlled**: registry ids only (`config.STUDIO_CUSTOM_POLICY`).

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
