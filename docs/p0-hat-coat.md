# P0 — fit engine: hats + harness on any mesh (REFERENCE, do not delete)

> Status: LIVE. A mesh-agnostic fit engine seats hats and builds winter
> harness garments on ANY mesh. Proven on dog (exact), brick minifig and
> badger. Products lets customers attach hat/harness on the ornament and
> buy. Last verified: 2026-10-03. 0 Meshy credits (all Blender/CPU + numpy).

## What P0 is

One engine, not one hat. Every mesh is measured ONCE into named anchors;
every part seats from those anchors; garments shrinkwrap so intersection
is impossible. New pet mesh tomorrow = run measure, attach, sell.

**Definitions (locked):**
- **Hat** = rigid accessory on the head (santa today; caps/beanies later).
- **Coat** = physical winter **jacket** (lofted torso shell + collar + hem
  + belly strap), NOT fur and NOT bare straps. Fur-colour grades still
  exist as preview stills only.

## The engine (`scripts/fit_engine.py`)

| Stage | How (foolproof bits) |
|---|---|
| `measure` | Union of all meshes (biggest-mesh lies on multi-mesh files). Head cluster top-down: pinch (neck narrows + widens back) with mass gate (10–50% head-mass rejects crowns/legs/waists), else shoulder flare, else fallback. Stations: torso slices, p70-p30 core radii (arms excluded), vertical = head-stacked-over-torso else spine-PCA. Sidecar: `data/assets/anchors/<mesh>.json` |
| `seat_hat` | Part sidecar (`hat-santa.json`: native head width) or brim-outer/1.15 fallback. Rigid transform `T(seat)·S(s)·T(-native)` — exact at any scale (naive location-then-scale silently offsets at s≠1; seen as 6 units on brick). Refine: density × solidity vote (vert count × midline fraction per slice, near-ties break higher) |
| `build_harness` | Parametric chest/belly torus rings sized from slice ellipses + gap (auto 1% height) + back strap; Blender Shrinkwrap (nearest-point + gap) onto the torso-band mesh, applied. Intersection impossible by construction |
| `compose` | Dog + parts → named product GLB, parts keep names (`hat_*`, `harness_*`) |

Research basis: industry socket/anchor convention (Roblox attachments,
Unity/Unreal sockets) + shrinkwrap garment fitting + parametric parts.
No GPU, no VLM, no Meshy.

## Generality proof (measured numbers)

| Mesh | Head seat | Head width | Torso | Hat result |
|---|---|---|---|---|
| Dog (quadruped, ears) | z≈0.158 (perched) | 0.050 | horizontal | engine reproduces the old hand seat sub-mm, then perches +17mm so ears flank outside the ring (orbitable-3D fix; stills keep the old seat) |
| Brick minifig (biped, arms out) | z≈18.0/47 | 9.8 | vertical, target=Torso mesh | brim upper-head, face clear |
| Badger (standing, leaning) | z≈0.35/0.92 | 0.21 | vertical | brim upper-head, face clear |

Dog seat reproduces the hand-tuned original exactly; brick/badger seats are
proportionally consistent (brim gap ≈15–28% of head width, faces clear).

## Parts library (`data/assets/parts/` → `/img/prod/`)

| Part | File | Notes |
|---|---|---|
| Santa hat | `hat-santa.glb` + `hat-santa.json` | 3 meshes, pre-seated dog space, sidecar pins native head width 0.05 |
| Harness ×6 | built per compose (`harness_<colour>` mats) | cream/golden/chocolate/black/fawn/grey; `scripts/recolor_harness.py` clones colours via JSON surgery (instant, no Blender) |

Retired from the mapping (files stay on disk): `coat-<c>.glb` fur bodies —
those were the old coat definition.

## Composed product matrix (all live under `/img/prod/`)

| Hat | Jacket | GLB |
|---|---|---|
| none | none | `chibi-figure-hook.glb` |
| santa | none | `dog-santa.glb` |
| none | `<c>` | `dog-jacket-<c>.glb` (6) |
| santa | `<c>` | `dog-santa-jacket-<c>.glb` (6) |

Brick keeps `brick-figure.glb` (+ engine-fitted proofs in `/tmp/opencode/`).

## Products UX (attach → buy)

1. Products tab → tile (ornament/keychain/croc) → detail card opens **and
   scrolls into view**.
2. Hat chips (None/Santa) + coat chips (= harness colour) + pattern chips.
3. Picking a chip swaps the **photo** (`/api/studio/stills`) **and the 3D
   viewer** (`#pr-d-viewer` ← `productMeshUrl(it)`).
4. Order payload carries `{line, coat, hat, pattern, mesh_id, qty}` →
   `pending_checkout` (+ optional Shopify draft with `invoice_url`).

URLs: tab click sets `/products` (pushState); `/products/<line>` opens the
tab with that line preselected; `#products` still works. Bridge serves the
SPA for `/products*`; `/products.html` (Etsy gallery) untouched.

## Customising hat / coat later (allowed, controlled)

- New hat colours: new material on the same 3 nodes, same seat.
- New hat shapes: parametric build or measured part + sidecar
  (`head_w`); engine seats it on every mesh, QC numbers confirm.
- New jacket colours: one JSON recolor, instant.
- Never: free-form mesh edits, unlisted IDs (`STUDIO_CUSTOM_POLICY`).
- Patterns (spots/stripes) are photo-grade only in P0, not on garments.

## NOT in P0

- Khodrin xmas_hat as a part (FBX on disk, never seated).
- Wide-brim hats (ring-match seating, not apex/density).
- Per-combo print files (STL/OBJ per hat+harness — `mesh_export.py` on demand).
- `coat.glb` as a jacket shell (harness covers the garment slot).

## Verify (copy-paste)

```bash
cd /home/ubuntu/figgsite
BTOK=$(cat .token)
curl -s -o /dev/null -w "products %{http_code}\n" https://oddhobb.com/products
curl -s -o /dev/null -w "hat %{http_code}\n" https://oddhobb.com/img/prod/hat-santa.glb
curl -s -o /dev/null -w "jacket %{http_code}\n" https://oddhobb.com/img/prod/dog-jacket-cream.glb
curl -s -o /dev/null -w "combo %{http_code}\n" https://oddhobb.com/img/prod/dog-santa-jacket-chocolate.glb
python3 scripts/test_site.py   # full pass, exits non-zero on FAIL
# engine self-check (no Blender edits): re-measure + compare anchors
```
