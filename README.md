# figgsite

Figg backend — photo in, mesh out, mesh active across every product, with the
pi agent driving it.

> STATUS 2026-09-30: oddhobb.com storefront live via Cloudflare tunnel
> (multi-brand seam — ochema.co pending NS at Namecheap). Meshy **live**
> (real mesh on file, ledger 1,056 cr left, paid calls ask-first). Shopify
> dev store synced (13 products, GBP) — auth model in `docs/shopify-auth.md`.
> Test suite green (`python3 scripts/test_site.py` → `docs/test-report.md`).
> **Repo:** github.com/prx0r/pogpet (public) · **start here:** `HANDOVER.md`,
> audit: `docs/audit.md`, rules/map in `AGENTS.md`.

## Layout

```
figgsite/
├── figg-studio/      the figg. asset pack — brand studio (see below)
├── backend/           the pipeline (Flask, sqlite, rclone→R2)
│   ├── server.py      HTTP API + job worker
│   ├── pipeline.py    photo → mesh → fan-out
│   ├── meshy.py       Meshy client + offline stub (valid GLB)
│   ├── intake.py      photo QC (magic bytes, EXIF, downscale, dedupe)
│   ├── storage.py     R2 via the preconfigured `rclone r2:` remote
│   └── db.py          photos / meshes / product_bindings / jobs
├── bridge/llm_bridge.py  site AI contract → pi (serves site/ + figg-studio/ + premesh/)
├── premesh/          image normaliser: photo → Cloudflare edge → Meshy/card/thumb input
│   ├── recipes.py    meshy | card | thumb — options + QC as data
│   ├── pixabay.py    page URL → API → licensed image bytes (+ provenance)
│   └── README.md     how to reuse it elsewhere
├── pi/.pi/extensions/figgsite.ts   the agent's 5 tools
├── site/              product frontend, imported from stallspy/brands/mythicbee/site
├── dash/              dashboard + agentcom, imported from qpbot
├── pi/                vendored earendil-works/pi (built)
├── assets/style/      5 styling PNGs from R2:stallshark (gitignored)
├── serve.sh           one process, one port
└── .env               gitignored, 0600 — never committed
```

## figg-studio (the theme)

Installed from `r2:stallshark/figg-studio.zip` (27 MB, 114 files) — this is the
brand layer that replaces the bee/Bartholomew theme.

| | |
|---|---|
| Brand | `figg.` lowercase, violet period — never uppercase |
| Signature | `#8B3DFF` figg violet · `#111111` ink · `#EAD8FF` lilac · `#FAFAF8` paper |
| Mascots | **32** original characters, each as editable SVG + 1024×1024 transparent PNG |
| Identity | 8 logos incl. `figg-wordmark-outlined.svg` (vector paths, **no font needed** — use this for print) |
| Templates | Etsy hero / before-after / 4-step process, A6 thank-you card, round sticker, social square |
| Handoff | `design-tokens.{css,json}`, `mascot-manifest.json` (32 variants) |
| Archive | 4 original concept boards (full + thumbs) |

Served at **`/studio/`** on the bridge, same origin as the product site:

```bash
/                 → site/       the product frontend
/studio/          → figg-studio/  brand studio
/studio/assets/…  → mascots, logos, tokens, templates
```

Verified: 28/28 local refs resolve, 32/32 manifest variants have both files,
traversal blocked (404), correct MIME for svg/png/css/json/jpg/zip.
`downloads/figg-asset-kit.zip` is gitignored — rebuild with
`python3 scripts/package.py` after editing assets.

Brand rules and the product-truth checklist are in `figg-studio/README.md` —
notably: the concept boards are art-direction references, and public listings
need photographs of real prints.

## Backend

```
POST /api/photos              multipart photo → QC → R2   (3/owner/day, dedupe free)
POST /api/meshes              {photo_id} → start the sculpt (cached per photo)
GET  /api/meshes/<id>         status + products + jobs
GET  /api/meshes/<id>/products the fan-out only
POST /api/run                 drain the job queue now
GET  /api/artifacts/<key>     stream a private R2 object
GET  /health                  counts, meshy live/stub, catalogue
```

The design point: a **Mesh row is the single source of truth**. Products hold
`product_bindings` rows pointing at it, so re-theming for a season re-renders
from the same GLB rather than re-sculpting — upload once, own the character.

```bash
set -a; . ./.env; set +a          # API_TOKEN, OPENCODE_API_KEY, FIGG_UPLOAD_DIR
python3 backend/server.py         # port 8798, prints its token, starts a worker
./serve.sh                        # site + pi bridge on 8797
```

### Agent tools

`pi/.pi/extensions/figgsite.ts` registers five tools, invoked by the bridge
with `-e` and `--no-builtin-tools` so a site visitor gets the pipeline and
**no shell, no edit, no write**:

`figg_pipeline_status` · `figg_upload_photo` · `figg_start_mesh` ·
`figg_mesh_status` · `figg_products`

`figg_upload_photo` is the only tool that touches disk, and it resolves
symlinks then requires the file to be inside `FIGG_UPLOAD_DIR`.

## Free tier — the wedge

Generation is free, physical is the revenue. **Measured cost per video: $0.**

```
GET  /api/voices                voice library + scenes
GET  /api/credits?owner=…       daily balance (mesh / video / upload)
POST /api/videos                {mesh_id, topic, voice, scene} → mp4
GET  /api/videos?owner=…        a user's renders
GET  /api/videos/<id>/file      download
```

| component | how | cost |
|---|---|---|
| script | our LLM (`mimo-v2.5` via the vault key) | $0 |
| voice | **edge-tts — 324 voices, no key, no GPU** | $0 |
| frame | PIL, figg branding + the pet's photo | $0 |
| render | ffmpeg still-frame + audio → h264/aac | $0 |
| lip sync | needs a GPU this box doesn't have → Kaggle or fal | — |

Free renders carry a watermark (`WATERMARK_FREE=1`); paid unlocks don't.
`FREE_MESH_PER_DAY=3` (real Meshy credits) and `FREE_VIDEO_PER_DAY=5`
(ours cost nothing — an abuse limit, not a budget one).

The Kaggle kernel for voice **cloning** is written and waiting:
`kaggle-qwen/qwen_kaggle.py`, kernel `priortrades/qwen-bank-render-v1`, GPU on —
it needs an `HF_TOKEN` secret attached. Presets need nothing.

Measured end to end: **46s, 17.6s MP4, 596 KB, 1080×1920, watermark verified,
credit 5 → 4.**

### Per-account storage

Every asset lives under its owner's own prefix — their personal slice of R2:

```
owners/<owner>/photos/<sha[:2]>/<sha>.jpg
owners/<owner>/meshes/<mesh_id>/model.glb
```

Listed via `GET /api/credits?owner=…` (`assets_stored`). Old pre-namespace
test objects were removed; `owners/` is now the only top-level prefix.

### Known gaps

- **Lip sync** (SadTalker/Wav2Lip) needs GPU — Kaggle free tier (30h/week,
  9h sessions, cold starts) is fine for batch/alpha, not a live API.
- **Meshy still keyless** — `meshy.py` runs its stub, so the "pet" in a video
  is the photo, not a sculpt.
- **AR + Stripe + Google OAuth** still absent from the vault.

## The hookup (what changed)

`site/index.html` called Cloudflare Workers AI directly:

```js
fetch('https://mythicbee-proxy.tradesprior.workers.dev/api/ai/cf/@cf/meta/llama-3.3-70b-instruct-fp8-fast', ...)
fetch('https://mythicbee-proxy.tradesprior.workers.dev/api/ai/cf/@cf/openai/whisper', ...)
```

Now relative, so they hit the bridge on the same origin:

```js
fetch('/api/ai/cf/@cf/meta/llama-3.3-70b-instruct-fp8-fast', ...)
fetch('/api/ai/cf/@cf/openai/whisper', ...)
```

The bridge keeps the **exact response shape** the site already expects —
`{success:true, result:{response}}` — so `index.html` needed no other edit.
The model name in the path is ignored; every call goes to pi in print mode
with `--no-tools --no-session` (a site visitor must never get a shell).

## Front end (single file, `site/index.html`)

Themed **pogpet** with a Halloween palette, built as four screens in one
inline document (no build step, no framework):

```
pogboot   z300  jumbled-words loading curtain,6 phrases, 7s failsafe
greet     z200  "Welcome to the pogverse" + 3 steps + CTA
tabrail   z60   left rail — brand switcher + chat/upload/studio/shop
app       —     the original chat stage, shifted right by 72px
```

| tab | talks to | state |
|---|---|---|
| **chat** | `/api/ai/cf/*` → pi | working |
| **upload → spotlight** | `GET /api/me` · `POST /api/me/active` · upload + sculpt | working |
| **studio** | `GET /api/voices` → `POST /api/videos` → streams the mp4 | working |
| **shop** | `GET /api/products` → Prodigi mockups + mesh bindings | working |

**Avatar spotlight** — the upload tab is a roster screen. Every sculpted pog
is a thumb, one is lit with a pulsing halo; clicking one calls
`POST /api/me/active` and that mesh is what appears on every product from
then on. `profiles.active_mesh_id` is the single switch.

**Shop = Prodigi**, 12 items (greeting card, postcard, sticker, framed print,
poster, photo tile, cushion, mug, tote, notebook, jigsaw, **wrapping paper**),
each a server-side mockup with the *active* pog on it — `backend/mockup.py`,
cached at `owners/<you>/products/<item>.png`. Prices carry **EST** (no live
Prodigi key to quote against); wrapping paper is grade Q per
`docs/prodigi-tiers.md:36`. Underneath those sit the eight products bound
straight to the mesh.

### One public token

The bridge injects `window.__FIGG_TOKEN` and patches `window.fetch`, so the
browser holds **one** secret. `/backend/*` is gated on it; the bridge then
strips it and substitutes `API_TOKEN` when proxying, so **`API_TOKEN` never
reaches the client** (verified: 0 occurrences in served HTML).

`<img src>` doesn't go through `fetch`, so shop images carry the token
explicitly via `art()` — that was silently 401ing every card until fixed.

The top-left **`p.`** opens a switcher between `pog.pet` and `pog.town`.
`pog.town` isn't served by this app yet — the link points at the domain.

Verified end to end through the same calls the UI makes: upload → sculpt
(succeeded in 3s) → shop returns 8 products → studio rendered a **14.2s,
1080×1920, watermarked, $0** mp4 in 20.7s → file downloads as `video/mp4`.

Branding source: `pogpet`, character **Pogo**, role *Spooky Season*. The
mythicbee copy came from `stallspy/brands/mythicbee`; the numbered
"1. Upload your pet" step pattern is lifted from bwick's Roast.pet Card
Studio (`bwick/engine/card-studio/static/index.html`).

Internal ids (`bee-status`, `hive-signal`, `session.bee`) still say "bee" —
renaming them ripples through working JS for no user-visible gain.

## Blockers

1. **`MESHY_API_KEY` — the only one that matters.** Not in the vault, not in
   any `.env`, 0 hits box-wide. Until it lands, `meshy.py` synthesizes a valid
   GLB so the whole chain runs; set the key and it flips to live with **no code
   change** (same `create_task` / `get_task` / `extract_artifacts` path).
   Also blocks the Creative Lab chibi track and the video/card renders.
2. **Voice.** `/api/ai/cf/@cf/openai/whisper` returns `success:false`, so the
   site falls back to typing. No local STT wired.
3. **R2 credentials** pasted into chat on 2026-09-28 are burned — rotate. They
   live in the rclone remote (`r2:`), not in this repo; `.env.example` has
   placeholders only and a secret scan is clean.

### Resolved

- ~~`402 Insufficient account funds`~~ — the vault held five `opencode-go` keys
  (`LLM_KEY`…`LLM_KEY_5`, Fernet-sealed in `~/.qpbot/vault.json`). Tried in
  order: `LLM_KEY` works. Two bugs behind the 402: the pi extension declared
  `api: "openai-responses"` while `mimo-v2.5` only speaks `chat/completions`,
  and `~/.pi/agent/models.json` carries a stale `apiKey` that beats the env var
  (the bridge now passes `--api-key` explicitly).
- ~~project-local extension discovery~~ — cwd/`.pi/extensions` picks up nothing
  in this pi build (a trivial probe file is ignored, `tps.ts` / `redraws.ts` /
  `prompt-url-widget.ts` were never loading either); `--extension` works, so the
  bridge passes `-e` explicitly.

## Not imported (on purpose)

- `site/js/*.js` (21 files) are **unreferenced** by `index.html` — a parallel
  modular build. Left in place but inert; the live app is the inline script.
- `site/node_modules` present but gitignored.
- `stallspy` itself — already cloned at `/home/ubuntu/stallspy` and in sync
  with `prx0r/stallspy@a8db464`.

## Hosting

**Live: `https://pog.pet`** — proxied through Cloudflare, one URL for everything.

```
https://pog.pet/            product site      https://pog.pet/studio/    figg. brand studio
https://pog.pet/api/ai/cf/* pi agent          https://pog.pet/backend/*  → proxied to API on 8798
www.pog.pet                 same
```

| | |
|---|---|
| Zone | `abadc6500da5fdac89a74bbfa5bfd49e`, **active** since 2026-09-28 22:45 UTC |
| NS | `gina.ns.cloudflare.com` · `pete.ns.cloudflare.com` (moved from Namecheap) |
| Tunnel | `figgsite` = `54295d83-e7e7-4741-b148-9e0ccf4382f2`, config `~/.cloudflared/figgsite.yml` |
| Cert | Let's Encrypt YE1, 2026-09-28 → 2026-12-27 (Universal SSL, auto-renews) |
| SSL mode | `full` · `always_use_https` = on |

Created non-interactively — `cloudflared tunnel login` was never needed. The
zone was made with `POST /zones` (the token needs `account.id` in the body,
otherwise it 1067s), the tunnel with `POST /accounts/{id}/cfd_tunnel`, its
credentials hand-assembled as `{AccountTag, TunnelID, TunnelSecret}`, and the
CNAMEs written directly via the DNS records API.

**Fallback during setup:** `https://captain-per-lighter-divide.trycloudflare.com`
(a quick tunnel to the same origin) — no longer needed now the domain resolves.

The bridge injects a `window.fetch` patch into served HTML so same-origin
`/api/` calls carry the gate token — no secret is written into any source
file. Anyone holding the URL holds the token. **On a stable public domain
that's not good enough** — put the AI route behind real auth before this
gets traffic; today it's a personal demo.

### Other domains in the plan

| domain | state |
|---|---|
| `pog.pet` | ✅ live |
| `pog.town` | registered at Porkbun, **not yet on Cloudflare** |
| `pogtown.com` | **not registered** — needs a purchase (~$10–15) |
