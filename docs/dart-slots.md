# Personalisation primitive: OddHobb Dart Stand (v1)

## Principle
A product is **fixed geometry plus typed slots**. The stand body never changes per order. Only the slot parts (text meshes) are generated, and colours are material swaps. There is no remeshing and no Meshy.

| Part | Kind | Per-order cost |
|---|---|---|
| base (plinth, board relief, 3 towers, banner) | fixed, cached GLB/OBJ | 0 |
| bands (alternate treble/double wedges) | fixed, takes the accent colour | 0 |
| name | text slot, raised 1.0 mm on the banner | ~50–250 ms (manifold3d) |
| tagline | text slot, 2.4 mm cap under the name | ~20 ms |
| arc | text slot on the rim, r 50.9 mm | ~40 ms |
| base / accent colour | material slot | 0 |

## Slot limits (personalisation_spec.json is the source of truth)
- **name**: required, 1–10 chars, A–Z 0–9 space ' & - . !, uppercased. Fraunces SemiBold, 7.4 mm cap, max width 58 mm. Long names auto-shrink, but are **rejected below a 5.0 mm cap** (MAXIMILIAN prints at 6.12 mm, which is OK).
- **tagline**: optional, 0–16 chars, Inter Bold 2.4 mm cap, max width 56 mm.
- **arc**: optional, 0–18 chars, Inter Bold 3.4 mm cap on r 50.9 mm, max chord 78 mm.
- **base colour**: midnight, white, navy, racing-green, oddhobb-orange, red.
- **accent colour**: gold, silver, white, red, green, orange, black. It applies to the bands and all text, and must contrast the base (ΔE > 30).
- The validator returns a hard error (never a silent truncate) so the agent can retry with a nickname.

## Backend primitive (suggested shape)
```json
POST /products/{sku}/personalise
{ "subject_id": "person_9fdc…",            // optional: autofill from the family profile
  "slots": { "name": "BEN", "tagline": "BULLSEYE BEN", "arc": "BEN'S OCHE" },
  "colours": { "base": "navy", "accent": "silver" } }
→ { "ok": true, "resolved": {…, "name": {"cap_mm": 7.4, "width_mm": 21.8}},
    "preview": { "base_glb": "cdn/…/dart-base.glb", "slot_glbs": {…} | null, "render_png": "…" },
    "config_hash": "sha1(slots+colours)", "price_gbp": … }
```
- `GET /products/{sku}/personalisation_schema` returns the JSON spec. Agents read the limits and fill the slots without guessing.
- The same `config_hash` is the cache key for previews and print files, so ordering the same "BEN, navy/silver" twice costs nothing.
- Print files are built only at checkout: union base + bands + slots → one watertight STL/3MF (the colours become per-part bodies for multi-colour or painted).

## Autofill from the family profile
| Slot | Profile source | Rule |
|---|---|---|
| name | `subject.nickname` → `display_name` first word | uppercase; if > limit, try the nickname, then the initials; never truncate silently |
| arc | relation to the buyer | dad → "DAD'S DARTS", grandad → "GRANDAD'S OCHE", else "{NAME}'S DARTS" |
| tagline | interests/hobbies | darts → "180 CLUB", else blank |
| base colour | `favourite_colour` / football team | nearest palette swatch by ΔE (CIELAB) |
| accent | — | highest-contrast palette swatch vs the base, with gold preferred for dark bases |

## Cheap previews when someone picks a different person
1. **Best: render in the browser (zero server cost).** Ship `dart-base.glb` + `dart-bands.glb` once (CDN cached, ~0.5 MB together). Build the name in three.js with `TextGeometry` from the same font (typeface JSON) and the same placement constants (y −29.6, z top+2.19, depth 1.0). Colours are `material.color.set()`. Switching person changes a string and re-extrudes about 2k triangles in under 16 ms.
2. **Server mesh, client render:** call `dart_gen.py` per config_hash (≤250 ms) and stream just the slot GLBs (~50–200 KB).
3. **Static thumbnails:** pre-render the base once per colourway as a PNG, then composite the name layer with the same camera matrix (2D text with a perspective warp plus a baked emboss shadow). Good for grids and email, about 10 ms.
4. **Full Cycles renders** (like these PNGs, ~1 min each) only for hero/listing shots, cached by config_hash.

## Files
- dart_gen.py: fixed parts are built once into out/_fixed; slots go to out/<name>/{name,tagline,arc}.obj + text.json
- personalisation_spec.json: slot limits, palettes, profile sources
- render.py / batch.sh: Blender Cycles product renders (`blender -b --python render.py -- <dir> <base_hex> <accent_hex> <hero|front|top|side|name> <res> <samples> <out.png>`)
