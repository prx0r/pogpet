# AGENTS.md — pog.pet (figgsite)

> **Read `HANDOVER.md` first** — status, what's running, what's next.
> This file is the map and the rules. Detail lives in `BUILD_NOTES.md`,
> product truth in `README.md`, the normaliser in `premesh/README.md`.

## What this is

**oddhobb.com** — the brand is **oddhobb** (never: pogpet, bwick, figg-studio).
photo (or preset, or GLB) in → mesh out → active across 13 products → stage
(comedy/dance/singing) → print files. Live via Cloudflare named tunnel at
https://oddhobb.com (NS pending as of 2026-09-30) with https://pog.pet as the
existing alias — same app, same bridge. `$0 marginal cost` end to end;
Meshy is the only paid step and it is currently **stubbed** (no key).

Repo: **github.com/prx0r/pogpet** (public). Baseline `6542c06`.

## Run it

```bash
./serve.sh                                     # bridge :8797 + Flask :8798
set -a; . ./.env; set +a; python3 -m backend.mcp_server   # MCP :8799 local-only (MCP_HTTP=1)
# ...public MCP for ChatGPT/Claude: https://mcp.oddhobb.com/mcp?token=$(cat .token)  (docs/mcp.md)
cloudflared tunnel --config ~/.cloudflared/figgsite.yml run figgsite
```

One process serves site + `/studio/` + `/premesh/` + proxies `/backend/*` to
Flask. `/backend/*` is gated on `BRIDGE_TOKEN` (`.token`); the bridge swaps in
`API_TOKEN` so exactly one secret is ever public — the browser only ever holds
`window.__FIGG_TOKEN`.

## Map

| Path | What |
|---|---|
| `backend/server.py` | 42 routes: photos → meshes → products → stage → print |
| `backend/meshy.py` | Meshy client — `create_task(…, chibi=True)` is the Creative Lab figure track; synthesises a valid GLB while `MESHY_API_KEY` is empty |
| `backend/intake.py` | upload QC: magic bytes, EXIF, 256px floor, flat-frame reject, sha256 dedupe |
| `premesh/` | **image normaliser** (standalone: PIL+stdlib only) — see below |
| `bridge/llm_bridge.py` | static roots + `/backend` proxy + the fetch/token patch |
| `scripts/` | `add_hook.py` (amend: loop+ballast) · `meshy_figure.py` (chibi run) · `render_product.py` (Cycles product shots) |
| `site/`, `figg-studio/` | product frontend, brand kit (served at `/`, `/studio/`) |
| `data/` | runtime only: sqlite, photos, meshes, staged images — **gitignored, never commit** |
| `dash/`, `pi/` | vendored from qpbot (provenance headers) |

## premesh — the reusable image module

One job: uploaded photo → what the next stage needs. `normalize(source, recipe)`.

- **Sources:** local path · bytes · any public URL · **Pixabay page URL**
  (resolved through the API with `PIXABAY_API_KEY`, licence flags in `meta`).
- **Recipes:** `meshy` (subject cut, centred, ≥1024, transparent) · `card`
  (cut-out, ≤1600, uncropped — greeting cards) · `thumb` (≤512 JPEG).
- **CLI:** `python3 -m premesh photo.jpg -o out/ -r meshy`
- **Route:** `POST /api/premesh` — multipart `photo`, or `?url=`; `format=json`
  for report+base64, `strict=1` for 422-on-QC-fail; binary responses carry
  `X-Premesh-Ok/Recipe/Coverage`.
- Everything runs at the Cloudflare edge (`segment=foreground`, `trim`,
  `fit`, `upscale=generate`) — 5,000 unique transformations/month free.

**Do not break:** AI upscale must stay a *prelude* (after `segment` it drops
the alpha); trust `report.fmt` for content-type, never the options (the zone
ignores `format=`); stage files are content-addressed so the same photo never
pays twice.

## Keys & status

| Key | Where | State |
|---|---|---|
| `MESHY_API_KEY` | `.env` | **set — LOCKED. Ask the user before every call.** See `docs/meshy.md` |
| `PIXABAY_API_KEY` | `.env` | live — free-licence stock for demos/tests (free API, no credits) |
| `PRODIGI_*`, `OPENCODE_*` | `.env` | live |
| `GOOGLE_CLIENT_ID/SECRET` | `.env` | empty — sign-in returns 501 |

`.env` and `.token` are 0600 and gitignored. Never print key values, never
commit them, never let `API_TOKEN` reach the client.

## Money rules — Meshy (real credits)

Full guide: **`docs/meshy.md`**. Non-negotiable, for every agent:

1. **Always ask the user before using the Meshy key** — before a task call,
   before a build, before anything that can spend. No exceptions, even when
   a run is "obviously next". `/balance` is the only free endpoint, and even
   that waits for the user's go-ahead in a new session.
2. **Track credit usage.** Append every spend to
   **`data/meshy_credits.jsonl`** (`{ts, stage, task_id, credits, source,
   recipe, asked:true, balance_after}`) and report the delta to the user.
   Show the running total before a run.
3. **Never store the key outside `.env`** — not in docs, tests, scripts,
   history, or chat-pasted files. Never echo it. `.env` must stay gitignored
   (check with `git check-ignore .env` after any edit).
4. **No key, no problem:** empty `MESHY_API_KEY` flips `backend/meshy.py`
   into its offline stub — use that for development and tests.
5. **Amend is Blender-only.** Hook/hole/scale/orient (`scripts/add_hook.py`)
   runs in local Blender — **0 credits, ever**. The Meshy plugin's local
   operators (`meshy_check_solid`, `meshy_check_all`, hollow, export) are
   offline too. Only the plugin's *Bridge* touches Meshy — never use it
   without asking. Meshy is for prototype (6 cr) and build (30 cr) only.

Before trusting a key at all: `GET /openapi/v1/balance` must not answer
`Invalid API key` (a Pixabay key failed exactly this way once).

## Rules

1. **Commit only when asked.** Remote is public — `git diff` before every push;
   `data/`, `.env`, `.token` must never appear in it (verified by
   `git check-ignore`).
2. **Sibling repos are read-only:** `petsy`, `stallspy`, `qpbot`, `freaktown`,
   `bwick`, `pow*`. Vendored copies live *here* with provenance headers.
3. **Prices without a `sku` are EST**, always labelled. Never present them as
   verified. Wrapping paper is grade Q.
4. User content never leaves `data/` except through an authenticated route.
   The one public exception is `/premesh/<content-addressed>` (128-bit hash,
   pruned by `stage.prune()` — still unwired, see BUILD_NOTES).
5. Specs and protocols in this repo: **`docs/meshy.md`** (Meshy API + spend rules),
   **`docs/balance.md`** (foolproof hang/ballast protocol — run
   `scripts/add_hook.py --ballast`, follow the PAUSE AT HEIGHT it prints; loop
   sizing standards live there too), **`docs/rendering.md`** (Cycles render
   recipe + image-verification tag protocol — read before rendering),
   **`docs/how-it-works.md`** (the map — start here), **`docs/foundation.md`**
   (catalog/flow/manifest), **`docs/navigation.md`** (sections/subdomains),
   **`docs/muse-mcp-design.md`** (MCP = product contract, agent-first),
   **`docs/unimate.md`** (planned stage-animation model — spec only, all spend gated).
6. Docs/mirrors outside the repo: **`/home/ubuntu/meshy-docs`** (Meshy docs,
   106 pages, start at `INDEX.md`; API in `md/en__api__*.md`) — refresh with
   the script noted in its header. Our own Meshy conventions live in
   **`docs/meshy.md`** (the mirror is not committed: Meshy's docs are
   copyrighted and re-fetchable).

## Machine extras

- **Blender 4.2.9** at `opt/blender-4.2.9-linux-x64` (the one `usdz.py`
  wants) with the **official Meshy plugin v0.6.1** installed and enabled as
  extension `bl_ext.user_default.meshy` — bridge + print-prep operators
  (`meshy_check_all`, `meshy_hollow`, `meshy_clean_non_manifold`, STL export).
  Linux is "not officially supported" by Meshy but it loads and registers.
- Disk is tight (~12G free) — check `df -h` before big downloads.

## Verify after any change

```bash
python3 scripts/test_site.py            # full pass: 37 checks, 0 credits
#   (report lands in docs/test-report.md; exits non-zero on any FAIL)

curl -s localhost:8798/health            # meshy: stub|live, counts
curl -s -o /dev/null -w '%{http_code}\n' https://pog.pet/
grep -c Traceback /tmp/opencode/api.log  # want 0
TOK=$(cat .token); curl -s -o /dev/null -w '%{http_code}\n' \
  "https://pog.pet/backend/api/styles?token=$TOK"
python3 -m premesh /tmp/opencode/chibi/golden.jpg -r meshy --no-save   # want OK
```
