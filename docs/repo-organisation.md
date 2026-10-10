# Repo organisation — vision, structure, assets, graphs (2026-10-10)

Audit base: 3,056 tracked files; backend 105 + 12 new session modules;
docs 106; tests 51 + 8 new files; data/ 3.3G ignored; 57-line uncommitted
tree (19M + 38??); main + 4 origin branches. Detail: HANDOVER.md,
docs/audit.md (09-30), docs/base-contracts.md.

## 1. Vision stack (read top-down)

1. `docs/canonical-vision.md` v1.0 — source of truth (Shenzhen-only,
   recipe-as-unit, phases, exit gates). Its own rule: strategic edits
   bump version/date/decision-log; supplier rates timestamped.
2. Supporting strategies: shenzhen-hub, kit-assembly, glimling-suppliers,
   shenzhen-rfq, oddhobb-model, personalised-projects,
   project-compiler-learnings, faces-p0, photo-labels, provider-templates,
   template-engine, fal, vendor/{gelato,printify,slant}.md.
3. Measured contracts (never contradict without evidence): jlc-*,
   supplier-catalog, cardspec, studio*, base-contracts, meshy (money).
4. Status (point-in-time, not contract): HANDOVER.md, docs/todo.md,
   docs/test-report.md, audits, fit-problems, hark-beta-tests.

## 2. Org: what lives where

- `backend/` execution layer (server, pipeline, intake, cards, studio_library,
  subjects, mockup, renderers) + money adapters (prodigi, shopify_*) +
  session-built intelligence (faces, subject_assets, template_engine,
  delivery, feasibility, project_check, components, parametric, restore)
  + staged provider clients (gelato, printify, slant) + comedy/video/voice
  + mcp_server/factory_mcp. New modules each own ONE thing (see §5).
- `site/` storefront (bridge-served, no build) + `openapi.json` (ChatGPT
  actions) + `llms.txt`. `bridge/` single-file proxy. `pi/` vendored agent.
- Surfaces contract: every REST addition ships with MCP tool + openapi
  path + test (the pattern this session followed 6 times).
- `data/` = runtime only (never committed): figg.db, uploads, meshes,
  productimg, marketing, listings, cad, ledgers (*.jsonl), tmp/.
- `assets/` = tracked production masters (bricks, pegs, logo3d, prod GLBs,
  face ONNX except 38MB SFace). `etsy/samples/` = tracked Etsy packs.
- Secrets: `.env` (41 keys, 0600, ignored) + R2/Stallshark S3 creds;
  `.env.example` is 12 keys behind (todo 2).

## 3. Asset storage map

| Class | Where | Examples | Rule |
|---|---|---|---|
| Production masters | `assets/` (tracked) | bricks/prod GLB/STL/3MF, pegs STLs, prod/*.glb, YuNet onnx | commit; SFace 38MB stays ignored + auto-fetch |
| Listing packs | `etsy/samples/` (tracked) | p01–p11 photos, listings.json, JLC zips | commit per Etsy batch |
| Runtime renders | `data/productimg/`, `data/marketing/` (ignored) | stills, wrap/card/booklet outputs | regenerate via scripts; `assets/README.md` restore map |
| Uploads/meshes/DB | `data/uploads`, `data/meshes`, `data/figg.db` (ignored) | per-owner blobs | R2-backed; sqlite backups to opencode-backup bucket |
| Public URLs | `/img/*` → `data/productimg/*` via bridge | hero PNGs, GLBs | marketing only; user content via authed artifact routes |
| External source | R2 `stallshark/` (50 buckets visible) | canonical vision, glyph packs, comics | import Bosch-style: copy in, cite source, never depend live |

Open: `etsy/assets/` absent locally (paste references it); `data/photos/`
doesn't exist (uploads/+tmp/+productimg cover the role — pick one name).

## 4. Graphs + per-account inheritance

- Chain: photos → meshes → product_bindings → orders/card_orders
  (mesh = single source of truth, db.py).
- Identity: studio_subjects → photo_subjects (confirmed + provenance) →
  photo_faces → face_embeddings; mesh_subjects; studio_selection;
  subject_profiles_v2 (relationship/birthday/interests); families →
  family_members (people AND pets, roles, image-first).
- Projects: RECIPES/GIFT_RECIPES → project_runs/run_items
  (needed→ordered→received→verified) → feasibility gate → purchasable.
- Labels → slots → fills → provider payloads (Gelato/Printify staged,
  Prodigi renderable) → quotes/compare → checkout (no card charge).
- Inheritance rule: EVERY row carries owner; reads scope by owner;
  writes need key-match or owner_sig (anon open only on demo paths);
  claim_assets moves a whole account; agent keys act as parent handle
  with per-route grants. Faces suggest, users confirm — scores never
  become identity. Birthdays/reminders owner-enforced; catalog reads open.

## 5. Module ADRs (why the 12 exist)

faces (suggest-never-confirm embeddings, zero new deps) · restore
(staged rescue dispatcher) · gelato/printify (staged fills) · slant
(direct farm client) · template_engine (one template, 3 adapters) ·
delivery (value/speed/balanced + countdowns) · feasibility (0–100 gate) ·
project_check (idea→lanes verdict) · components (registry + run-states) ·
parametric (build123d adapter) · subjects families · server endpoints
(candidates/compare/fill/reminders/recipe/gift/projects).

## 6. Ten todos

1. [commit] Review 57-line tree → batch commits (owner go).
2. [secrets] Sync .env.example + rotate chat-pasted creds.
3. [assets] Restore runbook + resolve etsy/assets + data/photos naming.
4. [data] Lifecycle: tmp/marketing retention, ledger rotation, sqlite backups.
5. [docs] Vision index table (SPEC vs status) + dedupe pass.
6. [backend] Surface-parity check in CI (endpoint→tool→openapi).
7. [backend] Track-order endpoint (last mapped API gap).
8. [mfg] Elecrow RFQ send + 3/3 pilot parcels (Phase-1 exit).
9. [mfg] Mixam live quote client (real delivery dates for countdowns).
10. [release] Phase-0 exit checklist live (3 types, paid checkout, costs).
