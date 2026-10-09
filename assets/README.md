# assets/ (tracked binaries)

`data/` is gitignored, so files the code expects under `data/productimg/prod/` were never in git. They live here now.

Restore them with:

    mkdir -p data/productimg/prod && cp assets/prod/* data/productimg/prod/

| path | what |
|---|---|
| assets/prod/brick-figure.glb | brick figure #1 (pyjama, production GLB) -> config STUDIO_BRICK_GLB |
| assets/prod/brick-figure-2.glb | brick figure #2 (dress, production GLB) -> STUDIO_BRICK2_GLB |
| assets/prod/brick-hero.png / brick-hero-2.png | 3/4 renders of those -> STUDIO_BRICK_PORTRAIT / STUDIO_BRICK2_PORTRAIT |
| assets/bricks/prod/ | all brick production files: GLB/STL, PLA STL/3MF, Bambu multi-colour 3MF, view renders, colour previews |
| assets/bricks/jlc/ | JLC3DP full-colour (WJP) upload zips; use `*-fullcolour-repaired.zip` |
| assets/bricks/scripts/ | brick pipeline scripts (final.py, repair, colour paint, QA) |
| assets/pegs/ | cribbage peg masters regenerated to the HANDOVER spec: peg_classic, peg_ball, peg_topper_mount (3.1 mm shaft, watertight). `Cribbage_peg_5.stl` was not available to Hark and is NOT included. |
| assets/uploads/ | raw source uploads (Meshy brick-figure GLB/STLs, reference photos, logo SVG) |
| assets/logo3d/ | OddHobb 3D coin (STL/GLB/OBJ), Blender spin loop (WebM alpha/MP4/GIF + frames zip), 9 SVG/CSS loaders + demo index.html |
