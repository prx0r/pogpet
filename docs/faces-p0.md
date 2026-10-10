# Faces P0 — one subject → ideal image → every Prodigi gift

> Status: SPEC (2026-10-10). Founder call: cards perfect first, then this
> engine transfers to wrap + all Prodigi gifts. Wrapping paper is already
> the proof case: SKU `WRAP-1-50X70` verified LIVE (`backend/config.py`,
> `scripts/wrap_preview.py`, Etsy `wrapping_paper` entry).

## Endgame

Selected family member → system picks their ideal image → it appears on
wrapping paper. Same engine feeds cards. Then every Prodigi gift (calendar,
canvas, postcards, prints) renders from the same face collection. Uploaded
images in studio gain a **faces** layer: faces pre-processed per image per
subject, products display them.

## What already exists (verified 2026-10-10 — no rebuild, join up only)

| Piece | Where | State |
|---|---|---|
| Uploads + autosort + roster | upload tab, `POST /api/photos/autosort`, `POST /people/rename`, `photos.person` | live |
| Subjects graph | `studio_subjects` / `photo_subjects` (confirmed + provenance) / `mesh_subjects`, `backend/subjects.py` | live |
| Face detection (lazy) | MediaPipe at library confirm → `photo_faces` box rows, provenance `mediapipe` (`backend/studio_library.py:220-222`) | live, lazy |
| Face gate (attach) | YuNet DNN, CPU, `assets/face/face_detection_yunet_2023mar.onnx` (`backend/cards.py:336-351`) | live |
| Face chips | cropped thumbs `_{size}_{face_id}.jpg` (`backend/studio_library.py:358-364`) | live, no UI |
| Ranker | `backend/subject_assets.py:resolve` — face_quality by area, frontal by centrality, top-5 faces/bodies, `allowed_compositions` | live, uncalled by renderers |
| Photo-capable consumers | `xmas_card_preview --photo`, `PERSONAL_CARDS real_photo`, rail previews with viewer photos, `mockup.render(subject)`, `_product_src` mesh-else-photo, `wrap_preview --photo` | live |

## Gaps (the actual P0)

- **G1 — detection is lazy, not preprocess.** `backend/intake.py` has only a
  flat-colour guard (`_has_face_like_subject`); no detection at upload.
  Faces appear only when library confirm runs. P0: run detection at intake,
  store `photo_faces` immediately, backfill existing photos.
- **G2 — no faces collection UI.** Chips endpoint exists, nothing shows a
  subject's faces strip (confirm / correct / pick hero). P0: faces strip in
  upload / `my.` roster.
- **G3 — no ideal-image selector wired to products.** `resolve()` ranks, but
  no renderer calls it. P0: `subject_hero(subject_id)` → best face-crop
  asset; `--subject` on card + wrap renderers (falls back to `--photo`,
  then mesh still).
- **G4 — cards go first.** Per founder call: get all cards perfect, then
  transfer to Prodigi gifts. Wrap is built and waiting on G3.

## Cards-perfect definition (the gate before G3 spreads)

From `HANDOVER.md` freeze + `docs/cardspec.md` + `tests/test_card*.py`:

1. Founder verdict on Dad's 5 proofs (freeze gate — nothing creative till then).
2. Suites green: golden tests, triptych default, middle-title geometry,
   fullbleed attach lane + YuNet face gate, solo-first photos, relationship
   labels, bundle retry on busy queue, edit auto-renders, one canonical card
   in gallery, rail previews with viewer photos.
3. `real_photo` + face chips as first-class card sources (this is G3's input).

## Build order (do not skip ahead)

```
1. Cards perfect (verdict + fixes)                        ← now
2. G1 intake faces + backfill (0 credits, CPU only)
3. G2 faces strip UI (confirm/correct/hero)
4. G3 subject_hero + --subject in card + wrap renderers
5. Roll to Prodigi gifts: calendar (12 heroes), canvas, postcards, prints
```

## Pricing note (wrap precedent)

`GET /api/products` flips EST→LIVE when a SKU is attached — the grid then
shows trade-cost-derived price (wrap: £3.81) while retail truth lives in the
Etsy listing (£14.99) and fixed checkout. Cards already work this way
(grid vs `CARD_PRICE_CENTS`). Do not "fix" the grid; keep retail in listings.
