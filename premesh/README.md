# premesh

Normalise an uploaded image into a well-formed input for whatever comes next —
Meshy photo-to-3D, a greeting-card subject cut-out, a thumbnail.

Standalone on purpose: **PIL + stdlib only**, no backend imports, so this
folder can be dropped into another project and driven from its own CLI.

```python
from premesh import normalize

out = normalize(photo_bytes, recipe="meshy")
out.data     # normalised PNG bytes
out.report   # QC report — .ok, .issues, .coverage
out.url      # transformation URL actually requested (reproducible)
```

```bash
python3 -m premesh photo.jpg -o out/ --recipe meshy      # saves out/photo.meshy.png
python3 -m premesh https://pog.pet/premesh/abc.jpg -r card --json
```

## Recipes (`premesh/recipes.py`)

| recipe | does | QC gate |
|---|---|---|
| `meshy` | subject cut out → trimmed → centred on 1024×1024 transparent canvas → AI upscale → PNG | ≥1024 short side, alpha present, subject covers 3–99% of frame |
| `card` | subject cut out → trimmed → up to 1600px, transparent, uncropped | alpha present, subject in frame |
| `thumb` | plain 512px WebP | size only |

A new use case is a new `Recipe` entry (options + QC thresholds), not new code.

## How it works

Cloudflare Images does every step at the edge, in one URL — no fal, no GPU on
the box:

```
https://pog.pet/cdn-cgi/image/<options>/<source-url>
```

- `segment=foreground` — BiRefNet subject isolation → transparent PNG
- `trim=border` — drop leftover background border
- `fit=contain,w=1024,h=1024` — square canvas, subject centred
- `upscale=generate` — ESRGAN, for inputs below the target (phone thumbs)
- `sharpen,metadata=none,format=png` — clean, EXIF-free, lossless

Each unique (source × options) combination is one "unique transformation":
**5,000/month free**, then $0.50/1,000. Results are edge-cached, so repeating
the same photo+recipe in a month costs nothing.

Cloudflare only pulls transformation sources **from the zone**, hence
`stage.py`: a local file is written to `data/premesh/public/` (served by the
bridge at `/premesh/`, content-addressed so the same bytes never stage twice)
and pruned after 12h. An already-public URL is used as-is.

## Wiring checklist

- [x] `PATCH /zones/{id}/settings/transformations {"value":"on"}` — zone feature enabled
- [x] `bridge/llm_bridge.py` serves `/premesh/` → `data/premesh/public/`
- [x] secrets in `.env` (gitignored): `CF_ACCOUNT_ID`, `CF_API_TOKEN`,
      `R2_S3_ENDPOINT`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`
- [ ] call `normalize()` from the upload path (`POST /api/photos`) when we
      want a normalised copy alongside the original
- [ ] `stage.prune()` on a timer or job tick so staging never accumulates

## QC failures are values, not exceptions

`normalize()` raises only when Cloudflare fails. If the *output* is wrong
(segmentation missed, subject too small), you get `out.report.ok == False`
with the reasons — that's the signal to retry with another recipe or tell the
user to re-upload a clearer photo, before any Meshy credits are spent.
