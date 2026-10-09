# Studio MCP Spec — prompt → Blender + Meshy + Fal + web hands

> Status: SPEC v2 (2026-10-09). Nothing built, nothing spent.
> Endgame: own studio — talk to the assistant, watch it work in Blender,
> Meshy + Fal behind explicit spend gates, web hands where APIs gap,
> prompt-to-edit. Pi builds the glue; harnesses do the clicking.

## 0. Stack decision (researched 2026-10-09)

**Blender hands — `blender-agent` (Rich-Siomporas, Blender Projects), run as
a separate service, never vendored.** Self-hosted harness + browser web UI
(`:10102`), MCP over HTTP (`:10101`) shared by any number of clients,
OpenAI-compatible chat API, bring-your-own LLM (remote endpoint or
in-browser WebGPU, zero key), spawns its own headless Blender, Docker image
bundles Blender + ffmpeg, confirm gate for destructive actions, artifacts
panel for renders/exports. It is **GPL-3.0** — talk to it over HTTP/MCP,
do not copy its code into this repo (same law as AGPL: patterns only).
Fallback if it disappoints: `ahujasid/mcp-for-blender` (MIT, 9 tools,
`uvx`, safe mode) + our own harness.

**Web hands — Steel (self-hosted) + Gemini Flash CUA.** Steel core is
Apache-2.0, Docker on our hardware ($0), captchas + persistent logins + 24h
sessions. Eyes: Gemini 3.5 Flash computer-use ($0.01–0.08/task), Claude
fallback for hard pages (Eden AI one-endpoint fallback chain). Rule: API
where an API exists (Printie, Etsy, Shopify — $0.01/call beats ~$2.70 for
a 10-min visual session); computer-use only where it doesn't.

**Rejected:** Hark/Handoff (closed consumer product, no builder API, no
Blender). Admire, don't plan on it.

Our studio MCP stays the orchestrator; harnesses are the hands.
Never reimplement Blender control — wrap it with spend gates + product flow.

## 1. Target architecture

```
You → Studio UI → Studio MCP (orchestrator; Pi builds this glue)
  ├── blender.*  → blender-agent service (:10101 MCP-HTTP, :10102 web UI)
  │                 → headless Blender it spawns; screenshots back
  ├── web.*      → Steel service (self-host) + Gemini Flash CUA
  │                 → supplier/Etsy pages only where APIs gap
  ├── meshy.*    → backend/meshy.py (exists, key-gated, ledgered)
  ├── fal.*      → new backend/fal.py (image edit/inpaint, TTS previews)
  └── oddhobb.*  → existing (add_hook amend, render_product, premesh, prodigi)
```

Blender + browsers need a machine with GPU — not this box (no Blender, no
GPU). Harnesses run there (Docker); studio MCP + UI run anywhere.

## 2. MCP tool surface

**Blender (via blender-agent service, confirm gate on):**
- `blender.exec {code}` — gated code execution, confirm file/network ops
- `blender.look {view, mode}` — screenshot back, shown in studio UI
- `blender.scene` — compact scene summary before/after every edit
- `blender.render {engine, out}` — stills/video (ffmpeg included) → `data/marketing/`

**Web (via Steel + CUA, API-gap only):**
- `web.act {url, instruction}` — supplier/Etsy pages with no usable API
- `web.extract {url, schema}` — structured data back (prices, order status)
- Budget guard: flag any session projected over $1; prefer API always.

**Meshy (wrapped, spend-gated — docs/meshy.md rules stay):**
- `meshy.balance` — free, always allowed, studio header
- `meshy.prototype {photo}` — 6cr, explicit go required
- `meshy.build {prototype_id}` — 30cr, explicit go required
- `meshy.status {task_id}` — free poll
- Every spend → `data/meshy_credits.jsonl` + delta reported.
  Disable all other Meshy paths (incl. bridge built-ins); ours is the only route.

**Fal (new, same gating as Meshy):**
- `fal.image_edit {image, prompt}` — listing-photo touch-ups, backgrounds
- `fal.upscale {image}` — 2000×2000 Etsy stills from renders
- `fal.tts {text, voice}` — casting-side demos only, never narrator voices
- Key in `.env` 0600, never auto-called without owner OK.

**Product (exists, expose in studio):**
- `oddhobb.amend` → `scripts/add_hook.py` (Blender headless, 0 credits)
- `oddhobb.render` → `scripts/render_product.py` (Cycles, CPU)
- `oddhobb.quote` → Prodigi live pricing

## 3. Studio UI

Extend `figg-studio/`, four panes:
1. **Prompt box** → tool calls stream below it
2. **Viewport** — latest `blender.look` screenshot, auto-refresh after exec
3. **Queue** — Meshy/Fal jobs with cost, approve/deny = spend gate in UI form
4. **Credits** — Meshy balance + session spend + Fal spend, always visible

Every action: code shown → executed → screenshot shown → approve or "undo".
Undo via Blender undo stack + pre-edit `.blend` snapshots for destructive ops.

## 4. Build order

| Phase | Work | Done when |
|---|---|---|
| 0. Bench | GPU machine: blender-agent Docker + Steel Docker; "make a cube red" → screenshot; Steel loads a supplier page → extract a price | Prompt → Blender → screenshot AND prompt → web → data both work |
| 1. Passthrough | `blender.*` + `web.*` wrappers in `backend/mcp_server.py`; render output into `data/marketing/` | Existing render flow + one API-gap page drivable by prompt |
| 2. Meshy gate | `meshy.*` with balance-first + approval + ledger | First gated prototype→build, credits logged |
| 3. Fal | `backend/fal.py`, same key/ledger discipline | Render → Fal touch-up → 2000×2000 pack |
| 4. Studio page | Four-pane UI (+ web view), approvals, credit meter, snapshots | "New keychain variant" by conversation |

## 5. Costs & keys

- Blender harness + Steel: $0 (GPL service / Apache-2.0 self-host, local compute).
- Web eyes: Gemini Flash CUA ~$0.01–0.08/task, Claude fallback. Budget guard $1/session.
- Meshy: 6cr prototype + 30cr build; `/balance` free. Key LOCKED, every call needs go.
- Fal: pay-per-call, stored key, never auto-used.
- GPU: cost is wherever Docker harnesses run. Phase 0 picks the machine.

## 6. Open owner calls

1. Which machine runs the Docker harnesses (workstation vs GPU box)?
2. BYO LLM for blender-agent: remote endpoint or in-browser WebGPU (zero key)?
3. Fal session budget cap (suggest $5, UI-enforced)?
