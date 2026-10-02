# Etsy priorities — P0 / P1

> Status: **P0 DONE (2026-10-02)** — 12 listing stills live at
> `https://oddhobb.com/products.html#etsy` · pack zip at
> `/img/etsy/oddhobb-etsy-listing-pack.zip`. P1 in progress (coat library).
> Mesh spend: **none for P0** — body GLB already exists. Renders are Blender/CPU only.

## P0 — Etsy listing stills from the existing dog mesh (NOW)

**Goal:** downloadable, Etsy-ready product images for the **ornament** and
**keychain** lines, built from `data/uploads/chibi-figure-hook.glb`.

| Rule | Detail |
|---|---|
| Source mesh | one approved body — no new Meshy spend |
| Size | **2000×2000 px** (Etsy listing recommendation) |
| Background | pure white (product-photo path) |
| Hardware | **printed plastic only** (ornament: tree S-hook prop; keychain: printed ring) |
| Hole | ornament 5.0 mm · keychain 4.0 mm (locked) |
| Publish | `https://oddhobb.com/products.html` → **Etsy listing pack** section + direct `/img/etsy/*` downloads |
| QC | white-path targets: product-px `blown < 25%`, `black < 2%` (see `docs/rendering.md`) |

### P0 shot list (per line)

**Ornament** (`etsy-orn-*.png`)
1. `hero` — 3/4 whole product
2. `front` — face-on
3. `side` — left profile
4. `back` — loop visible
5. `hang` — hanging from printed S-hook
6. `hook-close` — loop + hardware detail

**Keychain** (`etsy-kc-*.png`)
1. `hero` — 3/4 whole product
2. `front`
3. `back` — printed ring
4. `left`
5. `ring-close`
6. `ring-side`

### P0 also includes
- Optional **scale caption** baked lightly onto hero shots (≈80 mm) via PIL after render
- Zip pack mirrored under `data/productimg/etsy/` and served at `/img/etsy/`
- `products.html` gains an **Etsy listing pack** block with one-click downloads

## P1 — Hats, coats, site customisation, Etsy variants (AFTER P0)

Order (do not skip):

1. **Coat library stills** — free Blender material grades on the same mesh:
   `cream | golden | chocolate | black | fawn | grey` on key frames
   (`--coat`, already coded). No Meshy.
2. **Santa hat QC** — import `data/assets/hats/oga-santa/santa_hat.fbx`
   (CC0), seat on measured skull (`--hat-asset`). Mini set only.
   **Publish only if seat + silhouette pass.** Withhold otherwise
   (rule from `docs/oddhobb-custom-preview.md`).
3. **Hat text** — `--hat-text` decal preview (e.g. `lucky`) after hat seats.
4. **Site customisation** — coat/hat picker on the shop or a `/custom` panel
   that drives free local previews (still 0 Meshy credits).
5. **Etsy variant images** — coat + hat stills published as additional listing
   images / separate listings once 2–3 look right.

## Money / safety

- **Never** call Meshy for P0 or P1 stills. Body is locked; props are Blender.
- New Meshy bodies (new pets, brick line) stay **gated** — ask first, ledger on.
- R2 credentials live only in `.env` (0600, gitignored). Never print, never commit.
- Sibling repos stay read-only. All writes in `figgsite` only.

## Build command (P0)

```bash
blender --background --python scripts/render_product.py -- \
  --in data/uploads/chibi-figure-hook.glb \
  --out data/marketing --size 2000 --bg white --shots marketing --sat 1.45

blender --background --python scripts/render_product.py -- \
  --in data/uploads/chibi-figure-hook.glb \
  --out data/marketing --size 2000 --bg white --shots keychain \
  --variant keychain --sat 1.45
```

Then copy/rename into `data/productimg/etsy/` + public `/img/etsy/`, update
`site/products.html`, verify over the tunnel.
