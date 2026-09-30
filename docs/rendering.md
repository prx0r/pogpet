# Product rendering — spec

> Reproducible recipe for turning an amended mesh (loop, ballast, S-hook prop)
> into review/listing images. Code: `scripts/render_product.py`. Everything is
> local Blender/CPU — **0 credits, always** (AGENTS.md money rule #5).

## Run it

```bash
blender --background --python scripts/render_product.py -- \
    --in data/uploads/chibi-figure-hook.glb --out /tmp/renders --size 900
# listing pass: --size 2000
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
| S-hook | Bezier curve, 0.5 mm bevel (=1 mm wire), steel BSDF, **prop only** | matches real tree-hook wire; never exported with the product |

## Verifying what you rendered (do this — eyes lie here)

The image-viewing tool in this environment **repeatedly served wrong/old files**
mid-session. Protocol:

1. Tag every candidate: draw two coloured bars on one edge (e.g. 24 px + 14 px).
2. **Give each file a *different* tag** (colours or side) — identical tags made a
   mis-serve undetectable.
3. Read the tagged copy: if the bars aren't what you painted → you were served
   another file; rename with a fresh unique tag and retry.
4. Cross-check with numbers: `blown`/`black` percentages from the QC line.

## Known issues / open

- **Hard shadow wedge** on the detail shot's lower-left (uncropped) — worked
  around by cropping `(250,30)-(900,640)`; root cause (normals vs UV-atlas
  sampling) not yet proven. QC `black` catches it (1.2% after crop, ~23% before).
- **Fur colour is paler than the source mesh** — AgX desaturation; `--sat`
  (default 1.35) is the knob, tune per product against `dog-mesh-original.png`.
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
