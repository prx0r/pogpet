# Props workbench — golf club + glove (PAUSED)

> Status: **PAUSED 2026-10-03** — do not block Etsy P0 on this.
> Script: `scripts/add_golf_props.py` · Source mesh: `data/uploads/brick-figure-01a0feb8-7c26-7796-be37-b6fddb09d772.glb`
> Outputs so far: `data/uploads/brick-man-golf.glb`, `data/marketing/golf/golf-{hero,front,side}.png`
> Credits: **0** (pure Blender). Resume when Etsy listings are live.

## Goal

Give the brick man a **golf club + glove** as controlled preview props
(same doctrine as santa hat: separate objects, never recolour the body,
registry IDs later if we productise).

## What we learned (do not rediscover)

1. **glTF import frame is not the GLB accessor frame.**
   - Accessors: Y-up, body ~1.4 units tall, hands at x=±0.45, y≈−0.23.
   - Blender import: **Z-up** + root empty `Node_11` at **scale ≈ 29.8**.
   - World verts: head high-Z, feet low-Z (figure height ≈ 47 units), arms at ±X.
   - `Right Arm` lands at **negative X** in this import (node names still match).

2. **Never `transform_apply` the body** to "flatten" it — it scrambles axes
   and bound_box stops matching vertex data. Parent props to `Node_11`
   instead so they inherit the same scale.

3. **`bound_box` lies** after glTF import. Measure from `ob.data.vertices`
   transformed by `matrix_world`.

4. **Hand placement:** outer-X + lower 35% of the arm volume + mid-Y.
   Hip height fallback: `fmn.z + 0.42 * height` (Z-up).

5. **Club geometry:** grip at hand, clubhead on the floor
   (`ground_z = fmn.z + 0.01*h`), shaft from head→grip, lean ±X, forward +Y.
   Prop scale = `figure_height / 1.4` (design assumes ~1.4-unit minifig).

6. **Stills must render from the same Blender scene** — re-importing the
   exported GLB re-applies parent scales and props vanish or explode.

7. **White body on white/grey bg** can disappear; tint from a palette if the
   glTF material has no image texture (`_tint_white_body`).

8. Blender has **no PIL** — do not import PIL inside `blender --python`.
   Composite/annotate in host Python after render.

## Current stills QC

| Shot | State |
|---|---|
| hero / front / side | Body renders; club/glove placement still off (last pass hands at ±12, club short vs 47-unit figure). Need one more pass with Z-up hand measure + ground club + parent-to-Node_11. |
| brick-man-golf.glb | Written; props parented; verify in model-viewer before publishing. |

## Resume checklist

```
1. blender --background --python scripts/add_golf_props.py -- \
     --in data/uploads/brick-figure-01a0feb8-….glb \
     --out data/uploads/brick-man-golf.glb \
     --preview data/marketing/golf --size 1200 \
     --club-hand right --glove-hand left --export-props
2. Eyeball golf-hero/front/side — clubhead on floor, grip in hand, glove on other hand
3. If good: register props in config (STUDIO_HATS-style) + publish lifestyle stills
4. Exact product photos stay on the PLAIN brick mesh (no props) — Etsy rule
```

## Delegation split (when we resume)

| Track | Owner | Depends on |
|---|---|---|
| Etsy P0 listings (orn / kc / brick) | **now** | existing meshes + Blender |
| Golf props polish | later | P0 done · one visual QC pass |
| Template library (dog coats/hats × brick variants) | after P0 | registry IDs + still packs |
| Live Etsy upload / API | human + shop | listing copy + photo packs ready |

## Related

- Product stills contract: `docs/rendering.md`, `docs/oddhobb-custom-preview.md`
- Etsy formula + slots: `docs/etsy-listings.md`
- Brick line: `STUDIO_LINES.brick` status **live** · mesh `msh_a984c413e47f48a19b63`
- Santa/coat templates already rendered under `data/productimg/prod/coat-*.png` + `santa-*.png`
