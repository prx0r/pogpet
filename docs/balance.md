# Foolproof balance & weighting system (ornaments)

> Living protocol for anything that hangs. Code: `scripts/add_hook.py`
> (`--anchor com --ballast …`). Why it exists: a printed object's real centre
> of mass never exactly matches the mesh's — infill, walls, skin and supports
> all shift it — so prediction alone gets you close and a ballast slot makes
> the last degree a 30-second fix that is then *recorded and repeatable*.

## The four layers

| Layer | What | Where |
|---|---|---|
| **1. Predict** | Compute the mesh CoM, hang the loop on its plumb column → predicted tilt 0.0° | `add_hook.py` prints `HANG TILT` |
| **2. Regularize** | Print settings that keep reality ≈ prediction: **≥4 walls, gyroid infill, no supports on the loop side, same orientation and material per SKU** | slicer profile (per SKU, documented) |
| **3. Ballast** | Enclosed steel-shot slot under the loop, filled at pause-at-height, biased left/right to trim | `--ballast`, prints `PAUSE AT HEIGHT` |
| **4. QC** | Hang test to **±3°**, record ballast per SKU, re-check every reprint | this doc |

## Why the loop goes where it goes

A hung object rotates until its centre of mass sits directly below the pivot.
Tilt from a lateral CoM error `e`:

```
θ = atan(e / h)      h = vertical distance pivot → CoM
```

For the demo dog: `h = 32.9 mm`, so **1° of visible tilt ≈ 0.58 mm of CoM error** —
tiny, which is why prediction alone can't be trusted after printing.

## The ballast slot

Cut by `add_hook.py --ballast`, directly below the loop, fully enclosed:

- **Axis runs side-to-side (X)** so fill can be biased to the side it dips toward —
  a single cavity then corrects *either* direction.
- Defaults: **Ø8 mm × 48 mm long, centre 10 mm below the back skin** → 6 mm roof.
- Capacity: 2.41 cm³ → **up to 18.8 g of steel shot** (452 g·mm of correcting
  moment = **4.5 mm of CoM trim on a 100 g print ≈ 7.8° of tilt**, at h = 32.9 mm).
- The script prints the exact slice Z: `PAUSE AT HEIGHT z=… mm (layer … at 0.2 mm)`.

## Print + QC protocol

1. **Slice** with the SKU profile (walls/infill/orientation above) and a
   *pause at layer* at the Z the script prints. Verify the slicer preview shows
   the bore open at that layer.
2. **Print**; at the pause, pour steel shot in (Ø6 mm BBs ≈ 0.9 g each; lead
   shot is denser, so fewer). Bias to one end if the tilt direction is already
   predictable from the slicer preview — otherwise leave centred.
3. **Hang test**: thread through the loop, hold free, read the tilt with a
   phone inclinometer against the wall (or print a simple ±5° paper gauge).
4. **Trim**: tilt left → add shot to the left end of the bore, one BB at a
   time, re-hang. The maths (`m = M·e/x`, e = h·tan θ, x = shot offset from
   centre) is a guide; **counting BBs until it hangs level is the protocol**.
5. **Fix**: once level within **±3°**, a drop of epoxy/CA on the shot stops it
   rattling. Never ship a rattling ornament.
6. **Record**: log `ballast_g` (and BB count) against the SKU + slicer profile
   in the product record. Same model + same profile = same ballast → the
   reprint is dialled-in with no re-testing.

## Safety / quality notes

- 4–5 walls and a solid roof over the bore (6 mm default) so shot can never
  puncture a dropped print; gyroid infill lets any loose fill settle evenly.
- Never fill above the pause layer (nozzle collision).
- Children's product: glued-in shot only, no loose fill.

## When this isn't enough

If a figure must hang level **and** stand on its base, one CoM cannot serve
both poses — that's the movable-mass problem: Prevost et al., *Balancing 3D
Models with Movable Masses* (VMV 2016, ETH) places capsules with steel balls
giving a different CoM per orientation. Engineered, published, and far beyond
an ornament — kept here as the reference if we ever need multi-pose balance.

## Loop sizing — the standards (searched 2026-09-30)

| Source | Rule |
|---|---|
| Just One More Project (hanging-hole guide) | **4–6 mm (0.15–0.25")** suits jump rings, key rings, ribbon and ornament hooks |
| mkrclub (3D-print practice) | ~4 mm hole, **2–3 mm of material around it**, ring O.D. **7–10 mm** |
| Ponoko (hole↔jump-ring pairing) | hole must clear the ring's cross-section *through the material* — a 2 mm hole in 7 mm stock won't take the ring |
| Tree S-hooks (retail specs) | wire ~**1 mm**; hooks advertise a **10 mm opening**; mini S-hooks need a loop **≥2.5 mm** ID to engage |
| Ribbon | 3 mm ribbon = upper end of the band (5–6 mm hole) |
| 3DCentral (ornament design) | load-bearing sections **≥1.5 mm** wall; hang point at the balance centre |

**Our defaults (`add_hook.py`):** `--inner 5.0` / `--wire 2.4` → O.D. 9.8 mm.
Hole clears jump rings, mini S-hooks (≥2.5), 3 mm ribbon; wire gives 2.4 mm wall
(≥1.5 structural, survives annual handling); O.D. inside the 7–10 mm practice band.
Keychain/pocket variant: `--inner 4.0` (same wire).
