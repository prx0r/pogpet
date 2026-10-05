# assets/logo — CANONICAL OddHobb mark. This is the source of truth.

If you need the logo for anything — site, print, Blender, loaders — it comes
from this folder. Nowhere else. `data/logo1/` holds working copies and
superseded explorations; this folder holds the canon.

| File | Use |
|---|---|
| `oddhobb-canonical.svg` | THE mark. Static placements, favicon source, social avatar. |
| `oddhobb-canonical-draw.svg` | Same geometry, paths reversed bottom-to-top. Draw-on animation ONLY. |
| `oddhobb-etch-loader.svg` | Animated loader variant (self-contained SMIL/CSS). Boot curtain. |
| `oddhobb-canonical-preview.png` | 1400px reference render. Never ship; compare against it. |

Rules:

1. Blender (`scripts/factory/mark.py`, `glyph_spin.py`) reads
   `assets/logo/oddhobb-canonical.svg` by default. Meshes derive from here,
   so logo drift is impossible unless someone edits this folder.
2. Never re-author the mark in a design tool and save beside it. Propose
   changes by replacing these files with review, never by adding `v5-final`.
3. Colors: strokes are `#000` here; product tints happen at render time.
