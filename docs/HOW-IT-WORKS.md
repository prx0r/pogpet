# How OddHobb works (read this first, after HANDOVER.md)

Product truth: `docs/canonical-vision.md` v1.0. Money rules: `AGENTS.md`.
This file is the operator's map: what happens when, in which module.

## The loop (one idea → one box)

1. **Upload** — photo in (`POST /api/photos`). Intake QCs, EXIF dates it.
   Faces detected (YuNet/MediaPipe), embedded (SFace), ranked. Nothing
   auto-confirms identity: `backend/faces.py`, `studio_library.py`.
2. **Organise** — autosort + roster: people, pets, families
   (`studio_subjects`, `family_members`), birthdays + interests profiles,
   birthday reminders. Names optional; face emblems primary.
3. **Label** — every photo gets shot_type (face/solo/couple/group),
   subjects, quality, print sizes (`backend/subject_assets.py`).
4. **Template** — layouts declare tag `requires`; the engine fills slots
   best-first with distinct photos (`backend/template_engine.py`).
   Carousel on site cycles the ranked shortlist; agents use the same
   endpoint. Missing slots shortfall honestly.
5. **Route** — value/speed/balanced across suppliers + GB/US matrix +
   order-by countdowns (`backend/delivery.py`). Prodigi live; Gelato /
   Printify staged (dashboard IDs); Slant direct for 3D.
6. **Compile** — kit ideas run every lane (`backend/project_check.py`);
   gift recipes resolve components + live products with the postage rule
   (`backend/components.py`); feasibility gates publishing
   (`backend/feasibility.py`); run-states track needed→ordered→
   received→verified. Rights gate blocks sale until sources clear.
7. **Make** — parametric CAD (build123d venv) for exact geometry,
   renderers (wrap/card/booklet/trio) for print assets, fal.ai rescue +
   matting behind approval + ledger.
8. **Sell** — Etsy packs (`etsy/samples/`), Shopify drafts, Prodigi /
   Printify / Gelato fulfilment, Shenzhen box assembly (staged RFQs).

## Surfaces (kept in parity)

- Site: `site/index.html` served by `bridge/llm_bridge.py` → Flask :8798.
- REST: `backend/server.py` (~100 routes). MCP: `backend/mcp_server.py`
  (full tier; public six only with `PUBLIC_MCP=1`).
- ChatGPT: `site/openapi.json` action spec (36 paths) + `chatgpt-plugin/`.
- Rule: new endpoint → MCP tool → openapi path → test. Enforced by
  `tests/test_labels.py::AgentSurfacesTest` pattern + `test_site.py`.

## Data + money rules (short version)

- Every row carries an owner; writes need key-match or owner_sig; anon
  only on demo paths. `data/` is runtime (never commit); `assets/` +
  `etsy/samples/` are tracked masters; R2 holds private blobs.
- Meshy/fal ask-first, ledgers in `data/*.jsonl`. Orders never charge
  from our API (pending_checkout / Shopify draft). `purchasable` false
  until rights + manufacturing proven. No metal hardware in product
  photos. Sibling repos read-only; writes only in figgsite.
