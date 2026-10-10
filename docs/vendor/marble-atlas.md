# Marble Atlas v2 (beta) — imported 2026-10-10

Key: `MARBLE_API_KEY` (`wl_live_…`) in `.env`. rule: ASK before every
call — including free reads. Our v1 client (`backend/marble.py`) targets
the OLD `api.worldlabs.ai` API; Atlas v2 is a different surface below.
Do not mix examples across versions.
Sources: atlas-beta.worldlabs.ai/docs/{quickstart,how-to-use-atlas,
api-reference}. Full reference text: tool-output archive (35KB).

## Connection

- Base: `https://api.atlas-beta.worldlabs.ai/api/v2`, header `WLT-Api-Key`.
- Key needs: `tasks.create`, `operations.read`, `assets.create`,
  `assets.read`. Project-scoped (assets/ops/spend isolated per project).
- Health `GET /api/v2/health` is keyless (still ask-first per house rule).
- Idempotency-Key header on submits; `?wait=true` blocks to server cap;
  webhooks optional (signed, JWKS at `/.well-known/webhooks/jwks.json`).

## Task endpoints (the six)

| Task | Does | OddHobb use |
|---|---|---|
| `images2PosedRGBD` | photo(s) → camera + depth (posed RGBD) | digitize remembered places; multi-view together, sharp static pairs |
| `atlasGenerate` | posed context + target cameras → new views (+depth) | explore a room; reuse `promptUsed`, `enhancePrompt:false` |
| `atlasMasked` | inpaint across posed views (black mask = edit) | restyle/furnish rooms |
| `atlasChisel` | depth-layout + prompt → views | planned scenes from layouts |
| `atlasTextToImage` | text → starting image (+camera/depth) | seed scenes from words |
| `splats2Mesh` | Gaussian splat → GLB (+texture/vertex color) | **the bridge**: splat room → mesh → our pipeline → print |

Conventions: 1280×720 grid; camera-to-world poses, one world frame;
quaternions XYZW; keep image+camera+depth (+confidence) bundled;
overlapping views only if co-reconstructed or Atlas-generated.

## Assets / operations

- Assets: create (URL/base64/upload grants) → READY → tasks; signed read
  URLs/prefixes; soft delete; transient outputs purge in 1h.
- Operations: submit → poll `GET /operations/{id}` (`done` terminal) →
  `response`; trace/cancel/`wait`/webhookDelivery endpoints.

## Fit for us

- Rebuild-a-remembered-place = images2PosedRGBD over room photos.
- Splat room → splats2Mesh → GLB → mesh pipeline → JLC/Slant print.
- AR overlays read posed views + depth; identity lives in OUR object
  record (`backend/objects.py`), not in Marble. Glasses commoditize
  display; the room standard + event protocol is the durable layer.
