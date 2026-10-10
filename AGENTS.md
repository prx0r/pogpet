# AGENTS.md — oddhobb / figgsite

> **Start here: `SPRINT.md`** — the current execution focus (packs → cards
> → Prodigi → transformations). Then `HANDOVER.md` (session status).
> This file = map + rules.
> Product truth: `README.md` · studio/custom: `docs/studio.md`, `docs/studio-custom.md` ·
> Etsy packs: `docs/etsy-listings.md` (config `ETSY_LISTINGS`) · money: `docs/meshy.md`.
> **Card invariant: for a personalised card request, the external agent
> supplies person + occasion + vibe. OddHobb chooses and completely executes
> one curated template. The only customer-facing render outputs are FRONT,
> INSIDE, BACK. No external agent may design layout or invoke lower-level
> card composition tools.** Detail: `docs/cardspec.md`.
> **Cards are cardgen-canonical:** `cardgen/` (agent-first generative:
> index → cast → write → generate → QA → spot → upscale → impose →
> freeze) is the card path. The PIL shelf (`backend/card_scenes.py`,
> `recipes/birthday_*`) is the legacy deterministic fallback only — do
> not extend it, do not add PIL templates.

## What this is

**oddhobb.com** — photo (or GLB) in → mesh → products (ornament, keychain,
croc tag, gift card, cards) → optional stage video. Brand is **oddhobb**
(never pogpet / bwick / figg-studio). Live via Cloudflare tunnel; `pog.pet`
is an alias. Repo: **github.com/prx0r/pogpet**.

**Focus now:** products · Blender assets · gift cards · personal Xmas cards ·
Etsy-ready listings · Shopify one-click · agent (MCP) control.
**Parked:** stage/lipsync/standup video (pogtown wedge) — `docs/standup-p0.md`.

## Run it

```bash
cd /home/ubuntu/figgsite
./serve.sh                          # bridge :8797 + Flask :8798
set -a; . ./.env; set +a; MCP_HTTP=1 python3 -m backend.mcp_server   # :8799
cloudflared tunnel --config ~/.cloudflared/figgsite.yml run figgsite
```

Public MCP for ChatGPT/Claude/Muse:
`https://mcp.oddhobb.com/mcp?token=$(cat .token)` — see `docs/mcp.md`.

Bridge token = `.token` (BRIDGE_TOKEN). Flask direct = `API_TOKEN` in `.env`.
Browser only ever holds `window.__FIGG_TOKEN` (bridge-swapped).

## Map

| Path | What |
|---|---|
| `backend/server.py` | HTTP API: photos → meshes → studio → products → orders → etsy |
| `backend/config.py` | STUDIO_LINES / COATS / PATTERNS / HATS · CARD_SIZES · PERSONAL_CARDS · ETSY_LISTINGS · BRANDS |
| `backend/shopify_fulfil.py` | Shopify draft orders (client_credentials + draftOrderCreate) |
| `backend/meshy.py` | Meshy client + stub (ask before every live call) |
| `backend/video.py` | Free vertical videos (edge-tts + PIL); stage/lipsync parked |
| `scripts/render_product.py` | Cycles product stills · `--exact` = no props |
| `scripts/add_jaw_morph.py` | Injects jawOpen morph (freaktown path; pogtown later) |
| `scripts/coat_retexture.py` | Controlled coat patterns (spots/stripes/fairisle) |
| `scripts/xmas_card_preview.py` | Personal card mockups (mesh + text) |
| `scripts/pose_lipsync.py` | Shareable standup bake (parked for oddhobb P0) |
| `site/index.html` | Tabs: chat · studio · products · cards · videos · upload · perform |
| `site/stage.html` | Live jawOpen stage (parked) |
| `pi/.pi/extensions/figgsite.ts` | MCP tools for ChatGPT/Muse |
| `data/` | **gitignored** — sqlite, meshes, productimg, videos |
| `shopify-app/` | Remix scaffold + `scripts/sync-catalog.mjs` |
| `catalog/` | **Product packs: the only way a product goes live** (`catalog/AGENTS.md`, validator `tools/validate_pack.py`, shelf `STATUS.md`) · standard: `docs/product-packs.md` |

## Studio products (controlled custom)

| Line | Price | Size | Props |
|---|---|---|---|
| ornament | £12.99 | 80 mm · loop 5.0 mm | santa / xmas_hat · coats · patterns |
| keychain | £14.99 | 60–80 mm · hole 4.0 mm | coats · patterns |
| **croc_tag** | £8.99 | **28 mm** · printed pin stem | coats · patterns |
| gift_card | £5 / £10 / £15 / £20 (amounts_cents) | digital | — |
| brick | soon | 75 mm | awaiting parent GLBs |

**Policy:** registry IDs only (`config.STUDIO_CUSTOM_POLICY`). No free-form mesh edits.
Coat = preview grade + optional pattern; multi-colour print = live farm quote.
**Never metal hardware** in product photos.

## MCP — what agents can do

Connect: `https://mcp.oddhobb.com/mcp?token=$(cat .token)`

```
figg_pipeline_status · figg_upload_photo · figg_start_mesh · figg_mesh_status
figg_mesh_manifest · figg_studio_state · figg_studio_props · figg_studio_customise
figg_products · figg_product_assets · figg_product_personalise
figg_studio_order · figg_checkout · figg_fullchain_personalise_order
figg_etsy_listing · figg_bricks_status
```

Full chain (ChatGPT / Muse):

```
upload photo → start mesh → mesh_manifest
→ studio_props / product_assets
→ fullchain_personalise_order({line, coat, pattern, hat, qty, fulfil:true})
→ order id + quote + optional Shopify draft
```

`fulfil:true` → `backend/shopify_fulfil.py` draft order. **No card charge** from our API.
Always show price to the customer before checkout tools.

## Keys & money

| Key | State |
|---|---|
| `MESHY_API_KEY` | **set — ASK before every call.** Ledger `data/meshy_credits.jsonl` |
| `SHOPIFY_*` | set — draft orders; tokens expire ~24h |
| `PIXABAY_*` | free stock |
| `GOOGLE_*` | empty — sign-in 501 |
| Cloudflare / R2 | in `.env` only — never print, never commit |

`.env` · `.token` · `data/` — 0600 / gitignored. `git check-ignore` before every push.
Sibling repos read-only. Writes only in **figgsite**.

## Verify

```bash
python3 scripts/test_site.py
curl -s localhost:8798/health
BTOK=$(cat .token)
curl -s "https://oddhobb.com/backend/api/studio/props?token=$BTOK" | head -c 200
curl -s "https://oddhobb.com/backend/api/products/studio?owner=anon&token=$BTOK" | head -c 200
curl -s -o /dev/null -w '%{http_code}\n' https://oddhobb.com/#products
```

## Docs index

| Doc | What |
|---|---|
| `HANDOVER.md` | session progress |
| `docs/todo.md` | current 10 to-dos |
| `docs/mcp.md` | agent connection |
| `docs/meme-engine.md` | meme loop: post → ledger → reweight → site |
| `docs/original-premise-bible.md` | premise quality guide (verbatim founder) |
| `docs/joke-blocks.md` | JokeBlock ontology: blocks, theories, operators |
| `docs/comedy-graph.md` | full architecture spec (verbatim founder) |
| `docs/comedy-os.md` | system inventory + Freaktown/oddhobb relevance |
| `docs/studio.md` | studio + products contract |
| `docs/studio-custom.md` | controlled custom + props |
| `docs/etsy-listings.md` | Etsy packs + sizing |
| `docs/meshy.md` | Meshy money rules |
| `docs/standup-p0.md` | lipsync research (parked) |
| `docs/product-packs.md` | pack = the only way a product goes live; agent outputs; graph next |
| `vision/system-os-verification-gates.md` | system-OS gate notes (dash/influence/qprivately) |

## Brick meshes (user generating)

User is generating parent meshes for **brick** line. Drop GLBs in
`data/uploads/` or send paths. Install via `backend/install.py` or MCP
upload/sculpt. Then flip `STUDIO_LINES.brick.status` → `live` + Etsy pack.
Bricks also feed Videos later (same mesh).
