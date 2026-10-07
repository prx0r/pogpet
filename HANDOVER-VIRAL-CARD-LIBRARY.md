# HANDOVER — viral card library import (2026-10-07)

## What arrived
`oddhobb_viral_card_library.zip` (42KB) from R2 `stallshark` bucket, built
against `8a78c94`. Payload: 22-premise catalog across 7 style families,
backend creative modules, style-aware renderer, Cards-tab UI, docs, tests,
installer script.

## Import decision: MERGE, not install
The bundled installer overwrites `backend/creative/{templates,briefs,matcher}.py`
and `backend/renderers/composite2d.py`. Those files carry this tree's
hardening (manifest print engine with bleed QC, panels, premise matching,
adapter max_chars, key-scoped everything). Blind install would have deleted it.
So instead:

**Copied verbatim (new files, no conflicts):**
- `templates/catalog.json` — 22 premises, 7 styles
- `backend/creative/catalog.py` — query(style/occasion/audience/tone/q)
- `site/js/viral-card-library.js` + `site/css/viral-card-library.css`
- `docs/viral-card-library.md`, `tests/test_viral_catalog.py`

**Merged by hand (ours wins on conflicts):**
- `templates.py`: kept our validator/engine, added `_presentation` +
  catalog→manifest synthesis (hand-authored manifests win, catalog enriches
  or synthesizes with a default print-safe layout).
- `briefs.py`: added `request` (buyer's actual words) end to end
  (endpoint → MCP tool).
- `matcher.py`: kept our weights, added lexical request evidence (+4/hit,
  cap 20) and `format`/`premise`/`tone` in match output.
- `composite2d.py`: kept manifest engine + panels + QC, added 8 style
  PALETTES + style branches on `render_card(style_id=)`, wired from the
  manifest taxonomy in `_render_revision` (mood palette still overrides).
- `server.py`: `/api/creative/catalog` endpoint + `request` passthrough.
- `mcp_server.py`: `figg_creative_catalog` (TOOL_AREAS + PUBLIC_TOOLS).
- `site/index.html` + `site/js/cards-studio.js`: CSS/JS includes + mount hook
  (guarded by `window.OddHobbViralCards` check).
- `bridge/llm_bridge.py`: `/api/creative/catalog` + `/api/creative/templates`
  added to tokenless PUBLIC_GETS.

**NOT taken:** installer script itself (markers drifted; applied adapted
versions above), payload's reweighted matcher (ours kept + additive only),
payload's `render_card` replacement (merged as style branches instead).

## State now
- 27 templates in registry (7 hand-authored + 20 synthesized).
- Tests: 309 pytest green (clean env — shell key leakage causes 4 false
  failures in companion/voice tests; always run with keys unset) + 78/78 site.
- Live verified: catalog filters, style renders differ per family, public
  catalog endpoint, MCP counts (81 full / 52 public).
- Tree is UNCOMMITTED. R2 source left untouched in stallshark.

## Open / next
- Catalog entries render on the default print-safe layout until each idea
  graduates to its own manifest + layout bundle (by design).
- `figg_creative_catalog` needs the bridge token removed from llms examples
  where it still shows `?token=` (minor doc sweep).
- Consider: premise packs (`templates/premises/*.json`) cross-linked from
  catalog premise ids (currently name-matched only in matcher reasons).
