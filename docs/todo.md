# OddHobb build — the 10

> **Round 6 (2026-09-30): audit fixes — owner-sig, rate limits, tests 64/64.**
> Round 5 below.

## Round 6 progress (same day)

| Item | Status |
|---|---|
| Owner-sig session model (`POST /api/session`, write/read gates) | done — named owners need sig or API key; anon/pog_* demo path open |
| Login + signup rate limiting | done — 5 fails / 15 min → 429 |
| Email UNIQUE partial index | done — `idx_users_email_unique` |
| Watermark + feed links per-brand | done — `config.watermark_brand()`, `_public_base()` |
| Bridge security headers + X-Owner-Sig/X-API-Key forward | done |
| Turntable exceptions logged | done |
| MCP signs only `FIGG_OWNER`; no arbitrary impersonation | done |
| Test soft-pass removed (figg_flow must parse real payload) | done |
| `docs/trademark.md` | done |
| README status refresh | done |
| `BRIDGE_TOKEN` pinned in `.env` (restarts stable) | done |
| Shopify dev store sync (13 products, GBP) | done — see `docs/shopify-auth.md` |
| Still open: token-in-page-source (R6-2 full), PUBLIC_BASE flip, ochema NS, dash/pi split, data-deletion endpoint, commit | pending |

> **Round 5 (2026-09-30): multi-brand seam + ochema.co.**
> Prior rounds below it.

## Round 5 — multi-brand + ochema.co (2026-09-30, latest)

| # | To-do | Status |
|---|---|---|
| R5-1 | **Brand config map** — `config.BRANDS` + `brand_for(host)` (www strip, subdomain inherit, safe default), `DEFAULT_BRAND_HOST` | done |
| R5-2 | **`GET /api/brand`** — per-request Host answer; unknown hosts fall back, never error | done |
| R5-3 | **Frontend repaint** — `initBrand`/`applyBrand` on load; title, boot/greeting/topbar marks, section labels, AI prompt line all server-driven; no hardcoded brand strings | done |
| R5-4 | **Per-host premesh zones** — `normalize()` now uses `brand_for(request.host)["host"]`; staged sources live on the serving zone | done |
| R5-5 | **ochema.co edge** — CF zone created, CNAMEs + tunnel ingress added, seamless rollover, pog.pet verified 200; email rule queued | done |
| R5-6 | **Docs** — `docs/multi-brand.md` (structure spec + ochema steps + Shopify3D pattern) | done |
| R5-7 | **Shopify/3D preview research** — reference clone of `brennan252/Immersive-Product-Display`; adopted model-viewer + native product media pattern in `shopify-app/ODDHOBB.md` | done |
| R5-8 | **Tests extended** — brand_for + /api/brand checks in `scripts/test_site.py` | done |
| R5-9 | **ochema.co zone ACTIVE** — blocked on user pasting NS at Namecheap (`gina`/`pete.ns.cloudflare.com`) | blocked |
| R5-10 | **Real Shopify sync** — blocked on `SHOPIFY_STORE` + `SHOPIFY_ADMIN_TOKEN` from user | blocked |

> **Round 4 (2026-09-30): agent compatibility — product feeds,
> llms.txt, native Shopify app.** Verification at the bottom of this file.
> Prior rounds below it.

## Round 4 — feeds + Shopify app (2026-09-30)

| # | To-do | Status |
|---|---|---|
| R4-1 | **Public product images** — bridge `/img/` route + `data/productimg` mirror (marketing assets only; feeds need token-free images) | done |
| R4-2 | **Google Merchant Center feed** — `GET /api/feeds/google.xml`, ungated, 13 items, GBP, section-shelf links | done |
| R4-3 | **Shopify-shaped feed** — `GET /api/feeds/shopify.json` mirroring `/products.json` | done |
| R4-4 | **llms.txt** — `site/llms.txt` for shopping agents (catalog, feeds, MCP, contact) | done |
| R4-5 | **Native Shopify app** — official Remix template in `shopify-app/` (no nested git), scopes `write_products,read_products` | done |
| R4-6 | **`sync:catalog`** — feed → Shopify upsert by handle, `--dry-run`, fail-fast auth check, `ODDHOBB.md` connect guide | done |
| R4-7 | **Muse/ChatGPT compat** — MCP already standard streamable HTTP (Round 1 verified); llms.txt documents the token-URL pattern | done |
| R4-8 | **Docs: GTM inspo noted** (read-only clone, not vendored), HANDOVER + BUILD_NOTES updated | done |
| R4-9 | **Tests extended** — feeds, llms.txt, shopify-app structure in `scripts/test_site.py` | done |
| R4-10 | **Full suite green** — see Verification log | done |

## Round 3 — storefront + my.space (2026-09-30)

| # | To-do | Status |
|---|---|---|
| R3-1 | **Kill the double rail** — remove `.seclrail`; one nav layer only | done |
| R3-2 | **Amazon top bar** — logo + search + account/cart, fixed above content | done |
| R3-3 | **Persistent category strip** (All/Board games/Gifts/Cards/…) under the bar, registry-driven; in-shop chips removed (declutter) | done |
| R3-4 | **Search** — top-bar field filters the shop grid, combines with section filter | done |
| R3-5 | **Section blurbs** in config → strip/panel copy updates per section | done |
| R3-6 | **my. copy rebrand** — kill "pog" wording: Your star / people & pets / add someone | done |
| R3-7 | **Autosort into people** — `photos.person` column + dHash clustering endpoint + rename ("who's this?" → saved to profile) | done |
| R3-8 | **my. layout** — spotlight superstar + uploads grouped by person chips | done |
| R3-9 | **cards.oddhobb.com first test** — cards hero/section pass + end-to-end | done |
| R3-10 | **Docs + full test re-run** (`test_site.py` extended for the new surface) | done |

---

| # | To-do | Status |
|---|---|---|
| 1 | **Unified catalog** — one registry in config (products + sections + emoji/blurb), served by `GET /api/catalog` | **done** |
| 2 | **Flow endpoint** — `GET /api/flow` returns upload→mesh→previews as a state machine (empty/uploaded/sculpting/ready) | **done** |
| 3 | **Cards driven by the registry** — site fetches `/api/catalog` at boot and overrides inline EMOJI/BLURB fallbacks | **done** |
| 4 | **Previews refresh on mesh success** — when a sculpt lands, an open shop re-renders every product preview (status cache reset included) | **done** |
| 5 | **MCP manifest** — `TOOL_AREAS` is the single registration point; add a tool = one row | **done** |
| 6 | **MCP covers the whole loop** — `figg_catalog`, `figg_flow`, `figg_start_mesh`, `figg_upload_photo`, `figg_tools` → 20 tools | **done** |
| 7 | **Sandbox-safe MCP upload** — path resolve + prefix containment inside `FIGG_UPLOAD_DIR`, multipart to `/api/photos` | **done** |
| 8 | **`docs/foundation.md`** — how to add a product / tool / section, flow contract, verification | **done** |
| 9 | **Flow-driven shop UX** — status line resets per reload; hints come from `/api/flow` | **done** |
| 10 | **Verification** — catalog 21/5, flow `ready`, MCP `tools/list`=20 via the public gated URL, `node --check` OK | **done** |

**Bug found & fixed during the round:** the photos table has no `status`
column — `/api/flow` 500'd on it; presence of photos is the state
(`id,mime,width,height,created_at` only). Also documented: raw Python-urllib
clients get **403 from Cloudflare** on POST — send a normal User-Agent.

---

> Set 2026-09-30. Foundation for the vision in `docs/oddhobb-vision.md`:
> organised subdomains per category + sections rail on the left (Board games,
> Gifts, Cards) + MCP for the whole library (ChatGPT-ready).
> Status: `pending` / `doing` / `done`.

| # | To-do | Status |
|---|---|---|
| 1 | **Section registry** — single source of truth in `backend/config.py` (`SECTIONS` + per-product `section`) exposed at `GET /api/sections` | **done** |
| 2 | **Sections rail on the left** — Board games, Gifts, Cards, All, My oddhobbs — beside the existing tab rail, with hash routing | **done** |
| 3 | **Section chips in the shop** — same controls inside the catalog (works on mobile where the rail collapses) | **done** |
| 4 | **Tag + filter every card** — both card sources (Prodigi mockups + mesh products) carry `section`; shop filters by active section with a real empty state | **done** |
| 5 | **Host → section routing** — `cards.oddhobb.com` opens Cards, `gifts.` Gifts, `boardgames.` Board games, `my.` the roster | **done** |
| 6 | **Category subdomains at the edge** — `gifts.oddhobb.com`, `boardgames.oddhobb.com` DNS + tunnel ingress (cards./my. already live) | **done** |
| 7 | **MCP for the whole library** — bind local-only, add inbound token gate, publish `mcp.oddhobb.com`, write the ChatGPT/Claude connect docs (`docs/mcp.md`) | **done** |
| 8 | **oddhobb meta** — description + og:title/url tags (page has none) | **done** |
| 9 | **`docs/navigation.md`** — sections, subdomains, rail, MCP architecture in one place | **done** |
| 10 | **Verification pass** — all hosts resolve through the tunnel, sections API, filtered shop, MCP 401-without-token / 200-with, meta present; update this file + HANDOVER | **done** |

Rules that don't change: no Meshy credits without asking (AGENTS.md), commits
only on explicit ask, secrets never in files outside `.env`.


## Verification log (10/10 closed)

- `GET /api/sections` returns the registry; `/api/products` items and
  `/api/meshes/<id>/products` rows both carry `section` (checked live: card→cards,
  bauble→gifts, video→(all)).
- Page serves rail + chips + og/meta (curl on the live tunnel); all inline JS
  passes `node --check`.
- **NS propagated — zone ACTIVE — all seven hosts 200**: `oddhobb.com`, `www`,
  `gifts.`, `boardgames.`, `cards.`, `my.`, `mcp.oddhobb.com`.
- MCP gate proven on the public hostname: `POST https://mcp.oddhobb.com/mcp`
  → **401** without token, **200 + text/event-stream + mcp-session-id** with
  (see `docs/mcp.md`).
- Tunnel roll-overs were seamless each time (4 registered connections, old
  connector retired, site 200 throughout). `api.log`: 0 tracebacks.
- Not done: a real browser click-test — playwright isn't installed on this
  box; JS verified by `node --check` + static structure instead.
