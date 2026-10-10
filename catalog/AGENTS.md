# AGENTS.md: OddHobb product packs

You are designing, changing or shipping an OddHobb product. **A product exists only as a pack in `catalog/packs/<SKU>/`.** A product is "finished" only when `tools/validate_pack.py` says so. Your opinion, a nice render, or a passing preflight on its own is not the gate.

## The one rule
```
python3 catalog/tools/validate_pack.py catalog/packs/<SKU> --preflight
```
- Exit 0 and `level` LISTABLE or PROVEN: you may list it (Etsy, oddhobb.com) and send it to print.
- Anything else: it is not finished. Fix the FAIL lines. Do not list it, do not print it for a customer, do not advertise it.
- Never hand-edit `gates.json`, `listing/renders.json` or `print/preflight.json`. Tools write them.
- After any change in any pack, re-run the validator, then `python3 catalog/tools/build_graph.py` (rewrites `graph.json` + `STATUS.md`).

## Levels (config.json → levels)
| Level | Gates | What it unlocks |
|---|---|---|
| DRAFT | anything failing G01-G06 | nothing; design work only |
| PRINT_READY | G01-G06 | upload to the supplier for a **quote** or a **test print** for us |
| LISTABLE | G01-G13 | Etsy + oddhobb.com listing, customer orders, print on order |
| PROVEN | G01-G14 | paid ads, bundles, wholesale |

## Pack layout (copy `_template/` via `tools/new_pack.py`)
```
packs/<SKU>/
  product.json        the canonical record (schema/pack.schema.json, schema_version 2)
  print/<SKU>-<process>.zip   THE file sent to the supplier. Nothing else is ever uploaded.
  print/preflight.json        written by --preflight, stamped with the print file sha256
  print/prep_report.json      optional (Blender print3d report, feeds thin-wall + intersection checks)
  listing/*.png               Etsy/store images, >= 5, >= 2000 px short side, PNG
  listing/renders.json        provenance: images were rendered from the exact print file (tools/register_renders.py)
  listing/listing.txt         optional human copy of the listing
  preview/                    site personalisation plates + corner JSON, three.js assets
  evidence/                   slot measurements, DFM sign-offs, supplier quote PDFs/screenshots
  samples/                    photos of the physical sample we received
  gates.json                  validator output (do not edit)
```
SKU = `FAMILY-VARIANT[-...]`, upper case, matches the folder name.

## Gates (all deterministic, see tools/validate_pack.py)
| Gate | Passes when |
|---|---|
| G01 structure + schema | product.json parses, validates against schema/pack.schema.json, sku = folder, print/ + listing/ exist |
| G02 supplier + process | supplier is in suppliers.json and offers the process; process is in config.json |
| G03 print file pinned | `manufacture.print_file.path` exists inside `print/`, its sha256 equals the json, format matches the process (wjp = OBJ+MTL+PNG flat zip, mjf/sla/slm = mesh zip, cnc = STEP zip) |
| G04 preflight | pipeline/preflight.py run on that exact sha: no FAIL, and every WARN has a written reason in `manufacture.preflight.acknowledged` (key = check name). Processes without an automated preflight (cnc, fdm) need `evidence/dfm.json` {print_sha256, verdict: PASS} |
| G05 geometry agrees | `geometry.dims_mm` within 0.5 mm and `volume_cm3` within 2 % of what preflight measured |
| G06 manufacture spec | material, finish, colour, lead times set; **no hand-finish steps on a dropship product** |
| G07 real cost | print and shipping cost have basis `quote` or `invoice`, a ref, and an ISO date <= 90 days old. Estimates never pass |
| G08 margin | for every channel: (price − fees − cost) / price >= 30 % (fees + FX in config.json) |
| G09 slots | personalised products offer >= 1 slot; every **offered** slot is `validated: true` with an evidence file; text slots have max_chars, cap_mm, min_cap_mm >= process minimum, charset, and a fit policy that ends in a hard error (never truncate); colour slots have a palette containing the default. Unmeasured slots must be `offered: false` |
| G10 listing copy | title <= 140 chars; exactly 13 unique tags, each <= 20 chars; materials; description >= 200 chars; >= 3 spec rows; processing time; channels |
| G11 listing images | >= 5 declared PNGs, >= 2000 px, a hero, alt text on each, all in renders.json with matching sha256, and renders.json pinned to the current print sha |
| G12 audience | >= 3 suits, >= 2 occasions, >= 1 buyer relationship, >= 1 not_for |
| G13 graph | every parent / related SKU resolves to a pack or a template id in config.json |
| G14 sample | `samples[]` has a received physical sample with a photo and verdict PASS |

## Workflow for a new product
1. `python3 catalog/tools/new_pack.py <SKU> "<name>" <family> personalised|fixed <supplier> <process>`
2. Build the geometry from the product line's official template; keep its locked interfaces (record them in `geometry.locked_features`).
3. Produce the print file with the pipeline (`pipeline/run_product.sh` for meshes: prep → repair → pack). Put it in `print/`, write its sha256 into product.json.
4. `validate_pack.py --preflight`. Fix or acknowledge (in writing) every WARN. Copy measured dims/volume into `geometry`.
5. Render the listing images **from the zip in print/** (`pipeline/bl_listing.py`), save PNGs into listing/, declare them in `listing.images`, then `tools/register_renders.py`.
6. Measure every slot on the real geometry (free area, surface, min cap height for the process). Save the measurement to `evidence/`, then set `validated: true`. Only then `offered: true`.
7. Get a real supplier quote (print + shipping, region named). Record amount, ref (quote/order no.), date; save the screenshot in evidence/.
8. Price it so G08 passes. Fill audience + listing copy.
9. Validate → build_graph → it appears in STATUS.md at its level.

## Changing a product
Any change to the print file changes its sha256, which **automatically invalidates** G03/G04/G05/G11 until you re-run preflight and re-render + re-register the images. That is deliberate: listing photos can never drift from what we print.

## Hard don'ts
- Don't upload anything to a supplier that isn't `print/<SKU>-<process>.zip` of a PRINT_READY pack.
- Don't list a product below LISTABLE. Don't run ads below PROVEN.
- Don't mark a slot validated without an evidence file, or a cost as quote without a ref.
- Don't use listing images rendered from source/design meshes; render the print file.
- No hand-finish (paint fill, gluing, inserts) on dropship products. Either fold it into the print (WJP colour, separate printed part) or switch fulfilment to via-oddhobb.
- Don't spend money (quotes are free; orders need the human's go).
