# HANDOVER

> **STATUS: CURRENT** — written 2026-09-29, updated 2026-09-30 (premesh + mesh/hook/renders sessions).
> **Start here.** What's running, what was touched, what's next.
> Detail lives in `BUILD_NOTES.md`; product system in `README.md`;
> rules and map in `AGENTS.md`.
> Do not delete this file.

## Where we are

**Live:** https://pog.pet (also `www.pog.pet`) — Cloudflare → named tunnel →
the bridge on `:8797` → site + `/backend` proxy → Flask on `:8798`.

Everything in the core loop works today: photo **or** style preset **or**
uploaded GLB → mesh → active in the spotlight → shop (13 products rendered
with that mesh) → stage (comedy/dance/singing) → print files. **$0 marginal
cost end to end.** No Meshy key needed for any of it.

### Running right now

| service | port | start |
|---|---|---|
| bridge (site + studio + `/backend` proxy) | 8797 | `BRIDGE_TOKEN=$(cat .token) python3 bridge/llm_bridge.py` |
| Flask API + job worker | 8798 | `set -a; . ./.env; set +a; python3 backend/server.py` |
| MCP server (streamable HTTP) | 8799 | `set -a; . ./.env; set +a; MCP_HTTP=1 python3 -m backend.mcp_server` |
| cloudflared named tunnel `figgsite` | — | `cloudflared tunnel --config ~/.cloudflared/figgsite.yml run figgsite` |

All four were started detached with `setsid` during the session. To bring the
whole stack back after a reboot, run `./serve.sh` for the first two — it
creates `.token` if missing and prints the URL — then the MCP and tunnel by
hand until that's folded into `serve.sh`.

**Token:** `BRIDGE_TOKEN` is in `.token` (0600). The API service token is
`API_TOKEN` in `.env`. The browser only ever holds `window.__FIGG_TOKEN`;
`API_TOKEN` never reaches the client (verified: 0 occurrences in served HTML).

## Done this session — chronological

**1. Box diagnosis (before figgsite existed).** Hardware was fine — 6 vCPU,
94% idle, 0 steal, PSI 0.00. Two real finds: **five `opencode-go` keys
Fernet-sealed in `~/.qpbot/vault.json`** (`LLM_KEY`…`LLM_KEY_5`), of which
`LLM_KEY` works, and a **powpowpow crash loop**: three user services failing
on a hardcoded `/home/box/...` path, 67,784 restarts over 5 days.

- `/home/box` → `/home/ubuntu` symlink (system-level, outside any repo)
- `pow-venue-l2` + `pow-chain-state` **stopped and disabled** (they cannot
  run without a powpowpow code fix — 24 bad paths across 21 files)
- `pow-venue-ws` now healthy
- Two bugs behind a `402`: the pi extension declared `openai-responses` while
  `mimo-v2.5` only speaks `chat/completions`, and `~/.pi/agent/models.json`
  carries a stale `apiKey` that beats the env var

**2. Domain.** `pog.pet` zone created (`abadc6500da5fdac89a74bbfa5bfd49e`),
you moved the NS, it went active. CNAMEs for `pog.pet` and `www.pog.pet` →
`54295d83-e7e7-4741-b148-9e0ccf4382f2.cfargotunnel.com`. New tunnel config at
`~/.cloudflared/figgsite.yml` + `figgsite.json` — built entirely through the
API, no `cloudflared tunnel login` needed.

**3. Imported into figgsite.** `figg-studio/` from `r2:stallshark/figg-studio.zip`
(32 mascots, logos, templates); `site/` from `stallspy/brands/mythicbee/site`;
`dash/` from qpbot; `pi/` from qpbot's vendored copy (447 MB, `.git` excluded);
`assets/style/` 5 PNGs from R2; `data/concepts/catalog.json` from petsy.

**4. Built the backend** — see `BUILD_NOTES.md` for the module map, 41 routes
and the measured free-stack numbers.

**5. Front end rethemed** to `pogpet` (character **Pogo**, *Spooky Season*),
with boot curtain → greeting → tab rail → four working panels.

## Session 2026-09-30 — published repo, Meshy prep, premesh

**Repo published.** First commit `6542c06` (2,014 files, 53 MB) pushed to
**github.com/prx0r/pogpet**, now **public**. `.env`/`.token`/`data/` verified
absent (`git check-ignore` + value-level grep of every staged file). `gh` is
authenticated on this box via the credential helper.

**Meshy prep.**
- Official **Meshy Blender plugin v0.6.1** installed into Blender 4.2.9 as
  extension `bl_ext.user_default.meshy` — 26 operators registered
  (bridge, `meshy_check_all`, hollow, non-manifold clean, STL/OBJ/PLY export).
- **Meshy docs mirrored** to `/home/ubuntu/meshy-docs` (106 English pages,
  `md/` + `html/` + `INDEX.md`). Key pages: `en__api__creative-lab-figure`
  (chibi: prototype 6cr → build 30cr, chained by `input_task_id`) and
  `en__webapp__plugins-blender__*`.
- `MESHY_API_KEY` still **empty** — nothing has been charged, no chibi built.
  A Pixabay key was handed over by mistake first; it is now stored as
  `PIXABAY_API_KEY` and works.

**premesh — the new module** (`premesh/`, see its README + AGENTS.md).
Photo → Cloudflare edge (`segment=foreground`, `trim`, `fit`, `upscale`) →
QC → bytes for the next stage. Three recipes (`meshy`/`card`/`thumb`), CLI
(`python3 -m premesh …`), route `POST /api/premesh`, Pixabay page-URL sources
resolved through the API with licence flags kept as provenance. Zone
transformations had to be enabled (`PATCH /zones/…/settings/transformations`);
bridge now serves `/premesh/` and forwards `X-*` headers.

Measured on the demo photo (Pixabay 2706681, 1280×853): `meshy` →
1024×682 transparent PNG, subject 41% of frame, QC ok, 0.5 s warm.
Prepared asset: `https://pog.pet/premesh/403e21d9ec8edcf7912a15bc710d8799.png`.

**Two Cloudflare quirks, both worked around:** `upscale=generate` drops alpha
(→ upscale runs as a prelude, before segmentation); `format=` is ignored
(→ content-type read from the bytes, `report.fmt`).

**Uncommitted:** everything since `6542c06` — `premesh/`, `AGENTS.md`,
`backend/server.py` (+route), `bridge/llm_bridge.py` (route + header
forwarding), `BUILD_NOTES.md`, this file.

## Session 2026-09-30 (continued) — mesh, hook + ballast, renders, UniMate

**Mesh (manual, 0 credits).** You generated the dog in the Meshy webapp (plain,
no bucket) and dropped it in R2 `stallshark/chibi-figure.glb` -> pulled to
`data/uploads/`: 555,646 tris, 104 x 304 x 200 mm at Meshy's scale. Note for
next time: webapp tasks are invisible to the API (verified), so the manual route
was the right call; API runs remain prototype 6cr + build 30cr with the ledger
at `data/meshy_credits.jsonl` (**42 cr total, balance 1,056**).

**Amend — `scripts/add_hook.py` (Blender-only, 0 credits, AGENTS rule #5):**
- CoM-anchored loop on the back, `HANG TILT 0.0 deg` (0.0 mm off the column).
  Defaults now **5.0 mm hole / 2.4 mm wire / O.D. 9.8 mm** — standards searched
  and recorded in `docs/balance.md` (4-6 mm hole band, >=2.5 mm for mini
  S-hooks, >=1.5 mm wall, ribbon needs the top of the band).
- `--ballast` cuts the foolproof-weighting bore: **pause at z=128.8 mm
  (layer 644 @0.2)**, 2.41 cm3 -> up to 18.8 g steel = 4.5 mm CoM trim on a
  100 g print (~7.8 deg of tilt). Full protocol in `docs/balance.md`.
- Export order matters: **GLB before voxel remesh** (texture intact), **STL
  after** (sealed manifold, scaled to mm). Outputs in `data/uploads/`.

**Renders — `scripts/render_product.py` (recipe + gotchas in `docs/rendering.md`):**
Cycles/CPU, AgX + Punchy, saturation 1.35, material rebuilt from the texture
extracted out of the GLB, S-hook prop modelled (1 mm wire). QC targets printed
per shot (blown <2%, black <3%). Shipped to R2 `stallshark/`:
`dog-hook-hero.png`, `dog-hook-detail.png` (plus the earlier
`dog-mesh-original/full/closeup` set, superseded).

**Specs written:** `docs/meshy.md` (API + money rules), `docs/balance.md`
(weighting system), `docs/rendering.md` (render recipe), `docs/unimate.md`
(stage-animation model, spec only), `premesh/README.md`.
**UniMate** cloned read-only to `/home/ubuntu/refs/UniMate` (MIT) for later.

## Files touched 2026-09-29 session

**Created in this repo** (committed as `6542c06` on 2026-09-30):

```
README.md  BUILD_NOTES.md  HANDOVER.md  .gitignore  .env.example  serve.sh
.env                keys only: OPENCODE/PRODIGI live, GOOGLE empty  (0600, gitignored)
.token              bridge token                                  (0600, gitignored)
backend/  config db intake storage meshy pipeline server mockup render video
          auth concepts concepts_src r3d mesh_export usdz acts install
          styles prodigi mcp __init__          ← 22 modules, 5,542 lines
bridge/llm_bridge.py
site/index.html                              ← imported, then rethemed + 4 tabs
pi/.pi/extensions/figgsite.ts                ← agent tools (explicit -e; local
                                                extension discovery is broken)
figg-studio/  dash/  pi/  assets/style/  data/concepts/catalog.json
```

**Outside this repo (system / infra):**

- `/home/box` symlink; the two powpowpow user units stopped + disabled
- Cloudflare: `pog.pet` zone, 2 CNAMEs, tunnel `figgsite`
- `~/.cloudflared/figgsite.yml` + `figgsite.json`
- R2: removed an orphan `owners/.../pending.jpg`; added `figgsite/owners/**`
- Read-only reads: `petsy` (a second clone of `prx0r/bwick`), `freaktown`,
  `stallspy`, `qpbot`, `bwick`, `~/.qpbot/vault.json`

**Never written to:** `powpowpow`, `freaktown`, `petsy`, `stallspy`, `qpbot`
— source repos stayed read-only; vendored copies live here with provenance
headers.

## Bugs found and fixed (worth knowing about)

- **Script ordering** — the panels script ran before the panel markup, so
  `drop`/`st-go`/`up-sculpt` were `null` and three tabs were silently dead.
- **`<img src>` bypasses the fetch patch** — every shop card and roster thumb
  401'd. Now the token is appended explicitly via `art()`.
- **Boot ran before the bridge's fetch patch** — boot-time `loadMe()` went
  out tokenless → 401, which looked like "no mesh on file". Fixed with
  `withTok()` + deferring to `window.load`.
- **Service gate ate `Authorization: Bearer`** — made every *user* API key
  read as "bad token".
- **Cloudflare 524** — real meshes took 78–200s to spin; CF cuts at 100s.
  Fixed by async turntable *and* by dropping Blender for `r3d.py`.
- **`me()` and `products()` open identically** — a `.replace(…, 1)` landed in
  the wrong function twice. Use the docstring as the anchor, not the body.

## Next

**Foundation built 2026-09-30 (see `docs/todo.md` — 10/10 + verification log):**
sections registry + left rail + shop chips + host→section routing, category
subdomains (`gifts.` `boardgames.` `cards.` `my.` — all 200), and public MCP
at `mcp.oddhobb.com/mcp` behind the token gate (401/200 proven). oddhobb.com
NS is **active** — all seven hosts live. Architecture: `docs/navigation.md`,
MCP: `docs/mcp.md`, and the modular core in `docs/foundation.md` (catalog registry, flow endpoint, MCP tool manifest).

**Progress 2026-09-30 (all same day):** 20/20 to-dos across two rounds
(`docs/todo.md`) · sample dog seeded for `anon` (flow `ready`, 8/8 products)
with the product **inheritance guarantee** proven (`docs/foundation.md`) ·
**full test pass 37/37 — `docs/test-report.md`**, re-runnable via
`python3 scripts/test_site.py` (also in AGENTS verify routine) · docs set
complete (11 files, map in `docs/how-it-works.md`).

**Progress this session (Round 4):** agent-compatibility layer live —
public Google + Shopify feeds (13 canonical renders), `llms.txt`, native
Shopify app scaffolded with a catalog sync script (`shopify-app/`,
`ODDHOBB.md` has the 2-value connect).

**Progress this session (Round 5):** multi-brand seam live — `config.BRANDS`
+ `brand_for()` + `GET /api/brand`, frontend repaints brand strings from
the server (no hardcoded brand left in the page), premesh zones follow the
request host. **ochema.co**: CF zone created, CNAMEs + ingress wired,
support email rule queued — **zone pending on NS at Namecheap
(gina/pete.ns.cloudflare.com)**. Shopify 3D preview pattern researched
(`brennan252/Immersive-Product-Display` reference clone; adopt
`<model-viewer>` + native product media — see `shopify-app/ODDHOBB.md`).
**54/54 tests green.** Spec: `docs/multi-brand.md`.

**Round 6 (same day) — audit fixes landed, 64/64 tests green:**
owner-sig session model (`POST /api/session` + gates on credit-burning and
non-anon reads — named owners need a signed session or API key; anon/pog_*
demo path stays open), login/signup rate limiting, email UNIQUE index,
per-brand watermark + feed links, bridge security headers + owner-sig
forwarding, MCP signs only `FIGG_OWNER`, trademark doc, README refresh,
`BRIDGE_TOKEN` pinned so restarts don't 401 the frontend. Shopify dev store
synced (13 products GBP) — auth model documented in `docs/shopify-auth.md`
(no secrets outside `.env`). Full audit: `docs/audit.md`.

**SEO + bobdod + CompanyGraph (same day):** Google's 8 AI attributes are
official (Merchant Center docs verified by owner) and now wired —
`/api/seo/products.json`, `/api/seo/faq.json` (32 Q&A pairs), `/guides/<id>`
FAQPage schema, Merchant RSS custom labels. Main helper agent renamed
**bobdod** (storefront default host + MCP identity). CompanyGraph live at
`GET /api/companygraph` (FACTS/RESOURCES/CAPABILITIES, 20 products, derives
from config) + MCP tool `figg_companygraph` (21 tools). Spec:
`docs/companygraph.md`, playbook `docs/seo.md`, status `docs/seo-impl.md`.
**Discovery stack (same day):** robots.txt allows GPTBot/ClaudeBot/
PerplexityBot/Google-Extended/Bingbot; Product+FAQPage JSON-LD on guides;
GEO learn pages with comparison tables at `/learn/*`; sitemap.xml; Q&A bank
expanded to **422 public pairs**. **77/77 tests green.**

Needs from you: (1) NS for ochema.co at Namecheap, (2) commit when you
want the session work in git, (3) Google console redirect before flipping
`PUBLIC_BASE` to oddhobb.com, (4) Merchant Center account + feed submit,
(5) Etsy + Pinterest accounts (ops, not code).

**Read first, in order:**
1. `docs/how-it-works.md` — the map: system, approach (contracts first,
   pages second), why **my.oddhobb.com** is the centre, doc index.
2. `docs/oddhobb-vision.md` — product vision (Amazon-style catalog + docked
   chat + voice + personalized browsing + rubric + subdomains).
3. `docs/muse-mcp-design.md` — the MCP as product contract, Muse-agent
   perspective: journey-ordered tools, session model, honest gap backlog
   (rubric, remote upload, **figg_order doesn't exist**).
Edge infra for all oddhobb hosts is live; contract docs are current.

**Yours (blocked on you):**

1. Google client ID + secret -> paste into `.env`, sign-in goes live.
2. Prodigi SKUs from your dashboard -> `GET /api/prodigi/check?sku=` validates,
   then add `sku` to a product and its price flips EST -> **LIVE** (canvas
   already proves the path: `GLOBAL-CAN-10X10`, £16.00, EVRi Next Day).
3. Cloudflare Access still not enabled on the account (one click) — wanted for
   `/admin` only; the public site must not go behind it.
4. Decide if/when to start **UniMate Phase 0** (free: their interactive demo +
   reading the HF checkpoint licence) — spec in `docs/unimate.md`.
5. Eyeball the shipped R2 renders (`dog-hook-hero.png`, `dog-hook-detail.png`)
   and say if the fur colour passes; the listing pass comes after that.

**Mine, still open:**

- **Listing render pass** — `render_product.py --size 2000` + composite into
  the figg-studio before-after template; tune `--sat` against
  `dog-mesh-original.png` (AgX still pales the fur a little). Details:
  `docs/rendering.md` Known issues.
- **Black wedge root cause** — hard shadow on the detail shot's lower-left;
  cropped around for now (QC `black` metric catches regressions).
- **premesh -> `POST /api/meshes`** — key exists now, so the normalise step
  can go live in the mesh pipeline; plus `stage.prune()` on a job tick.
- **Performance history UI** — `GET /api/videos?owner=` already returns them;
  nothing renders a list yet.
- **freaktown scoring** — wire `show_runtime` / `performance_compiler` /
  `judge` / `scoring` / `reputation` as the Perform layer; `stage/theme.json`
  already supports a theme switch (Halloween/Christmas/Midnight Carnival/
  Sticker Freakshow).
- **Stage themes on our own site** — only the palette is Halloween right now.
- **Fold MCP + tunnel into `serve.sh`** so one command brings the stack up.
- **Rebrand cut-over to oddhobb.com — brand DECIDED = oddhobb** (not
  pogpet/bwick/figg-studio). Done: zone + NS pair `gina`/`pete.ns.cloudflare.com`
  (NS set at Namecheap 2026-09-30, zone pending), apex+www CNAME -> tunnel,
  tunnel ingress + zero-downtime connector roll-over, **site copy swapped**
  (title, boot/greeting marks, nav, AI system prompt — 7 substitutions in
  `site/index.html`, verified live on pog.pet). Remaining: `PUBLIC_BASE` in
  `.env` (+ restart bridge/Flask so premesh URLs brand correctly), pog.pet
  redirect-or-alias decision, **mascot rename?** ("Pogo" appears in5 copy
  lines + the AI persona CAST entry — kept for now, character vs brand),
  add og/meta description (page has none), optional internal cleanup
  (localStorage keys `pogpet.*` are kept on purpose so returning users don't
  lose local state; `window.__FIGG_TOKEN` needs a coordinated page+bridge
  rename), figg-studio stays as the *visual* system (tokens/templates) — only
  the presented name changed.
- **Commit + push** — everything from 2026-09-30 is still uncommitted
  (`premesh/`, `docs/`, `scripts/`, `AGENTS.md`, bridge/server edits).

## Gotchas to re-read if you're coming back cold

- Local pi extension discovery (`cwd/.pi/extensions`) **loads nothing** in
  this build — pass `-e` explicitly. That's why `tps.ts`, `redraws.ts` and
  `prompt-url-widget.ts` were never loading either.
- Blender is **gone from the render path**; only `usdz.py` still needs it, and
  it wants `/home/ubuntu/opt/blender-4.2.9-linux-x64/blender` (the Ubuntu
  package ships no USD libs).
- The `petsy` tree is a second clone of `prx0r/bwick.git` at a *different*
  tip, and it holds the richer mesh path — don't assume `bwick/` is current.
- Prices without a `sku` are **EST**, always labelled. Never present them as
  verified. Wrapping paper is grade Q.
- `/backend/*` is gated on the bridge token; the bridge substitutes
  `API_TOKEN` when proxying, so exactly one secret is ever public.

**Added 2026-09-30 (render/amend edition):**

- **Renders:** never trust your eyes alone in this environment — the image
  viewer repeatedly served *old files*. Tag candidates with **different**
  coloured bars per file and check the bars on read (full protocol:
  `docs/rendering.md`). Headless EEVEE is flaky (flat-white output) — use the
  Cycles recipe. `Standard` view transform clips fur white; AgX alone goes
  anemic; the shipped combination is AgX + Punchy + saturation 1.35.
- **Cameras:** `view_layer.update()` after setting transforms or the render
  silently uses the previous camera matrix.
- **add_hook:** GLB export happens *before* the voxel remesh (keeps textures);
  the STL is exported after, scaled x1000 (Blender units are metres, slicers
  read mm).
- **Meshy Creative Lab paths:** create/poll at `/openapi/creative-lab/figure/v1/...`
  (NOT under `/openapi/v1/`), and polling mirrors the create path
  (`GET .../prototype/{id}`) — the docs' "Get a Task" endpoint 404s.
  Full details: `docs/meshy.md`.
- **rclone -> R2:** first copy attempt often returns `501 NotImplemented`;
  retry lands. Always `--retries 3` + verify with `rclone ls`.
