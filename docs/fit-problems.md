# Fit problems — exact status (2026-10-04)

What was wrong, what is fixed, what is still open. All paths repo-relative.

## 1. Sunk accessories in composed product GLBs — FIXED, live

- **Was:** santa brim ring (58 mm outer) seated at z≈0.142 mid-skull, where
  head+ears span ~90 mm wide (`skull_profile` columns in
  `data/uploads/chibi-figure-hook.glb`). Only the pompom cleared the fur.
  Jacket shell 41–59% of verts inside the torso, worst −28.6 mm.
  Root causes: `scripts/fit_engine.py` sizes jacket rings from p70–p30 core
  spread (≈true surface underestimated on quadrupeds) with a 2 mm gap, and
  the shell is deliberately never shrinkwrapped; hat scale came from
  `hat-santa.json` sidecar width (1.16×) with no ring-clearance check.
- **Fixed:** every `data/productimg/prod/dog-jacket-<c>.glb` (6),
  `dog-santa-<c>.glb` (5) + `dog-santa.glb`, `dog-santa-jacket-<c>.glb` (6),
  and the `hat-santa.glb` part were rebuilt (push-out to clearance, cap
  seating at ring z≈0.196, rest +7.3 mm, 0 poke-throughs) and verified
  PASS per file. Live on oddhobb.com under the same `/img/prod/` URLs.
- **Proof tools (live in `/home/ubuntu/aocsec`, not this repo):**
  `scripts/mesh_fit_verify.py`, `scripts/mesh_seat_perfect.py`,
  `scripts/rollout_build.py`, `scripts/mesh_proof_render.py`.

## 2. Stale pre-rendered stills — OPEN

- The ornament photo comes from `_studio_stills_for()` in
  `backend/server.py:2179`, which serves pre-rendered PNGs
  (`coat-<coat>-<hat>-*.png`, `santa-*.png`, `coat-<coat>-*.png`,
  `prod-*` fallbacks) out of `data/productimg/prod/`. Those PNGs were
  rendered from the old sunk meshes. Swapping GLBs cannot change them —
  the photo still shows the old fit until the stills are re-rendered in
  Blender from the fixed meshes.

## 3. Same-URL browser cache — MITIGATED, needs cache-busting

- `productMeshUrl()` in `site/index.html:3283` returns fixed paths for
  the new meshes, but URLs are byte-identical to before, so browsers and
  model-viewer serve the cached old copy. Customers need a hard refresh
  until a `?v=` version string is added to viewer URLs.

## 4. Source part + retired bodies — OPEN

- `data/assets/parts/hat-santa.glb` (the compose source) still carries the
  old seat; only the published copy `data/productimg/prod/hat-santa.glb`
  is fixed. Any future `scripts/compose_pet.py` run from parts resurrects
  the buried hat. The retired `coat-<c>.glb` fur bodies are still on disk.

## 5. Harness variants untouched — OPEN, low priority

- `data/productimg/prod/dog-santa-harness-<c>.glb` (6) still old builds.
  Nothing references them (`productMeshUrl()` only serves santa / jacket /
  santa-jacket), so no customer impact today.

## 6. Fit editor v1 — LIVE, hats only

- New `site/fit.html` (three.js + TransformControls, same unpkg 0.170.0
  importmap as `site/stage.html`): drag/rotate/resize the hat, Save posts
  to `POST /api/fit/placement`, reload via `GET /api/fit/placement`
  (`backend/server.py`, service-token gated, clamped, stored gitignored
  under `data/placements/`). Entry point: "Fine-tune hat fit" button in
  the products detail card (`site/index.html`).
- Limits: `PARTS` map covers santa only — `xmas_hat` has no GLB part
  (`backend/config.py` points at an unseated FBX). Jackets are baked into
  composed files, not separately posable. Saved placements do not yet
  rewrite the purchasable composed GLBs — that bake step is next.

## 7. Bridge large-file flakiness — PRE-EXISTING, unrelated

- `bridge/llm_bridge.py` static serving intermittently resets 25 MB GLB
  downloads (`ConnectionResetError` in `bridge.log`); retries succeed.
  Not caused by this work; noted for the ops pass.
