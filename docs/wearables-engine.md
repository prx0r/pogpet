# OddHobb Wearables Engine v0.1

A reusable Blender fitting/compiler layer for arbitrary customer GLBs.

## Design rule

**Do not generate the visible product from measurements.** Measurements position a high-quality authored asset or deform a low-detail proxy. The detailed master remains the thing the customer sees.

Four attachment classes are intentionally separate:

1. `headwear`: rigid/preserved crown + deformable lower fit zone.
2. `garment`: high-detail master driven by a low-detail proxy fitted to a torso convex hull.
3. `prop`: rigid GLB attached to semantic sockets (`hand_left`, `hand_right`, etc.).
4. `hardware`: printable product hardware generated from measurements (cake-topper spikes, ornament loops).

This is why one API can support dogs and brick figures without pretending one jacket topology is appropriate for both. `winter_jacket` is one logical product with `quadruped`, `brick`, and `biped` master variants.

## Install

Unzip this archive at the repository root. It only adds files.

```bash
unzip oddhobb-wearables-engine.zip -d /home/ubuntu/figgsite
cd /home/ubuntu/figgsite
python -m compileall wearables scripts/wearables_register.py
```

The package does not replace the current `scripts/fit_engine.py`. Run it in parallel until outputs pass visual QC.

## Smoke test without any external assets

Generate intentionally-simple test props:

```bash
blender --background --python scripts/wearables_seed_demo.py -- data/assets/wearables

blender --background --python scripts/wearables_cli.py -- compose \
  --in data/productimg/prod/brick-figure.glb \
  --asset-root data/assets/wearables \
  --item demo_candle@hand_right \
  --hardware cake_topper_spikes \
  --out /tmp/brick-candle-caketopper.glb
```

A JSON report is written beside the GLB.

## Import a Meshy prop once

Download/export the GLB once, then register it:

```bash
python scripts/wearables_register.py \
  --id golf_club \
  --kind prop \
  --glb ~/Downloads/golf-club.glb \
  --socket hand_right \
  --size-ratio 0.58 \
  --grip 0.5,0.5,0.92 \
  --source-name Meshy \
  --source-url 'PASTE_SOURCE_PAGE_OR_TASK'
```

Or provide a direct GLB artifact URL using `--glb-url`.

The resulting directory is:

```text
data/assets/wearables/golf_club/
  asset.json
  master.glb
```

From that point forward, fitting is local and costs zero Meshy credits.

## Compose products

```bash
# Dog wearing the premium Santa master
blender --background --python scripts/wearables_cli.py -- compose \
  --in data/uploads/chibi-figure-hook.glb \
  --item santa_hat \
  --out /tmp/dog-santa-v2.glb

# Brick holding a golf club + candle and converted to cake topper
blender --background --python scripts/wearables_cli.py -- compose \
  --in data/productimg/prod/brick-figure.glb \
  --item golf_club@hand_right \
  --item candle@hand_left \
  --hardware cake_topper_spikes \
  --out /tmp/brick-party-topper.glb

# Ornament hardware can be reused on pets or figures
blender --background --python scripts/wearables_cli.py -- compose \
  --in data/uploads/chibi-figure-hook.glb \
  --item santa_hat \
  --hardware ornament_loop \
  --out /tmp/dog-santa-ornament.glb
```

## Backend integration

Use the standard-Python runner from your Flask/job code; never import `bpy` into the server process:

```python
from wearables.runner import build_variant

result = build_variant(
    input_glb="data/productimg/prod/brick-figure.glb",
    output_glb="data/productimg/prod/brick-golf-candle.glb",
    items=["golf_club@hand_right", "candle@hand_left"],
    hardware=["cake_topper_spikes"],
    repo_root=".",
)
if result.returncode:
    raise RuntimeError(result.stderr)
```

## Target sidecars / manual overrides

Automatic sockets are cached as JSON. If a weird Meshy mesh defeats the heuristic, override only the bad socket instead of adding another special-case script:

```json
{
  "body_class": "brick",
  "sockets": {
    "hand_right": {"position": [-8.22, 1.10, 18.42], "rotation_euler_deg": [0,0,0]}
  }
}
```

Pass it with `--anchors path/to/mesh.wearables.json`.

## Headwear quality

`headwear.py` performs two transformations:

- uniform scale on the complete authored hat;
- anisotropic deformation only on the lower fitting zone, fading to zero into the crown.

Thus a dog skull can make the brim elliptical without stretching the floppy Santa cone/pompom. Set `quality.subdivision` to 1 or 2 for a clean silhouette if the imported master is moderately low-poly. Do not expect subdivision to rescue a genuinely bad source mesh; replace the master.

Recommended production master structure is a `.blend` or cleaned GLB with the intended final materials, folds and silhouette already authored.

## Garments

The garment path is deliberately different from hats:

1. select a body-class master (`quadruped`, `brick`, `biped`);
2. coarse-scale it to the measured torso;
3. create/decimate a low-detail proxy;
4. bind the detailed master to that proxy using Surface Deform;
5. fit the proxy to a torso **convex hull**, not directly into every armpit/leg gap;
6. Laplacian smooth the proxy with volume preservation;
7. bake the proxy deformation into the detailed garment.

This borrows the important architecture used by existing elastic clothing-fit tools while remaining self-contained.

## Prop manifest

```json
{
  "id": "candle",
  "kind": "prop",
  "file": "master.glb",
  "sockets": ["hand_right", "hand_left"],
  "fit": {
    "socket": "hand_right",
    "grip_normalized": [0.5, 0.5, 0.18],
    "size_ratio": 0.24,
    "size_axis": 2
  }
}
```

`grip_normalized` is measured in the prop's bounding box. `[0,0,0]` is one bbox corner; `[1,1,1]` is the opposite. It means raw Meshy GLBs do not need a skeleton or named Blender empty to become reusable.

For long props such as clubs or wands add:

```json
"aim": {
  "axis": [0, 0, -1],
  "mode": "direction",
  "direction": [0.22, 0.08, -1.0]
}
```

## Suggested library

Useful first prop IDs for brick figures:

- golf_club
- wine_bottle / beer_bottle
- candle
- bouquet
- coffee_cup
- champagne_glass
- football
- game_controller
- microphone
- guitar
- trophy
- book
- sign
- wand
- fishing_rod
- paint_brush
- chef_pan
- birthday_balloon
- christmas_present
- walking_stick

Useful hardware/product transformations:

- cake_topper_spikes
- ornament_loop
- keychain_loop
- desk_base
- fridge_magnet_socket
- nameplate

They all belong in the same manifest-driven library; there should be no `add_golf_props.py`, `add_candle.py`, `add_wand.py` explosion.

## Migration from current pogpet

1. Keep `scripts/fit_engine.py` live as v1.
2. Put a premium Santa GLB at `data/assets/wearables/santa_hat/master.glb`.
3. Generate dog + brick v2 proofs and compare to current production GLBs.
4. Register the first 5 Meshy props and tune each `grip_normalized` once.
5. Author one real quadruped jacket and one brick jacket; do not use the old 11-ring shell as the visible master.
6. When v2 passes, point generation jobs to `wearables.runner.build_variant()`.
7. Version generated GLB URLs (`?v=<content hash>`) and regenerate product stills separately; this engine does not hide stale-browser/stale-PNG problems.
