# Studio MCP Spec — prompt → Blender + Meshy + Fal

> Status: SPEC (2026-10-09). Nothing built, nothing spent.
> Endgame: own studio — talk to the assistant, watch it work in Blender,
> Meshy + Fal behind explicit spend gates, prompt-to-edit.

## 0. Bridge decision

**`ahujasid/mcp-for-blender`** (MIT, ~30k stars) as the Blender bridge.

- MIT fits the AGPL-patterns-only law. Richer alternatives (`mcp-blender`,
  `blend-ai`) are AGPL — reference only, never vendor.
- Supports OpenCode as a client, `uvx` install, 9 tools
  (`execute_blender_code`, `look`, `get_scene_info`, `generate_3d`, …),
  `BLENDER_MCP_SAFE_MODE=1` for gated code execution, viewport screenshots
  so the agent sees its own work.
- Blender Foundation's official MCP server (Blender 5.1+, Llama.cpp-oriented)
  is newer and less tooled — watch, don't build on it yet.

Our studio MCP stays the orchestrator; their bridge is the hands.
Never reimplement Blender control — wrap it with spend gates + product flow.

## 1. Target architecture

```
Prompt
  │
  ▼
Studio UI (prompt box + job queue + viewport stream + credit meter)
  │  MCP (stdio :8799 exists, + HTTP for ChatGPT/Claude)
  ▼
Studio MCP server (extend backend/mcp_server.py)
  ├── blender.*  → mcp-for-blender (uvx) → TCP :9876 → addon → bpy
  ├── meshy.*    → backend/meshy.py (exists, key-gated, ledgered)
  ├── fal.*      → new backend/fal.py (image edit/inpaint, TTS previews)
  └── oddhobb.*  → existing (add_hook amend, render_product, premesh, prodigi)
```

Blender needs a machine with screen/GPU — not this box (no Blender, no GPU).
The MCP server can run anywhere; the addon needs live Blender.

## 2. MCP tool surface

**Blender (passthrough, safe-mode on):**
- `blender.exec {code}` — gated code execution, confirm file/network ops
- `blender.look {view, mode}` — screenshot back, shown in studio UI
- `blender.scene` — compact scene summary before/after every edit
- `blender.render {engine, out}` — Cycles stills → `data/marketing/` pack flow

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
| 0. Bench | Blender 4.2+ LTS + addon on target machine; `uvx mcp-for-blender`, safe mode on; "make a cube red" → screenshot | Prompt → Blender → screenshot loop works |
| 1. Passthrough | `blender.*` wrappers in `backend/mcp_server.py`; render output into `data/marketing/` | Existing render flow drivable by prompt |
| 2. Meshy gate | `meshy.*` with balance-first + approval + ledger | First gated prototype→build, credits logged |
| 3. Fal | `backend/fal.py`, same key/ledger discipline | Render → Fal touch-up → 2000×2000 pack |
| 4. Studio page | Four-pane UI, approvals, credit meter, snapshots | "New keychain variant" by conversation |

## 5. Costs & keys

- Blender + bridge: $0 (MIT, local compute).
- Meshy: 6cr prototype + 30cr build; `/balance` free. Key LOCKED, every call needs go.
- Fal: pay-per-call, stored key, never auto-used.
- GPU: cost is wherever Blender + Cycles runs. Phase 0 picks the machine.

## 6. Open owner calls

1. Which machine runs Blender (workstation vs GPU box)?
2. mcp-for-blender confirmed, or evaluate official Blender MCP first?
3. Fal session budget cap (suggest $5, UI-enforced)?
