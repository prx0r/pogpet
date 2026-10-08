# Card audit — every card-related file and what it gives us

Generated 2026-10-08. Source of truth for what exists before wiring fal.ai
scene plates. Paper cards (print) vs 3D card accessories (filament) are
different systems — flagged below.

## Backend — paper card core

| File | What it gives us |
|---|---|
| `backend/cards.py` | Owner-scoped designs + immutable revisions, render jobs, cutouts, orders; `validate()` runs brand locks in the save handler (all paths); `via` transport stamp (mcp/rest/ui); `mcp_status` on responses; fixed £7.99 product truth; `POST checkout` → Shopify draft; direct-Prodigi fulfil disabled (410) |
| `backend/card_scenes.py` | Deterministic PIL renderer: `front` / `inside` (left+right spread) / `back` (locked brand) / `motion`; house fonts + `CARD_FONTS` registry (fraunces, caveat, inter, inter_bold, courier); semantic colours; `TEMPLATES` (7 live) + `FORMATS`; `CARD_DESIGN_CONTRACTS` |
| `backend/card_grammars.py` | Validators for the five rigid visual grammars (`comic_4panel`, `hero_scene`, `interview_scene`, `news_scene`, `meme_2beat`) + `validate_job` top-level schema. Spec-only today — not wired into `cards.py`/gallery |
| `backend/card_print.py` | Prodigi single-file compositor (back/front/inside in exact print-area pixels) + `preflight` against cached live spec; `PANEL_ORDER` still needs confirming against Prodigi's official template before first LIVE order |
| `backend/subject_assets.py` | `subject_asset_resolver`: face/body candidates + `allowed_compositions` (gates `full_body` — no invented bodies) |
| `backend/prodigi.py` | Live pricing, cached `print_area` per SKU, `create_order` (**spends real money** — webhook path only) |
| `backend/r2presign.py` | Presigned R2 delivery (~24h) so suppliers fetch PDFs, nothing stays public |
| `backend/shopify_fulfil.py` | Draft orders + `create_card_draft_order` (hidden SKU `ODD-CARD-5X7`, personalisation as `customAttributes`, no source photos leave us) + `verify_webhook`; API version via env (2026-07) |
| `backend/locks.py` | Read-model of locked constraints incl. card back/type/grammars; enforced in save/manifold/renderers, served by `figg_constraints` |
| `backend/mcp_server.py` (card tools) | 9 tools: `library, save, render, scene, job, cutout, reserve, checkout, templates`. `save` stamps via transport header; errors carry `http_status`; `checkout/reserve/cutout` gated (full tier only) |
| `backend/server.py` (card parts) | `/api/mcp/health` (version, tools_full/public, uptime, ports), `/api/shopify/webhooks/orders-paid` (HMAC, idempotent, panel-confirm gate), webhook `register`, gate exemption for webhooks |

## Backend — creative engine (jokes → briefs → match → render)

| File | What it gives us |
|---|---|
| `backend/creative/catalog.py` | Queryable 22-premise viral catalog (style/occasion/audience/tone/q) |
| `backend/creative/templates.py` | Template registry + validator; catalog→manifest synthesis (hand-authored wins) |
| `backend/creative/briefs.py` | Creative brief incl. buyer `request` words end to end |
| `backend/creative/matcher.py` | Deterministic template scoring + lexical request evidence |
| `backend/creative/comics.py` | Script → single-image artwork via composite2d |
| `backend/creative/performance.py` | Append-only engagement ledger; `?rank=top` catalog ordering |
| `backend/creative/review.py` / `jobs.py` / `projects.py` / `premises.py` | Revise loop, render jobs, creative projects/revisions, premise packs |
| `backend/creative/blocks.py` / `judge.py` / `operators.py` / `world_ops.py` | JokeBlock library, ComedyJudge, world/question operators (the material mine) |
| `backend/creative/providers/base.py` | `BaseAdapter` contract: capability in, artifact out; `paid` flag; free-first |
| `backend/creative/providers/router.py` | `ROUTES` capability→adapters; paid only with explicit approval + key |
| `backend/creative/providers/fal.py` | fal.ai supermarket: flux edit, wan video, kling lipsync, tripo mesh. Queue-based, BYO-or-env key, bills on success only. **No card scene-plate adapter yet — added by this change (see below)** |
| `backend/creative/providers/local.py` / `alibaba.py` / `mesh.py` | $0 paths (composite, pose bake, jaw bake, edge TTS), Qwen image/video/TTS, Meshy/Tripo mesh |
| `backend/renderers/composite2d.py` | Manifest print engine + panels + bleed QC + 8 style palettes (the 2D compositor from `cardgen.md`) |
| `backend/meme_video.py` | Panels + captions → 1080×1920 MP4 (push-in, edge-tts VO, burned captions) |
| `backend/mockup.py` / `pipeline.py` | Product mockups; mesh job pipeline (not card-specific) |

## Frontend

| File | What it gives us |
|---|---|
| `site/js/cards-studio.js` | Saved-scene editor: photo picker, crop/cutout, per-panel text + font/size/colour/align, save→preview→export→motion, **Buy £7.99 → checkout → Shopify**; deep-link `openDesign(id, rev)` |
| `site/js/card-gallery.js` | Ready-made gallery (photos × flagship templates, profile-aware headlines); previews render lazily |
| `site/js/card-renderer.js` | Legacy MythicBee canvas renderer (GameWinnerz-era). **Superseded by backend PIL renderer — do not extend** |
| `site/js/viral-card-library.js` | Viral catalog rail on the Cards tab |
| `site/js/site-router.js` | Parses `/cards/<id>/r<rev>` → `{tab, id, revision}` |
| `site/index.html` (cards tab) | Tab shell + `openDesign(id, revision)` on deep links |
| `site/openapi.json` | Documents card side doors with MCP-identical rules (designs, render, order, checkout, locks, mcp/health) |
| `site/css/cards-studio.css` / `viral-card-library.css` | Card tab styling |

## Templates / data

| File | What it gives us |
|---|---|
| `templates/catalog.json` | 22 premises × 7 styles (renders on default print-safe layout until graduated) |
| `templates/blocks/` + `templates/premises/` | 27 JokeBlocks + lore-anchored premise packs with `source_lore` (joke supply) |
| `templates/original/` | House Originals shelf (buyable, no photo needed) |
| `chatgpt-plugin/references/card-templates.json` | Template contract mirror for the ChatGPT plugin |
| `figg-studio/assets/templates/thank-you-card-a6.svg` | Legacy SVG thank-you template (pre-PIL era) |
| `scripts/factory/adapters/card_rack.json`, `card_hand_rack.json` | **Filament 3D card racks/stands — physical products, NOT paper cards** |

## Docs

| File | What it gives us |
|---|---|
| `cardgen.md` | Canonical architecture: person → brief → matcher → scene instance → renderers → artifacts → QC → checkout (the compiler, not a canvas editor) |
| `docs/cardp0.md` | Five-grammar spec verbatim + Prodigi Classic 5×7 contract (127×178mm, single flattened file, `fillPrintArea`) |
| `docs/card-style.md` | House type/colour rules for cards |
| `docs/card-review-fixes.md` | Auth/ownership hardening deltas for card tables |
| `docs/greeting-card-scenes.md` | Scene→MP4 implementation notes |
| `docs/viral-card-library.md` | Catalog import decision (merge, ours-wins) |

## Scripts / tests

| File | What it gives us |
|---|---|
| `scripts/xmas_card_preview.py` | 0-credit mesh-still + greeting-text mockups (DejaVu-era, predates house fonts) |
| `tests/test_cardp0.py` | Grammar validators, resolver, compositor/preflight, house type + canonical back |
| `tests/test_cards.py` | Full journey: save→render→order, idempotency, fixed pricing |
| `tests/test_card_checkout.py` | Guardrails: fixed price, renderer-owned rejections, via-spoof rejection, health tiers, auth passthrough, mocked save→export→checkout |
| `tests/test_card_fixes.py`, `tests/test_pi_cards.cjs` | Regression + harness checks |
| `tests/test_prodigi_fulfil.py` | Fulfil gates (410 on direct, address required, mocked happy path) |

## Gaps this audit found (now encoded)

1. No AI scene-plate path for the five grammars — `identity_image` capability resolves to composite/Qwen only. → `fal.flux_plate` (text-free plates), `fal.phota` (identity-locked hero plates), `fal.upscale` (sub-200dpi rescue).
2. No spend ledger for fal.ai (Meshy has `data/meshy_credits.jsonl`). → `data/fal_credits.jsonl` + ask-first.
3. `card_grammars.py` validators uncalled by `cards.py` save path (old 7-template system live). → documented; wiring is the deferred slice, validators stay green meanwhile.
