# Variant Engine — fan-out, re-roll, and taste (spec)

How one subject mesh becomes every product, how re-roll stays snappy, and how
saves teach the shop what good looks like. Companion to `thesis.md` (one-shot
manufacturing) and `roadmap.md` (stage plan).

## 1. Concepts

- **Subject**: one uploaded person/pet → photo, mesh, relief, silhouette, icon.
- **Adapter**: one product's recipe — functional base + personalisation zone +
  surface transform + material + supplier. Lives in `scripts/factory/adapters/`.
- **Variant**: one concrete rendering of (subject, adapter) — a seed over camera,
  arrangement, coat, pattern, hat. Has preview stills, a viewer GLB, and
  eventually a production 3MF.
- **Seed**: small int. Same seed + same subject + same adapter = same pixels.
  Variants are reproducible, shareable, and manufacturable.
- **Taste event**: keep / discard / checkout on a variant, with its params.

## 2. Cache contract (load-bearing)

Key: `(subject_hash, line, seed)` → `{viewer.glb, hero.png, angles/*, stills/*}`.

- Immutable: never overwrite a key, only write new seeds. URLs carry `?v=`.
- Storage mirrors local/R2: `owners/<owner>/variants/<line>/<seed>/`.
- A listing tile points at its *current* seed; switching seeds is a pointer
  swap, never a re-render in the request path.
- Eviction: keep pinned (checked-out) + recent seeds; background GC for the rest.

## 3. Fan-out worker (mesh activation)

Trigger: new/changed active mesh. For each of the 23 lines, in priority order:

1. Compose viewer GLB (subject asset into adapter base, content-hashed).
2. Render seed-0 hero still + 4 angles (the listing minimum).
3. Render seeds 1–2 (the instant re-roll buffer).

Priority: visible viewport first (client sends visible line ids), heroes before
angles, L0/text lines before L3 mesh lines (they compose faster). Retries with
backoff; a failed line keeps its fallback still, never a blank tile.

## 4. Viewer strategy (never 30 GLBs on a page)

Thirty live `model-viewer` instances *will* break the page: browsers cap
concurrent WebGL contexts around 8–16, each instance holds GPU memory and a
render loop, and mobile falls over first. So:

- Grid tiles are **stills only**. Always. No exceptions.
- At most **2 live viewers**: the spotlight hero + the open detail card.
- Viewers mount/unmount via IntersectionObserver; unmounted viewers keep their
  `poster` (the hero still), so the tile never flashes empty.
- `reveal="interaction"`, no auto-rotate offscreen; pause the render loop when
  the detail card closes.
- Viewer GLBs are decimated/display-grade; manufacture uses the full master.
  One shared texture per subject — no per-product texture duplicates.
- Preload the detail GLB on tile hover (link preload), so open feels instant.

## 5. Re-roll (snappy by construction)

`POST /api/products/reroll {line, seed | "next", visible: [...]}` →

1. **Instant (<300ms)**: pop the next pre-warmed seed from the line's buffer.
   The tile swaps immediately — this is a cache read, not a render.
2. **Top-up (background)**: the worker renders the *next* unseen seed into the
   buffer, so the buffer never empties no matter how often they roll.
3. **Progressive**: low-res tile still lands first, 2000px listing still follows
   in the same job. Tiles shimmer-then-sharpen; never a spinner with no image.

What a seed varies (all already parametric, zero Meshy spend): camera azimuth /
elevation, stage arrangement, coat grade, pattern, hat on/off. Angle-only
re-rolls are free-ish (same scene, new camera); coat/pattern re-rolls cost a
full frame. The buffer strategy hides both.

First paint on a brand-new mesh (cold buffer): serve seed-0 the moment it lands
(visible lines first per §3), older fallback art until then. Never blank.

## 6. Variants, taste, and prompt-customise

- **Save**: pinning a variant records (user, line, seed, full params, mesh).
  Checkout pins automatically — every order carries its seed into the 3MF job.
- **Taste profile (per user)**: kept/discarded params accumulate into weights
  (preferred coats, angles, props, text density). Re-roll samples from the
  profile-weighted distribution: your rolls drift toward your taste.
- **Global goodness (per line)**: aggregate keeps/checkouts per seed-param
  across users → default seed ordering for new visitors. The shop's front face
  is literally the best-known version of each product, updated continuously.
- **Prompt-customise**: "chocolate coat, santa hat, say lucky" → parsed to
  adapter params through the existing chat stack → rendered as a new seed with
  those params locked. The customer, not us, decides the best version: each
  product gets a variant gallery (kept rolls), and checkout is always from an
  explicit variant.

## 7. APIs

```text
POST /api/products/reroll {line, seed|"next", visible[]} -> {seed, stills, viewer_url, job_id}
GET  /api/products/variants?line=          -> kept seeds + params (mine)
POST /api/products/variants/keep {line, seed}
POST /api/products/variants/discard {line, seed}
GET  /api/agent/playbook                   -> existing funnel docs
MCP  figg_product_assets                   -> all listings + schemas (exists)
MCP  figg_product_personalise/order        -> variant-aware checkout (extend: accept seed)
```

Checkout carries `seed`; manufacture reproduces that exact variant. No seed on
an order is a bug.

## 8. Data model (new tables)

```text
variants   (id, owner, subject_id, line, seed, params_json, stills_json,
            viewer_key, pinned, created_at)
taste_events (id, owner, variant_id, kind: keep|discard|checkout, created_at)
```

Profiles and global goodness are views over these two tables, not new state.

## 9. Budgets

- Render: ~60s per 2×900px Cycles frames (CPU). Seed-0 + angles per line ≈
  3–4 min; full 23-line cold fan-out ≈ 60–90 min background. Never on the
  request path.
- Storage: hero + 4 angles + viewer GLB per seed; GC unpinned seeds older than
  N days. R2 mirrors local (existing `rclone r2:` remote).
- Meshy spend: zero. Re-roll never touches Meshy — only the original subject
  build costs credits, once.

## 10. Build order

1. Cache contract (§2) + fan-out wiring (compose per active mesh, hashed).
2. Viewer caps + posters + IO gating (§4).
3. Reroll endpoint + buffer top-up worker (§5).
4. Variant save/keep + seed-pinned checkout (§6).
5. Taste weights + global ordering (§6).
6. Prompt-customise via chat (§6).
