# Product rendering — spec

> Reproducible recipe for turning an amended mesh (loop, ballast, S-hook prop)
> into review/listing images. Code: `scripts/render_product.py`. Everything is
> local Blender/CPU — **0 credits, always** (AGENTS.md money rule #5).

## LOCKED sizes (see `docs/balance.md` for the full table)

| Line | Production body | Loop | Renders as |
|---|---|---|---|
| Pet core / desk | **80 mm** | none | `mkt-front/back/left/right/hero` |
| Pet ornament | **80 mm** | 5.0 mm hole, tree S-hook prop | `mkt-hang*`, `mkt-hook-*` |
| **Pet keychain** | **80 mm** (small 60 mm) | **4.0 mm hole**, split-ring prop | `kc-*` |
| Brick core | **75 mm** tall | ornament 70 mm + 5.0 loop | (pending brick mesh) |

Custom-request previews: `--prop santa` (etc.) adds a free Blender prop on the
approved mesh. New Meshy bodies = gated spend, ask the user first.

## Store gallery + 3D viewer (live)

- **`https://oddhobb.com/products.html`** — per-line galleries (ornament,
  keychain, custom) + Google `<model-viewer>` to drag the Meshy mesh.
- GLB is public at **`/img/chibi-figure-hook.glb`** (mirrored from
  `data/uploads/`, also on R2 `stallshark/marketing/`). Marketing PNGs are
  the same `/img/` files the gallery uses.
- Pattern adopted from `shopify-app/ODDHOBB.md` (model-viewer + poster; skip
  heavy WebGL engines). Shopify metafield path is next once the store token
  is live.

## Run it

```bash
blender --background --python scripts/render_product.py -- \
    --in data/uploads/chibi-figure-hook.glb --out /tmp/renders --size 900
# listing pass: --size 2000
# keychain marketing: --shots keychain --variant keychain
```

Outputs `detail.png` (ring + hook close-up), `hero.png` (whole product) and
prints QC: **targets `blown < 2%`, `black < 3%`**.

## The recipe (why each line is there)

| Setting | Value | Reason |
|---|---|---|
| Engine | **Cycles, CPU, 48 samples, denoise** | Headless EEVEE is flaky here (`EGL_BAD_MATCH`) — identical scenes render textured one run and flat white the next |
| Texture | **extracted from the GLB, material rebuilt** | glTF material import intermittently arrives flat white; extracting the embedded 4K JPEG + a UVMap/ImageTexture/HSV node chain is deterministic |
| View transform | **AgX + look `AgX - Punchy`** | `Standard` clips cream fur to pure white (~20% blown pixels); AgX mathematically cannot clip but desaturates ("anemic") — Punchy + a **saturation node (1.35)** in the material is the combination that passes QC |
| Lights | key 90 W / fill 65 / rim 55 / bounce 45, area, `visible_camera=False` | AgX handles the level fine; the bounce light lifts the near flank |
| World | `(0.085, 0.09, 0.10)` | keeps shadow side off zero |
| Normals | `normals_make_consistent` after import | voxel-remesh leftovers can face inward → pitch-black wedge |
| Camera | `view_layer.update()` after every transform | **without it the render uses a stale matrix** — framing silently wrong |
| S-hook | Bezier curve, steel BSDF, **prop only** | tree-hook wire; never exported with the product |
| Split ring | torus prop, **keychain variant only** | 4.0 mm hole clears a standard split ring; ring is packaging, not the print |
| Santa / custom props | `--prop santa` etc. | free Blender addons for request previews |

## Verifying what you rendered (do this — eyes lie here)

The image-viewing tool in this environment **repeatedly served wrong/old files**
mid-session. Protocol:

1. Tag every candidate: draw two coloured bars on one edge (e.g. 24 px + 14 px).
2. **Give each file a *different* tag** (colours or side) — identical tags made a
   mis-serve undetectable.
3. Read the tagged copy: if the bars aren't what you painted → you were served
   another file; rename with a fresh unique tag and retry.
4. Cross-check with numbers: `blown`/`black` percentages from the QC line.

## Marketing set (white bg) — 2026-10-01 pass

```bash
blender --background --python scripts/render_product.py -- \
    --in data/uploads/chibi-figure-hook.glb \
    --out data/marketing --size 1600 --bg white --shots marketing --sat 1.45
# keychain set:
blender --background --python scripts/render_product.py -- \
    --in data/uploads/chibi-figure-hook.glb \
    --out data/marketing --size 1600 --bg white --shots keychain --variant keychain --sat 1.45
```

Outputs: `mkt-front/back/left/right`, `mkt-hero`, `mkt-hang` + `mkt-hang-side`
(whole product hanging from the S-hook), `mkt-hook-close` / `mkt-hook-side`.

**White background = transparent film + PIL composite**, not a bright world.
AgX maps a 0.92 grey world to ~174 — the first pass looked grey, not white.
`film_transparent=True` keeps world light on the model only; after each shot
the script pastes RGBA onto pure 255 white and applies a mild
saturation/contrast lift (1.12 / 1.04) so AgX does not leave cream fur anemic.

**Lights stay near dark-studio levels** on the white path (key 72 / fill 48 /
rim 36 / bounce 38) — boosting them to “fight grey” blew ~6% of the fur.
Two extra lights kill the hook-shot wedge: `flank` (camera-side) and `under`.

**QC on white bg** samples the centre 64% of the frame so the pure-white
composite does not drown the product in false `blown` pixels. Targets:
`blown < 8%`, `black < 2%`.

## Known issues / open

- **Hard shadow wedge** on the detail shot's lower-left (uncropped) — worked
  around by cropping `(250,30)-(900,640)`; root cause (normals vs UV-atlas
  sampling) not yet proven. QC `black` catches it (1.2% after crop, ~23% before).
  Marketing path mitigates with `flank`/`under` fills + normals on every mesh
  (>100 verts, not just the >10k body) — re-check after the white pass.
- **Fur colour is paler than the source mesh** — AgX desaturation; `--sat`
  (default 1.35) is the knob, tune per product against `dog-mesh-original.png`.
  White path also post-lifts saturation 1.12× after composite.
- **Printed loop texture is UV-stretched** after the boolean union (looks like
  flat flesh ring up close) — mesh/amend issue, not a render issue. Same
  colour as the body is correct for a single-material print; the stretch is
  the UV atlas on the union'd torus.
- **Two dark dimples flank the loop on the back** — visible in `mkt-back`.
  Likely boolean remnants / ballast-slot roof shading; inspect `add_hook.py`
  output before shipping a back-view listing image.
- **900 px = review size.** Etsy/listing pass wants `--size 2000` + composite
  into the figg-studio before-after template (`figg-studio` ships one).
- Area lights must stay `visible_camera=False` or they render as white slabs.

## R2 delivery

```bash
rclone copyto <png> r2:stallshark/<name>.png --retries 3
```

Naming in `stallshark`: `dog-mesh-original.png`, `dog-hook-hero.png`,
`dog-hook-detail.png` (+ earlier `dog-hook-full/closeup` superseded).
**R2 flakes:** first attempt returns `501 NotImplemented`, retry lands — always
pass `--retries 3` and confirm with `rclone ls` after.

## Related

- Loop/ballast sizing standards: `docs/balance.md`
- Meshy generation (credits, ledger): `docs/meshy.md`
- The amend step itself: `scripts/add_hook.py`
