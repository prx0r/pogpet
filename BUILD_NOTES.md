# BUILD NOTES

> **STATUS: CURRENT** — written 2026-09-29 after the build session.
> What exists, how it fits together, and what was measured.
> Pick-up state and next steps live in `HANDOVER.md`.
> Do not delete this file.

## What this is

**fogp.pet / figgsite** — a pet-figurine storefront where a photo (or a
ready-made mesh) becomes a character that is instantly active across a shop
of personalised products and a talent-show stage.

```
upload photo ──┐
style preset  ─┼─► MESH ──┬─► spotlight (active pog)
upload .glb   ─┘          ├─► shop      (13 Prodigi products + 8 mesh-bound)
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
backend/          22 modules, 5,542 lines
  server.py       HTTP API (41 routes) + job worker
  db.py           schema: users, agents, profiles, photos, meshes,
                  product_bindings, videos, jobs, credits, upload_ledger
  pipeline.py     photo → mesh → fan-out
  intake.py       upload QC (magic bytes, EXIF, size, dedupe)
  storage.py      R2 via the preconfigured `rclone r2:` remote
  meshy.py        Meshy client + offline stub  ← still the only paid path
  install.py      GLB → live active pog (shared by upload + styles)
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
  mcp.py          MCP server — 15 tools
bridge/
  llm_bridge.py   serves site/ + figg-studio/, proxies /backend, injects token
site/
  index.html      the whole front end, one file, 89 KB, 4 tabs
figg-studio/      the figg. brand asset pack (32 mascots, logos, templates)
dash/             dashboard + agentcom (from qpbot)
pi/               vendored earendil-works/pi + .pi/extensions/figgsite.ts
assets/style/     5 styling PNGs from R2:stallshark
data/             gitignored — sqlite, staging, meshes, videos, concepts
```

## Tabs

| tab | does |
|---|---|
| **chat** | talks to pi through the site's AI contract |
| **upload** | spotlight roster, click to activate, drop-a-photo, **or** a style preset |
| **studio** | 8 voices × 3 scenes → comedy set → MP4 |
| **shop** | 13 Prodigi products rendered *with the active mesh*; concept picker (36) |
| **perform** | talent (comedy/dance/singing) × act (19) → stage video |

## API surface (41 routes)

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

**infra** `GET /health` · `GET /api/artifacts/<key>` · `POST /api/run`

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
