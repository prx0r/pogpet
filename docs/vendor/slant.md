# Slant3D V2 API — imported 2026-10-10

Key: `SLANT3D_API_KEY` in `.env` (verified live: platforms/filaments/
components read OK). Client: `backend/slant.py` (direct; the factory MCP
hop remains as fallback). Spec: `slant3dapi.com/v2/api/openapi.json`
(32 paths, fetched to `/tmp` — re-pull anytime, don't commit it).
Sources: slant3dapi.com docs, slant3d.com/api, integration guide
(blog 2026-08-05), ShapedQR walkthrough.

## What it is (verdict: farm backend, NOT personalization)

Upload STL → estimate (free, ms) → draft order (free) → process
(CHARGED) → track + webhooks. Order items: PRINT (our meshes) +
COMPONENT (their hardware) + STATIONERY (one 4x6 Custom Card).
No photo/artwork/template/mockup/personalization surface anywhere —
our labels→slots→fills engine is untouched by them. Complementary:
they are the US print lane + hardware catalogue for our 3D lines.

## Key rules (their guide, enforced in client)

- Server-side only; Bearer key never in browser.
- `filamentId` mandatory on estimate + order (else 400 price error).
- Uploads: presigned PUT → confirm (mesh analysis) → file id.
- Drafts need a deliverable address; commit only from verified payment
  webhook, never optimistically. Order row first (idempotent).
- STL ≤250MB, ≤220³mm, PLA/PETG, 2–5 day US ship, bill on process.

## Useful extractions (live reads)

- `filaments` (39): default picker prefers black PLA.
- `components` (83, snapshot `data/slant_components.json`): magnets,
  keychain findings, screws, nightlights — feeds 3D hardware decisions
  (magnet ornament backs, metal-vs-printed findings).
- Account has **zero platforms** — uploads/estimates stage until one is
  enabled in the dashboard.
