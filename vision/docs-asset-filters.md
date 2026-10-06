# Asset filters — products as frontends over tagged assets

> Status: SPEC (2026-10-05). Generalizes the card gallery's baby auto-assign
> (`backend/cards.py` gallery: latest 4 photos × 3 templates) into a real
> system: every upload gets tagged at ingest, every product/card owns a JSON
> filter declaring what it wants, a matcher assigns assets automatically.

## Vision

Each product and card is a frontend. Each owns a JSON spec of what it is
looking for from the uploaded assets: a face count and framing, a mesh or a
flat image, a name to inscribe, a motif zone. Each spec is a filter over the
asset bank. When a photo is ingested we tag it once, and all cards and
products can then automatically assign themselves.

## Part 1 — asset tags at ingest

### Where

The choke point is `POST /api/photos` → `intake.accept()` → `db.insert_photo`.
Person autosort (`POST /api/photos/autosort`) already fetches every photo to
local tmp — the face pass runs there and on single upload, same code path.

### What gets tagged per photo

| Tag | Type | How |
|---|---|---|
| `faces` | count + boxes `[{x,y,w,h,confidence}]` (0–1 frame coords) | face pass at ingest; 0 faces is valid (typography, textures) |
| `faces_count` | int, indexed | derived, for fast filtering |
| `orientation` | `portrait \| landscape \| square` | from processed w/h |
| `print_dpi` | `{a6, a5, a57, a4}` DPI at each card size | from pixels; drives the soft-print warning as data |
| `has_cutout` | bool + `cutout_id` | set when a cutout is authored |
| `has_mesh` | bool + `mesh_id` | join `meshes.photo_id`, already exists |
| `person` | string (existing column) | autosort cluster, unchanged |
| `occasion_fit` | `[birthday \| christmas \| …]` | from subject profile + EXIF date proximity, advisory only |
| `safety` | `ok \| review` | flat-frame + size gates already in intake; face pass never rejects, only tags |

Rules: tagging never blocks upload. A photo with no faces is a first-class
asset — typography cards and texture motifs want exactly that. All boxes
stored 0–1 relative so crops survive re-renders.

### Schema

New side table (photos untouched except an index):

```sql
CREATE TABLE photo_tags (
  photo_id TEXT PRIMARY KEY REFERENCES photos(id),
  faces_count INT NOT NULL DEFAULT 0,
  faces JSON NOT NULL DEFAULT '[]',
  orientation TEXT NOT NULL DEFAULT 'square',
  print_dpi JSON NOT NULL DEFAULT '{}',
  has_cutout INT NOT NULL DEFAULT 0,
  updated_at REAL NOT NULL
);
CREATE INDEX idx_photo_tags_faces ON photo_tags(faces_count);
```

Backfill: one pass over existing photos through the same function; missing
tags mean "untagged", and filters treat untagged as wildcard, never as fail.

## Part 2 — per-product filter JSON

Each product and card template owns a filter. Lives in `backend/config.py`
next to the existing `personalization` blocks (which become the
`channels` section), served at `GET /api/products/studio` items and
`GET /api/cards/templates` untouched in shape — filter added as a new key.

```jsonc
{
  "id": "portrait",
  "kind": "card",
  "channels": ["face_png", "name_text"],
  // --- the filter: what this product is looking for ---
  "wants": {
    "faces": {"min": 1, "max": 1},
    "orientation": ["portrait", "square"],
    "asset": ["photo", "cutout"],
    "needs_mesh": false,
    "min_dpi": {"5x7": 200},
    "text": {"zone": "headline", "max_chars": 160, "needs_name": true}
  }
}
```

Field reference:

| Field | Meaning | Examples |
|---|---|---|
| `faces.min/max` | faces wanted in the asset | portrait 1–1, family 1–5, typography 0–0, ornament mesh n/a |
| `orientation` | acceptable framings | cards prefer portrait/square; game fascia any |
| `asset` | `photo` (flat) / `cutout` / `mesh` (3D) | jibbit takes photo or mini-mesh; keychain mesh only |
| `needs_mesh` | hard-require a sculpted mesh | full-mesh lines true; cards false |
| `min_dpi` | per-size print floor | cards enforce; charms advisory |
| `text` | inscription contract | zone + max_chars mirrors existing factory zones; `needs_name` pulls subject profile |

Seed values: card templates take their min–max from `card_scenes.py`
(portrait 1–1, family 1–5, christmas 1–5, typography 0–0); factory lines
take method/zone/max_chars from their `personalization` blocks
(emboss → text-only, relief → text+motif, face_swap → mesh);
`golf_marker` keeps its `pet_mesh` override as `asset: [photo, mesh]`.

## Part 3 — the matcher

Pure function, no I/O: `score(asset_tags, product_filter) -> (0–1, reasons[])`.

- Hard fails (score 0): faces outside min–max, needs_mesh with no mesh,
  DPI below floor at the chosen size, orientation mismatch.
- Soft scoring: face centering vs focus, cutout present when preferred,
  person name available when needs_name, occasion_fit overlap.
- Untagged assets score 0.5 with reason `untagged` — visible, never silent.

Callers:

- `GET /api/cards/gallery` — replace the hardcoded 4×3 cross with
  match-every-template-against-every-tagged-photo, top-N per template.
  Same response shape plus `score` and `reasons`.
- Studio/products shelf — each line shows its best asset and why
  ("this is your Milo" carries the match reason).
- Ingest response — `POST /api/photos` returns `assigned_to: [...]`
  so the uploader watches the shelf populate.

## Part 4 — card/product pack zip (new)

No zip exists in cards today. New endpoint `GET /api/cards/pack?design_id=…`
(or per-order) producing `oddhobb-<id>-pack.zip`:

- `front.png`, `inside.png`, `print.pdf` (existing exporters),
- `assignment.json` (which asset matched which filter + scores),
- `README.txt` (print spec: size, bleed, DPI verdict).

Same pattern later extends to factory lines (STL + assignment.json).

## Part 5 — API surface

| Endpoint | Change |
|---|---|
| `POST /api/photos` | response gains `tags` + `assigned_to` |
| `GET /api/photos/tags/:id` (new) | inspect one asset's tags |
| `GET /api/cards/templates` | each template gains `wants` |
| `GET /api/products/studio` items | each item gains `wants` + `best_asset {id, score, reasons}` |
| `GET /api/cards/gallery` | generalized matcher, gains `score`/`reasons` |
| `GET /api/cards/pack` (new) | the zip |

## Rollout

1. `photo_tags` table + face pass + backfill; gallery unchanged.
2. `wants` on the 7 card templates; gallery switches to the matcher.
3. `wants` on the 5 full-mesh lines, then factory emboss/relief lines.
4. Pack zip for cards, then factory lines.
5. Ingest `assigned_to` in the upload response.

## Test plan

- Unit: matcher truth table (0-face photo vs typography/portrait/family;
  mesh-required line vs meshed/unmeshed photo; DPI floor at each size).
- Contract: every template and line has a valid `wants` (min ≤ max,
  known zones, known channels).
- Live: upload a 1-face photo → gallery assigns portrait/breaking/christmas,
  not family-overflow; upload a 0-face texture → typography only.
- Backfill: pre-tag photos return `untagged` reason, still assignable.
- Pack: zip contains all four files, PDF still prints to spec.
