# OddHobb product pipeline v1

One flow for every printed product: **source mesh → print pack → PREFLIGHT GATE → listing renders → product spec JSON**.

```
./run_product.sh <source.glb> <name> <height_mm> [faces=150000] [process=wjp]
python3 validate.py products/*.json
```

## Stages
| # | Script | What it does | Output |
|---|---|---|---|
| 1 | `bl_prep.py` (Blender) | scale to height in mm, feet on z=0, centred; merge by distance; drop debris shells; decimate (UV-safe); 3D-Print-Toolbox make-manifold; thin-wall (0.8 mm), intersect and overhang checks | `model.obj`, `prep_report.json` |
| 2 | `repair_uv.py` | weld for topology, drop flaps/debris, centroid-fan fill every hole with UVs kept → watertight | `model.obj` |
| 3 | `pack_jlc.py` | OBJ (v/vt only, 4/5 dp) + MTL (Kd/Ka 1.0) + RGB PNG, flat zip, auto-shrinks texture to stay uploadable | `<name>-<h>-jlc.zip` |
| 4 | `preflight.py` | **final gate before JLC.** Re-reads the zip exactly as JLC will. Exit 1 on any FAIL | `preflight.json` |
| 5 | `bl_listing.py` | renders the unzipped print file (not the source) on white: hero, front, side, back, detail (`DETAIL_TARGET=fx,fy,fz`, `DETAIL_ZOOM`) | `listing/*.png` 1600 px |
| 6 | `products/<SKU>.json` | spec per `schema/product.schema.json`: geometry, manufacture, preflight, cost, **slots**, **audience**, listing, assets, graph, ext | validated by `validate.py` |

## Preflight rules (WJP full colour; edit `RULES` in preflight.py)
FAIL: zip > 12 MB, files not at zip root, no/extra OBJ, MTL Kd ≠ 1.0, texture missing, no UVs, dims off target or unit-wrong (metres), open edges, not watertight, debris shells.
WARN: zip 8–12 MB, non-manifold < 20, thin faces < 0.8 mm, self-intersections, winding.
INFO: resin volume and a cost estimate (~$0.82/cm³, $6.91 floor) — the JLC quote is final.

## Rules of thumb
- Meshy GLBs come in **metres** (0.12 = 120 mm). Unscaled, JLC would read 0.12 mm.
- Meshy exports 1.5 M faces at 150 MB; 150 k faces is plenty at 80 mm and keeps the zip near 8 MB.
- Price grows with the cube of height (solid resin). Hollowing is the next big saving to test with JLC.
- Renders always come from the zip that preflight passed, so the listing shows what gets printed.
- Never two Blender jobs at once. A 5-view set at 1600/48 takes ~12 min on this sandbox.

## Product graph
Each spec's `graph` links SKUs (`variant_of`, `pairs_with`, `upsell_to`, `composes`). `parents` points at the base template whose locked features a variant must keep. New capability goes in `ext` first, then gets promoted into the schema with a version bump.
