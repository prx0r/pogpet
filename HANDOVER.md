# HANDOVER

> **STATUS: CURRENT** — written 2026-09-29, end of the build session.
> **Start here.** What's running, what was touched, what's next.
> Detail lives in `BUILD_NOTES.md`; product system in `README.md`.
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

## Files touched this session

**Created in this repo** (nothing committed — 2,012 files staged-to-be):

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

**Yours (blocked on you):**

1. `MESHY_API_KEY` — the only thing gating photo→3D that looks like *your* pet.
   Alternatives if you'd rather not: Kaggle meshgen (free, 30h/week, not a live
   API) or Trellis/Hunyuan on fal.
2. Google client ID + secret → paste into `.env`, sign-in goes live.
3. Prodigi SKUs from your dashboard → `GET /api/prodigi/check?sku=` validates,
   then add `sku` to a product and its price flips EST → **LIVE** (canvas
   already proves the path: `GLOBAL-CAN-10X10`, £16.00, EVRi Next Day).
4. Cloudflare Access still not enabled on the account (one click) — wanted for
   `/admin` only; the public site must not go behind it.

**Mine, still open:**

- **Performance history UI** — `GET /api/videos?owner=` already returns them;
  nothing renders a list yet.
- **freaktown scoring** — wire `show_runtime` / `performance_compiler` /
  `judge` / `scoring` / `reputation` as the Perform layer. Its `show.py` is
  literally *"Live talent show for artificial personalities"*, and
  `stage/theme.json` already supports a theme switch (Halloween/Christmas/
  Midnight Carnival/Sticker Freakshow).
- **Stage themes on our own site** — only the palette is Halloween right now.
- **Fold MCP + tunnel into `serve.sh`** so one command brings the stack up.
- **Commit** — nothing has been committed all session. 2,012 files staged-to-be.

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
