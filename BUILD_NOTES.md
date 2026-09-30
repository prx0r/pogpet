# BUILD NOTES

> **STATUS: CURRENT** — written 2026-09-29, consolidated end of 2026-09-30.
> What exists, how it fits together, and what was measured.
> Pick-up state and next steps live in `HANDOVER.md`.
> Latest full test: `docs/test-report.md` (**50/50**, `scripts/test_site.py`).
> Do not delete this file.

## What this is

**oddhobb.com / figgsite** — a pet storefront where a photo (or a
ready-made mesh) becomes a character that is instantly active across a shop
of personalised products and a talent-show stage. Public repo:
`github.com/prx0r/pogpet`. Live hosts: `oddhobb.com` (+ `www`, `gifts.`,
`boardgames.`, `cards.`, `my.`, `mcp.` — Cloudflare zone active, all 200).

```
upload photo ──┐
style preset  ─┼─► MESH ──┬─► spotlight (active star, formerly "pog")
upload .glb   ─┘          ├─► shop      (13 Prodigi products + 8 mesh-bound = 21)
                          ├─► perform   (comedy / dance / singing)
                          └─► print     (STL · OBJ · USDZ · turntable)
```

Everything downstream of the mesh is **free and local**. The only thing that
still costs money or a key is photo → 3D.

## Free stack (measured, not assumed)

| step | how | cost | measured |
|---|---|---|---|
| mesh → still | `r3d.py` pure Python | $0 | **1.2s** @512 |
| mesh → turntable | `r3d.py` + ffmpeg | $0 | **19.3s** /36 frames |
| mesh → STL/OBJ | `mesh_export.py` | $0 | 1.9s / 3.2s |
| mesh → USDZ | `usdz.py` + Blender 4.2.9 | $0 | 4.7s |
| style preset → active mesh | `install.py` | $0 | **4.2s** |
| script | LLM via opencode-go | $0 | ~10–25s |
| voice | **edge-tts, 324 voices** | $0 | instant |
| frame + mux | PIL + ffmpeg | $0 | instant |
| render a video | whole path | **$0** | **~23s**, 14–23s clips |
| storage | Cloudflare R2 (existing remote) | $0 | — |

Blender was removed from the render path: `render3d.py` is ~10× faster on
stills and 4–10× on turntables, and it cleared a hard failure — real meshes
took 78–200s and **Cloudflare timed the origin out at 100s (HTTP 524)**.

## Layout

```
backend/          22 modules
  server.py       HTTP API (48 routes) + job worker
  db.py           schema: users, agents, profiles, photos (+person), meshes,
                  product_bindings, videos, jobs, credits, upload_ledger
  pipeline.py     photo → mesh → fan-out
  intake.py       upload QC (magic bytes, EXIF, size, dedupe)
  storage.py      R2 via the preconfigured `rclone r2:` remote
  meshy.py        Meshy client + offline stub  ← still the only paid path
  install.py      GLB → live active mesh (shared by upload + styles)
  styles.py       7 ready-made characters, no key needed
  render.py       mesh → PNG / MP4   (uses r3d)
  r3d.py          vendored pure-Python renderer
  mesh_export.py  vendored GLB → OBJ/STL
  usdz.py         vendored GLB → USDZ
  mockup.py       product mockups (13 shapes) with the mesh composited in
  concepts.py     + concepts_src.py   36-concept template library
  acts.py         19 talent-show acts (vendored from freaktown)
  video.py        script + edge-tts + ffmpeg → MP4
  prodigi.py      live pricing (key in .env)
  auth.py         Google OAuth, stdlib only
  mcp_server.py   MCP server — 20 tools (TOOL_AREAS manifest)
bridge/
  llm_bridge.py   serves site/ + figg-studio/ + /premesh/ + public /img/,
                  proxies /backend (gated) + ungated /api/feeds/* + /mcp
premesh/          image normalisation: recipes, Cloudflare edge, QC, Pixabay
scripts/          add_hook · meshy_figure · render_product · seed_sample · test_site
docs/             10 guides (map: docs/how-it-works.md) + todo.md + test-report.md
shopify-app/      stock Remix template + sync:catalog (feed → Shopify upsert)
site/
  index.html      the whole front end, one file, ~107 KB, 5 tabs + topbar
  llms.txt        agent/shopping-bot machine summary (catalog, feeds, MCP)
figg-studio/      the figg. brand asset pack (32 mascots, logos, templates)
dash/             dashboard + agentcom (from qpbot)
pi/               vendored earendil-works/pi + .pi/extensions/figgsite.ts
assets/style/     5 styling PNGs from R2:stallshark
data/             gitignored — sqlite, staging, meshes, videos, concepts,
                  premesh/public, productimg/, meshy_credits.jsonl
```

## Tabs

| tab | does |
|---|---|
| **chat** | talks to pi through the site's AI contract |
| **upload** | spotlight roster, click to activate, drop-a-photo, **or** a style preset |
| **studio** | 8 voices × 3 scenes → comedy set → MP4 |
| **shop** | 13 Prodigi products rendered *with the active mesh*; concept picker (36) |
| **perform** | talent (comedy/dance/singing) × act (19) → stage video |

## API surface (42 routes)

**identity** `POST /api/accounts` · `POST /api/accounts/login` ·
`GET /api/accounts/me` · `POST /api/agents` · `GET /api/agents` ·
`POST /api/agents/<id>/permissions` · `POST /api/agents/<id>/revoke` ·
`GET /api/agents/me` · `GET /api/auth/google/{start,callback}`

**meshes** `POST /api/photos` · `POST /api/meshes` · `POST /api/meshes/style` ·
`POST /api/meshes/glb` · `GET /api/meshes` · `GET /api/meshes/<id>` ·
`GET /api/meshes/<id>/{products,measure,print,turntable,usdz}` ·
`GET /api/styles` · `GET /api/me` · `POST /api/me/active`

**shop** `GET /api/products` · `GET /api/concepts` · `GET /api/listing-pack` ·
`GET /api/prodigi/{check,quote}`

**perform** `GET /api/acts` · `POST /api/videos` · `GET /api/videos` ·
`GET /api/videos/<id>/{,file}` · `GET /api/voices` · `GET /api/credits`

**infra** `GET /health` · `GET /api/artifacts/<key>` · `POST /api/run` ·
`POST /api/premesh`

## MCP — the agent endgame

`backend/mcp.py`, mcp 2.x `MCPServer`, **stdio or streamable HTTP on `:8799/mcp`**.

```
figg_me · figg_create_account · figg_login · figg_styles · figg_install_style
figg_mesh_status · figg_measure · figg_print_export · figg_products
figg_concepts · figg_quote · figg_check_sku · figg_acts · figg_perform · figg_credits
```

Tools call the HTTP API rather than the DB, so permission checks, credit
accounting and validation stay in exactly one place. Identity comes from
`FIGG_API_KEY` in the environment — use your own key, or an agent key minted
via `POST /api/agents` (separate profile, only the permissions you granted).

**Verified over the wire:** initialize → session, `tools/list` → 15,
`figg_install_style(buster)` → `status=succeeded, products=8, active=True`,
`figg_quote(GLOBAL-CAN-10X10)` → `LIVE £16.00 EVRi Next Day`.

## Free tier

`FREE_MESH_PER_DAY=3` (real Meshy credits, the scarce thing),
`FREE_VIDEO_PER_DAY=5` (ours cost nothing — an abuse limit, not a budget).
Spend is atomic; failures refund. `WATERMARK_FREE=1` marks free renders.

## Accounts & agents

`handle` **is** the owner string — logging in stops the identity being a
random blob in localStorage. Agents are minted *by* a human account and get
their own handle, own profile, own meshes, **no wallet**, plus a permission
subset: `profile:read|write`, `photos:upload`, `mesh:sculpt|upload|read`,
`video:render`, `products:read|order`. Parents can revoke.

Auth layers: service gate = `?token=` / `X-API-Token`; user identity =
`Authorization: Bearer` or `X-API-Key`. **The service gate deliberately does
not consume Bearer** — it did once, and that made every user key 401.

## Verification log

All of this was run in a real browser (Playwright/Chromium) or over the wire,
not just parsed:

- tabs: upload/studio/shop/chat all `visible:true`, correct panel on top, 0 page errors
- spotlight: switch propagates to the shop (`spotlight: pog 977da`)
- shop: 20 cards, 12/12 images loaded, `source_kind: mesh`
- perform: `dance · 19s · ryan`, `readyState 4`, credits 5→3
- print: STL **59,504 triangles** @70mm (matches the exemplar README)
- turntable: `ready in 20s` (was HTTP 524)
- MCP: 15 tools, live quote, instant style install
- `api.log`: **0 tracebacks**

## Known stubs

- **Meshy** — `meshy.py` synthesises a valid GLB. `MESHY_API_KEY` still absent.
  Photo → 3D that looks like *your* pet is the one thing a mesh library can't fake.
- **Google auth** — built, returns a clean 501 with instructions until
  `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` are set.
- **Stripe** — "Add to cart" says so out loud.
- **Free video STT** — whisper route returns `success:false`; site falls back to typing.

## premesh — image normalisation module (2026-09-30)

New top-level package `premesh/` (PIL + stdlib only, zero backend imports, so
it can be lifted out for the greeting-card side or driven standalone):

```
premesh/recipes.py   meshy | card | thumb  — options + QC thresholds as data
       cloudflare.py  build /cdn-cgi/image/<opts>/<source> and fetch
       stage.py       local file -> content-addressed /premesh/<sha>.jpg on the zone
       qc.py          accept/reject: alpha present, size, subject coverage
       __init__.py    normalize(source, recipe) -> Normalized(data, report, traces)
       cli.py         python3 -m premesh photo.jpg -o out/ -r meshy
```

Everything happens at the Cloudflare edge in one URL — no fal, no GPU here:

- `segment=foreground` (BiRefNet) → subject on transparency
- `trim=border` → `fit=contain,w=1024,h=1024` → `sharpen` → PNG
- small sources get a **prelude** pass (`upscale=generate`, ESRGAN) *before*
  segmentation — see quirks below
- 5,000 unique transformations/month free, edge-cached, repeat = free

**Enabled:** `PATCH /zones/abadc…/settings/transformations {"value":"on"}`
(the zone was off — `/cdn-cgi/image/…` 404'd until then).
**Serving:** `bridge/llm_bridge.py` now routes `/premesh/` →
`data/premesh/public/` (content-addressed, gitignored under `data/`), and
`_proxy` forwards upstream `X-*` headers so `X-Premesh-Ok` reaches the
browser. **Secrets:** `CF_ACCOUNT_ID`, `CF_API_TOKEN`, `R2_S3_ENDPOINT`,
`R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY` appended to `.env` (0600,
gitignored). The zone URL interface itself needs no token.

**Route:** `POST /api/premesh` — multipart `photo` (goes through `intake`, so
flat/tiny/foreign files die before any edge call) or `?url=…`, plus
`recipe=meshy|card|thumb`, `format=json` (report + base64), `strict=1`
(422 on QC failure). Binary responses carry `X-Premesh-Ok/Recipe/Coverage`.

**Measured** on a 399×501 photo, over the tunnel, ~6s end to end:

| recipe | output | QC |
|---|---|---|
| `meshy` | PNG 814×1024, alpha, subject 34% of frame | ok |
| `card`  | PNG 1274×1600 (prelude upscaled 399→1600), alpha | ok |
| `thumb` | JPEG 399×501, ≤512 | ok |

**Quirks found the hard way (both worked around in code):**

1. `upscale=generate` **silently drops the alpha channel** — so AI upscale can
   never run after `segment`. It runs as a prelude on the opaque source.
2. `format=` is **ignored on this zone**: output is PNG whenever there's
   transparency, otherwise the source's format. QC reads the real container
   from the bytes (`report.fmt` → `content_type`) instead of trusting options.

**Pixabay source support** (`premesh/pixabay.py`): a Pixabay *page URL* is
now a valid `normalize()` source — resolved through the Pixabay API with the
key in `.env` (`PIXABAY_API_KEY`), downloaded via the signed `largeImageURL`
with a referer (the CDN 403s non-browser clients), and the licence flags
(`noAiTraining`, `isAiGenerated`, `isGRated`, tags, uploader) ride along in
`Normalized.meta` for provenance. Bare ids and `?id=` forms work too.

**Open:** call `normalize()` from `POST /api/meshes` once `MESHY_API_KEY`
lands; `stage.prune()` on a job tick; fal.ai as a fallback provider if
BiRefNet alone isn't clean enough on fur/ears.


## 2026-09-30 (later) — hook, ballast, balance protocol, UniMate spec

**`scripts/add_hook.py`** — the amend step, Blender-only (0 credits, AGENTS rule #5):
CoM-anchored loop (`--anchor com`, prints `HANG TILT`, 0.0 deg on the demo dog),
boolean union + 0.6 mm voxel seal to manifold, Meshy plugin's local checks run headless
(needs `addon_enable` after `read_factory_settings`). Exports GLB **before** remesh so
textures survive, STL after, scaled to mm.

**Foolproof weighting** (`docs/balance.md`): `--ballast` cuts an enclosed
Ø8 x 48 mm steel-shot bore under the loop (axis side-to-side so fill trims left/right).
Demo dog: pause at z=128.8 mm (layer 644 @0.2), 2.41 cm3 -> up to 18.8 g steel
(4.5 mm CoM trim on a 100 g print ~ 7.8 deg), manifold + Meshy checks pass.

**Assets:** `data/uploads/chibi-figure{,-hook}.{glb,stl}` (user's manual Meshy render +
hooked/ballast variants). Ledger: 42 cr total, balance 1,056 — nothing spent since.

**UniMate spec:** `docs/unimate.md` — SIGGRAPH Asia 2026 text->motion model, cloned to
`/home/ubuntu/refs/UniMate` (MIT). For the stage layer later; blocked on rig + GPU,
every spend phase gated. Nothing wired.


**Renders (same day, later):** `scripts/render_product.py` — Cycles/CPU recipe
that survives this box: material rebuilt from the texture *extracted out of the
GLB* (glTF import intermittently renders flat white), AgX + Punchy + saturation
1.35 (Standard clipped ~20% of pixels; AgX alone was the "anemic" look),
`view_layer.update()` before every shot (stale camera matrix), S-hook prop
modelled at real 1 mm wire, QC printed per shot (blown/black %, targets <2%/<3%).
Shipped to R2 `stallshark/`: `dog-hook-hero.png`, `dog-hook-detail.png`.
Full spec + image-verification tag protocol: `docs/rendering.md`. Loop sizing
standards (4-6 mm hole band, etc.) recorded in `docs/balance.md`; hook defaults
now 5.0/2.4.


**Section foundation (same day, later):** `docs/todo.md` — the10, all closed
with a verification log. Backend: `SECTIONS`/`SECTION_OF` in config +
`GET /api/sections`; items and mesh-products tagged with `section`. Frontend:
left `.seclrail` + shop `.secchips` (registry-driven, hash + host routing,
empty states), meta/og for oddhobb. Edge: `gifts.` `boardgames.` `cards.`
`my.` `mcp.` — all seven oddhobb hosts live (NS active). MCP hardened: server
now binds 127.0.0.1, bridge proxies `/mcp` with token gate (401/200 proven on
the public host). See `docs/navigation.md` + `docs/mcp.md`.


**Modular foundation (same day, round 2):** `docs/todo.md` Round 2 — 10/10.
`GET /api/catalog` (21 products, one registry: price/section/emoji/blurb/preview
kind) now drives site cards, the shop and MCP alike; `GET /api/flow` returns the
upload→mesh→previews state machine (stage + hint); shop re-renders every
product preview when a sculpt lands; `backend/mcp_server.py` restructured to a
`TOOL_AREAS` manifest with 5 new tools (catalog/flow/start_mesh/upload_photo/
tools) — **20 tools total**, reachable through the gated public MCP. Fixed:
photos table has no `status` column (flow 500). Details: `docs/foundation.md`.


**Documentation pass (same day):** `docs/how-it-works.md` — the map + the
approach (contracts first, pages second; `my.oddhobb.com` as the flow page
that everything else continues from) + doc index; `docs/muse-mcp-design.md` —
MCP designed agent-first for a "Muse" connector: journey-ordered tool table,
session/identity model (per-customer `api_key`), money rules, and the honest
gap backlog (remote upload, rubric, preview URLs, **no order route exists**).
HANDOVER read-first order rewritten around them.


**Sample + inheritance (same day):** `scripts/seed_sample.py` plants the
generated dog mesh (`data/uploads/chibi-figure.glb`) + premesh PNG under owner
`anon` — 8/8 bindings, active, flow stage `ready`, 0 credits; idempotent.
`GET /api/meshes/<mid>/products` gained the **inheritance guarantee**: lazy
set-difference + idempotent `bind_products` so a product added to config shows
up on every existing mesh without re-sculpting (proof: deleted a binding →
re-read restored 7→8). anon's first shop render = 13 mockups in 30 s, then
cached. Docs: foundation.md + how-it-works.md updated.


**Full test pass (same day):** `scripts/test_site.py` — 37 checks, one
repeatable command, exits non-zero on failure, writes `docs/test-report.md`.
Covers: 6 oddhobb hosts + page structure/branding, contract APIs
(sections/catalog/flow/products/styles/acts/credits/me), sample-mesh
inheritance, preview-image fetch, auth gates (401 ×3), a free premesh edge
call, full MCP session (initialize → tools/list=20 → tools/call figg_flow →
401 without token), and a no-new-tracebacks delta check. **37/37 PASS.**
Test bugs fixed along the way: artifact paths need the /backend prefix,
flat images are rejected by intake on purpose, MCP replies 202 for
notifications, HTTP/2 lowercases headers, traceback check must be a delta.

## Round 3 — Amazon storefront + my. people space (2026-09-30)

Killed the double rail: `.seclrail` + in-shop chips deleted, replaced by a
fixed **topbar** (logo, store-wide search, account/cart) and a persistent
**category strip** — one nav layer. Full-page Amazon test: `test_site.py`
37→**44/44**. `my.` is now "Your star" + uploads autosorted into people:
`photos.person` column (migrated), dHash clustering endpoint, "who's this?"
inline rename that saves to the profile, "make star" spotlighting, custom
gifting seeded by design. `cards.oddhobb.com` verified as the first
section-shelf (blurb-led lede + filtered grid).

**Email (same day):** Cloudflare Email Routing enabled on `oddhobb.com`,
MX records live, rule `support@oddhobb.com` -> verified inbox
(tradesprior@gmail.com), enabled. Pinterest domain meta tag added to
`site/index.html` `<head>`, verified serving on oddhobb.com + www.

**Feeds + Shopify app (same day, Round 4):** per GTM inspo
(read-only clone, nothing vendored), Shopify is the canonical product DB.
`GET /api/feeds/google.xml` (Merchant Center RSS, GBP, section-shelf links)
and `GET /api/feeds/shopify.json` (products.json shape) — both public
(bridge exemption like /api/auth), both render from anon's canonical sample
renders, product images mirrored to public `data/productimg/` served at
`/img/` (marketing assets only; user photos never public). `site/llms.txt`
for shopping agents (catalog, feeds, MCP, contact). `shopify-app/` = stock
Remix template (nested .git removed) + `write_products,read_products` +
`scripts/sync-catalog.mjs` (`npm run sync:catalog`, `--dry-run`, fail-fast
auth, upsert-by-handle) + `ODDHOBB.md` connect guide. Test suite 44→**50/50**.
Needs from user: store .myshopify.com domain + Admin API token to run a real
sync. Known: PUBLIC_BASE still https://pog.pet in .env (OAuth callback
stability) — flip to oddhobb.com with the Google console redirect when ready.

**Multi-brand seam + ochema.co (same day, Round 5):** one codebase, many
storefronts. `config.BRANDS` maps hosts → brand strings; `brand_for(host)`
strips www, lets subdomains inherit the parent domain, and falls back to a
default for unknown hosts (never an error). `GET /api/brand` answers per
request Host; the frontend fetches it on load and repaints title, boot /
greeting / topbar marks, section labels and the Bee's system prompt from
the answer — no hardcoded brand strings remain in the page. Premesh
normalise() now takes the zone from `brand_for(request.host)` so staged
transformation sources live on the zone actually serving them. ochema.co:
Cloudflare zone created in the same account (id `1f0d6f8d88dec141c2d25011659e391c`),
CNAMEs + tunnel ingress added (seamless rollover, pog.pet still 200),
support@ email rule queued; **zone is pending — user must paste NS at
Namecheap (gina/pete.ns.cloudflare.com)**. Shopify 3D preview research:
cloned public repo `brennan252/Immersive-Product-Display` (reference-only,
not vendored) — adopted its one-snippet `<model-viewer>` + Shopify native
product 3D media pattern (free AR: Quick Look + Scene Viewer); documented
in `shopify-app/ODDHOBB.md` and `docs/multi-brand.md`. Tests 50→54/54.

**Audit Round 6 — security + trust (same day):** full codebase audit in
`docs/audit.md` (69 routes, money paths, untested threads, theatre register).
Fixes landed: owner-sig session model (`POST /api/session`; named owners
need a signed session or API key on credit-burning writes and non-anon
reads; anon/pog_* demo path open); login/signup rate limiting (5 fails /
15 min → 429); email UNIQUE partial index; bridge security headers
(nosniff / SAMEORIGIN / referrer-policy) + X-Owner-Sig/X-API-Key forward;
MCP signs only `FIGG_OWNER`; turntable exceptions logged; `BRIDGE_TOKEN`
pinned in `.env` so bridge restarts don't 401 the frontend; watermark +
feed links per-brand (`config.watermark_brand()`, `_public_base()`);
`docs/trademark.md` written (concepts IP gate); README status refreshed.
Test suite 50→**64/64**, then 71, then **77/77** as SEO/bobdod landed.

**Shopify dev store (same day):** app created in Dev Dashboard (no
copyable `shpat_` in UI — `atkn_` is CLI-only). Auth = client_credentials
exchange of client_id + client_secret → 24h Admin API token; script
auto-refreshes (`shopify-app/scripts/sync-catalog.mjs`). Store
`oddhobb-oufybzg3.myshopify.com` (GBP) synced: **13 products ACTIVE with
images + prices**. Secrets live only in `.env` (0600, gitignored);
`docs/shopify-auth.md` is the secrets-free reference; `shopify.app.toml`
has blank client_id. Money note: Admin API cannot spend funds; Meshy is
the only paid path (ask-first, ledger).

**Google AI + Pinterest SEO (same day):** playbook saved `docs/seo.md`
(owner-verified against Google Merchant Center docs: Product Highlight,
Product Detail, Document Link, Q&A are official AI attributes). Wired:
`SEO` pack in config (8 attributes + product-specific Q&A per product) →
`_feed_items` → Merchant RSS (custom labels, item_group_id, FAQ in
description) + Shopify feed (Q&A in body_html). Public:
`GET /api/seo/products.json`, `GET /api/seo/faq.json` (**422 pairs** via
GEO shared bank `expand_seo_qa()`), `GET /guides/<id>` (Product+FAQPage
JSON-LD, GBP offers). GEO hub `GET /learn/` + 4 definition/comparison
pages (Article JSON-LD, comparison tables). `site/robots.txt` allows
GPTBot/ClaudeBot/PerplexityBot/Google-Extended/Bingbot/etc.
`sitemap.xml`. `llms.txt` points agents at all of it. Status:
`docs/seo-impl.md`.

**bobdod + CompanyGraph (same day):** main helper agent renamed
**bobdod** (storefront default host, MCP identity, system prompt gets
live catalogue facts). CompanyGraph per `prx0r/agentcom` pattern:
`GET /api/companygraph` public — FACTS (20 products derived from config),
RESOURCES (Shopify/CF/R2/Meshy/MCP), CAPABILITIES (reads free; mesh/video
writes approval-gated; order/email reserved), `helper_agent: bobdod`.
MCP tool `figg_companygraph` (21 tools). Spec `docs/companygraph.md`.
Research clones (read-only, not vendored): `prx0r/agentcom`,
`agentcomfinal` (xmrbot-private-procurement — non-custodial grant/gate
model; **not wired**, legal review required before any XMR/Tor path),
`qprivately`, `funnylabs`.

**Catch-up map for the next agent:** read `HANDOVER.md` → `docs/audit.md`
→ `docs/seo-impl.md` → `docs/companygraph.md` → `docs/shopify-auth.md`.
Run `python3 scripts/test_site.py` (77/77 expected). Services: bridge :8797
(token in `.token` / `BRIDGE_TOKEN` in `.env`), Flask :8798, MCP :8799
(MCP_HTTP=1). ochema.co pending NS at Namecheap
(`gina.ns.cloudflare.com` / `pete.ns.cloudflare.com`). PUBLIC_BASE still
`https://pog.pet` until Google OAuth redirect is updated. Secrets: `.env`
only — never commit.
