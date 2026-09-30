# figgsite codebase audit — 2026-09-30

Full deep-dive of **github.com/prx0r/pogpet** (working tree: `/home/ubuntu/figgsite`).
Method: read every core module, live probes against the running stack
(bridge :8797 → Flask :8798 → MCP :8799, tunnelled at oddhobb.com/pog.pet),
full `scripts/test_site.py` run (**55/55 PASS**), git/DB/ledger inspection.
No Meshy spend, no code changes outside this document + todo Round 6.

---

## 1. What the audit covered

| Area | Files | Method |
|---|---|---|
| HTTP API | `backend/server.py` (1690 L, 45 routes) | route inventory vs test coverage |
| Bridge/tunnel | `bridge/llm_bridge.py` (429 L) | path traversal probes, token flow |
| Auth | `backend/auth.py`, `server.py` OAuth block | state validation, key handling |
| Money | `backend/meshy.py`, `pipeline.py`, `db.py` credits, `data/meshy_credits.jsonl` | ledger read, refund paths |
| Storage | `backend/storage.py`, `intake.py`, `server.py` artifacts | private-R2 gateway, QC |
| Agents/MCP | `backend/mcp_server.py` (20 tools) | service-token abuse probe |
| Multi-brand | `backend/config.py` BRANDS, `/api/brand`, `site/index.html` | Host-header matrix |
| Feeds/Shopify | `_feed_items`, `shopify-app/`, `ODDHOBB.md` | public feed smoke, scaffold state |
| Frontend | `site/index.html` (2026 L) | brand seam, token injection |
| Vendored trees | `dash/`, `pi/`, `figg-studio/`, `site/node_modules/` | purpose + risk review |
| Live behaviour | login ×5, artifact traversal ×4, owner-spoof read, MCP foreign-mesh start | evidence below |

---

## 2. Verdict in one paragraph

The **product core is real**: modular pipeline (photo → QC → R2 → mesh → products → video),
race-safe free-tier credits, pbkdf2 passwords, private artifacts behind a gated gateway,
a working multi-brand seam, public feeds for shopping agents, MCP behind a token gate, and a
suite that actually exercises the live tunnel. The **money and trust edges are not real yet**:
there is no checkout anywhere, `PUBLIC_BASE` still emits pog.pet URLs, anyone holding the
page token can act as any `owner` (including burning *their* sculpt quota), login has no
rate limit, the public repo carries off-mission vendored code (`dash/`), and several
"done" claims in README/HANDOVER are stale relative to the running system. Meshy spend
discipline held: ledger shows only the documented dog-mesh spend, balance 1,056, `asked: true`
on every entry.

---

## 3. Verified strengths (evidence)

- **Test suite is honest about the live edge** — `55/55` today, including public
  `/api/brand`, feeds without token, MCP 401 without token, bad-token 401 on the API,
  and a final oddhobb.com smoke. Report: `docs/test-report.md`.
- **Token discipline at the bridge** — browser only ever holds `BRIDGE_TOKEN`;
  `_proxy` strips inbound tokens and re-injects `API_TOKEN` server-side
  (`bridge/llm_bridge.py:215-233`). MCP proxy strips tokens the same way
  (`:161-172`).
- **Path traversal holds on static serving and artifacts** — bridge
  `(root/rel).resolve()` + prefix check (`llm_bridge.py:311-314`); artifacts rejects
  `..`, leading `/`, `//` (`server.py:1568`). Live: `../.env` → 404,
  `..%2f.env` → 400, `owners/../../.env` → 404.
- **Intake QC is real** — magic-byte sniff, mime allowlist, EXIF strip, downscale,
  dedupe by processed-hash (`intake.py`), daily upload cap.
- **Passwords** — pbkdf2-sha256 200k rounds, `hmac.compare_digest` (`db.py:249-263`).
- **Google OAuth state** — one-shot dict with 600s TTL, popped on callback
  (`server.py:1136,1171-1187`); bad state → 400.
- **Multi-brand seam works** — `brand_for()` unit-proven in suite; live tunnel returns
  the right record per Host; unknown hosts fall back safely; premesh zones follow Host
  (regression 200).
- **Money ledger** — 3 entries, all `asked: true`, balance chain 1086→1056;
  video path refunds on post-spend failure (`server.py:1491,1495`).
- **Private artifacts** — R2 objects served only via gated `/api/artifacts/<key>`;
  feeds use a separate public mirror (`data/productimg/` → `/img/`), never user photos.

---

## 4. Findings (severity-ordered)

### HIGH — trust / money / exposure

**H1. Owner spoofing is the whole trust model.** Any caller with the page token
(every visitor gets it via `window.__FIGG_TOKEN`) can pass `owner=` to reads and,
through MCP's service token, to *writes*. Live evidence:
- `GET /api/meshes?owner=prx0r` → `ok:true count:1` with no user key.
- MCP `figg_start_mesh` with a **foreign** `photo_id` (`pho_ead82da…`) → returned
  prx0r's mesh via the service-token path. Credit spend is charged to the *photo's*
  owner (`pipeline.py:54-58`), so a visitor can burn someone else's daily sculpt
  allowance.
- `POST /api/videos` accepted `owner: "carol"` + unknown mesh (400 only for missing
  mesh — no ownership check before credit spend).
Fix direction: signed owner cookie or API key required on all credit-burning routes;
MCP tools must pass a principal, not a free-text owner.

**H2. No login / account rate limiting.** Five consecutive bad passwords → five 401s,
no backoff, no lockout, no per-IP cap (`server.py:950-968`). Combined with H3 this is
brute-forceable.

**H3. API key in URL + token in page source.** Google callback hands the key back as
`?auth=<api_key>&handle=` (`server.py:1183-1186`) — lands in history, logs, referrers.
Bridge injects the gate token into every HTML response (`llm_bridge.py:332-349`) —
view-source is a full credential. Mitigated only by "page origin is ours".

**H4. Email not UNIQUE + no deletion path.** `users.email` has no unique index
(`db.py:110-114`); `_ensure_google_user` queries by email but a race can fork
accounts. There is **no GDPR-style delete** for photos/meshes/videos — uploads are
personal data (pet + often human faces in the people grid).

### MEDIUM — correctness / completeness

**M1. Revenue path does not exist.** GTM inspo says physical is the revenue;
`AGENT_PERMISSIONS["products:order"]` literally reads "needs Stripe — not yet"
(`config.py:112`). Prodigi `quote`/`check` are live, but nothing places an order.
Shop prices still EST. This is the single largest gap between strategy and code.

**M2. `PUBLIC_BASE` still `https://pog.pet`.** Feeds' `link`, product image URLs,
OAuth redirect URI, and `?auth=` landing all emit pog.pet, not oddhobb.com
(`config.py:70`, `_feed_items` host fallback, `auth.redirect_uri()`). Google Merchant
feed currently points shopping agents at the wrong domain.

**M3. Watermark + studio brand still "figg."** Free videos burn
`"free preview — figg."` (`video.py:255`); `/studio/` serves the figg. asset pack;
AGENTS.md says the brand is oddhobb and *never* figg-studio. ochema.co would render
oddhobb-branded strings on any path not covered by the new `/api/brand` repaint
(feeds, watermark, llms.txt, section hosts are still oddhobb-only).

**M4. Test coverage is ~1/3 of the API.** 45 routes; the suite hits roughly 15.
Never tested end-to-end: accounts create/login/claim, agent mint/permissions/revoke,
`POST /api/videos` success + refund, prodigi quote/check, styles install, GLB upload,
credits semantics, OAuth state rejection, artifacts traversal (manual only today),
autosort algorithm correctness, turntable/usdz/print export, concepts/listing-pack,
`/api/run`, voices. **MCP `figg_flow` has a soft-pass**: on SSE timeout it records
PASS with "no SSE data in 12s" (`test_site.py:407-408`) — theatre risk in the suite
itself.

**M5. Single-process assumptions.** OAuth state is an in-process dict (restart drops
pending sign-ins; multi-worker would break it). Turntable worker swallows every
exception (`server.py:513-514`). Job table has `attempts` but no visibility endpoint.
SQLite WAL files live in `data/` with no documented backup/restore drill.

**M6. Repo hygiene on a public GitHub remote.** 15 modified/untracked paths vs a
single baseline commit `6542c06`; `shopify-app/`, `premesh/`, `scripts/`, `docs/`,
`site/llms.txt`, `AGENTS.md` are **untracked** — the work of this whole session is
not in git. `site/node_modules/` (12 MB, motion/framer-motion) is dead weight
(index.html never imports it). README claims Meshy is stubbed and the frontend is
the "imported MogMug build" — both false now.

**M7. Vendored off-mission code in the product repo.** `dash/` (45 tracked files)
is qpbot's agentcom: whale-wallet hunting, secret scanning, vault/"prizes",
subagent missions. It has nothing to do with oddhobb and is a liability in a public
repo. `pi/` (1723 files) is the agent runtime — documented, keep or split.
`figg-studio/` is a full figg.-brand studio — rebrand or retire.

### LOW / hygiene

- **L1.** Agent key prefix is `fagg_` (`db.py:330`) — profanity-adjacent, untested
  permission matrix (agents table is empty in the live DB).
- **L2.** No CSP / X-Frame-Options / HSTS / Referrer-Policy on bridge responses.
- **L3.** Bridge `do_OPTIONS` allows `*` for POST (`llm_bridge.py:356-360`) while
  actual GET/POST responses set no CORS headers — inconsistent, currently
  same-origin-safe.
- **L4.** `docs/trademark.md` is referenced by the concepts IP guard
  (`concepts_src.py:90-92`) but **does not exist**; every concept sits at
  `ip_check: pending`, so listing packs are blocked on a file nobody wrote.
- **L5.** Email-routing rule for ochema was created while the zone is `pending` —
  re-verify after NS flip.
- **L6.** No accessibility pass, no i18n/currency story for ochema's market,
  no load test, no backup restore drill, no content moderation beyond magic-bytes
  + flat-frame rejection.

---

## 5. Threads not explored (deliberately left open)

1. **Blender/offline render scripts** — `scripts/render_product.py`, `add_hook.py`,
   `mesh_export.py`, `r3d.py`, `usdz.py` (≈1.3k lines). Never executed by the suite;
   turntable/usdz/print/export paths untested end-to-end.
2. **UniMate** — `docs/unimate.md` written, zero code touched this session.
3. **Etsy wedge** — GTM names it; zero code.
4. **Per-brand section rails** — ochema may want its own category hosts; `SECTIONS`
   is oddhobb-only today.
5. **Prodigi order placement** — only `quote`/`check` exist; `/v4.0/orders` never
   called; SKU list needs the user's dashboard.
6. **Concurrent load** — job worker + turntable threads + WAL under real traffic:
   never measured.
7. **R2 cost/quota monitoring** — storage bill has no guardrail endpoint.
8. **Meshy quality at scale** — one real mesh (42 cr). No batch QC, no failure-rate
   tracking beyond the ledger.
9. **dash/agentcom as a product** — imported wholesale; never audited as if it were
   ours (it shouldn't ship with this repo).
10. **figg-studio tooling** — `build_assets.py`, `visual_test.py`, packaging script:
    unused while the brand is oddhobb.

---

## 6. Theatre register (looks done / isn't)

| Claim | Reality |
|---|---|
| "Shopify app" ready | Scaffold only, **untracked**, never synced; needs store + Admin token |
| "Agent compatibility" | Contract shape verified; no Muse/ChatGPT ever connected; H1 lets agents act as anyone |
| "oddhobb.com live" | Yes, but feeds/OAuth/images still emit **pog.pet** URLs |
| "Multi-brand ready" | Seam live for painted strings; watermark/feeds/llms/section hosts still oddhobb/pog.pet |
| "Meshy live" vs docs | Key is set and a real mesh exists; README/AGENTS.md still say stubbed |
| "54/54 green" | Now 55/55, but ~30 routes untested + one MCP soft-pass branch |
| "products:order" permission | Exists in the manifest; no order code path at all |
| figg-studio / "figg." assets | Served publicly; contradicts the oddhobb brand rule |
| dash/ vendored "dashboard" | Off-mission secret-scanning kit sitting in a pet-figurine repo |

---

## 7. Money audit (explicit)

- Ledger `data/meshy_credits.jsonl`: 3 lines — prototype 6 cr, build 30 cr, plus the
  earlier mesh entry; balance chain ends **1,056**; every line `"asked": true`,
  `"ok": true`. No unauthorised spend found in this session or the DB.
- Free-tier credits (db `credits` table) are fixture rows (carol/dave/pogdemo) from
  earlier demos — harmless, but they show the spend path works.
- Prodigi: key present and verified working; no money moves until an order endpoint
  exists (it doesn't).
- **No Meshy calls were made during this audit.**

---

## 8. The 10 to-dos (Round 6)

| # | To-do | Why (finding) |
|---|---|---|
| R6-1 | **Close owner spoofing** — require user API key or signed owner cookie on `POST /api/photos`, `/api/meshes`, `/api/videos`, `/api/meshes/glb`, `/api/meshes/style`; MCP tools carry a principal, not free-text `owner`. Test: foreign-owner write → 401/403 | H1 |
| R6-2 | **Kill token-in-URL and token-in-page-source** — HttpOnly session cookie set by the bridge on first visit; stop injecting `BRIDGE_TOKEN` into HTML; Google callback uses a one-time code, not `?auth=<api_key>`. Test: view-source has no token; browser flow still works | H3 |
| R6-3 | **Login/account hardening** — per-IP + per-handle backoff on `POST /api/accounts/login` and `/api/accounts`; UNIQUE index on `lower(email)` where non-empty + migration; lockout table | H2, H4 |
| R6-4 | **Revenue first proof** — pull real SKUs from the Prodigi dashboard into `PRODIGI_PRODUCTS`, flip shop EST → live quotes, add one checkout handoff (Shopify product page or Stripe test mode). The GTM wedge has zero code today | M1 |
| R6-5 | **Test suite depth** — cover the ~30 untested routes (accounts, agents, videos + refund, prodigi, styles, glb upload, credits, OAuth state, artifacts traversal in-suite, autosort correctness); **remove the MCP figg_flow soft-pass** — timeout must FAIL | M4 |
| R6-6 | **PUBLIC_BASE + brand sweep** — after Google console redirect update, set `PUBLIC_BASE=https://oddhobb.com`; parametrize `_feed_items` links, watermark text, llms.txt, section hosts, og:url per `BRANDS` entry so ochema.co is fully branded with no code change | M2, M3 |
| R6-7 | **Repo hygiene** — move `dash/` out of the public repo (off-mission); decide `pi/` (keep or split) and `figg-studio/` (rebrand/retire); delete unused `site/node_modules`; refresh stale README/AGENTS.md claims; **commit the untracked session work** when you say go | M6, M7 |
| R6-8 | **ochema.co completion** — after NS at Namecheap: verify zone ACTIVE, MX/routing, smoke brand paint on `https://ochema.co/`, add section-host mapping if needed, Pinterest verification meta for ochema | R5-9 |
| R6-9 | **IP/legal gate** — write the missing `docs/trademark.md`; clear `ip_check: pending` concepts before any listing pack; add privacy/terms + a **data-deletion endpoint** (photos/meshes/videos by owner) before public marketing | L4, H4 |
| R6-10 | **Ops resilience** — surface job failures (`/api/jobs` or flow field), stop swallowing turntable exceptions, backup/restore runbook for `figg.db` + ledger, log rotation, one documented process supervisor for bridge+backend+MCP, CI hook running `scripts/test_site.py` on push | M5, L-series |

---

## 9. How this audit was run (repro)

```bash
cd /home/ubuntu/figgsite
python3 scripts/test_site.py          # 55/55 → docs/test-report.md
# live probes (service token from .token; API token from .env):
#   artifact traversal ×4, owner-spoof mesh read, 5× bad login,
#   MCP figg_start_mesh on foreign photo_id
# DB/ledger: sqlite3 data/figg.db … ; tail data/meshy_credits.jsonl
# git: git status / git ls-files | wc -l (2014 tracked, 15 dirty)
```

**Scope note:** this audit and Round 6 live in `figgsite/` (the project under
active development all session). No other POW repo was touched. No commits were
made — say the word and R6-7 becomes a commit plan.
