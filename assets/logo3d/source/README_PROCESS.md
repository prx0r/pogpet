# OddHobb 3D Logo — Process Notes (2026-10-10)

Everything here was made from code. There is no Meshy or AI mesh: the geometry comes straight from the canonical SVG.

## 0. Environment
- Linux aarch64 sandbox. Blender 4.3.2 is installed through apt (blender.org builds are x86 only):
  `sudo apt-get update && sudo apt-get install -y blender python3-numpy ffmpeg`
- Python: `pip install manifold3d shapely trimesh numpy pillow`
- Renderer: Cycles CPU. There's no OpenImageDenoise in this build, so `use_denoising=False`, and noise is handled with samples plus the separate shadow pass.
- Colour management: AgX view transform with the "Medium High Contrast" look (Punchy for the orange variant).

## 1. Source artwork
- `oddhobb-canonical-perfect-black.svg`: viewBox 0 0 1000 1000. The knot is cubic-Bézier `<path>`s with a 26-unit stroke, and the ring is a circle centred at (500,500) with r=350.
- Each Bézier is sampled at 40 points per segment, buffered by stroke/2 = 13 units (round caps and joins, resolution 24), and unioned with shapely.
- The strokes are clipped to the circle (r=350). The ring is annulus r 337–363.
- Scale: **0.05 mm per SVG unit**, so the ring OD is **36.3 mm**. Y is flipped (SVG y runs down) and the shape is centred at the origin.
- Polygons are simplified at 0.4 units, then extruded with manifold3d, so every mesh is watertight.

## 2. Geometry (coin.py, variants.py)
### A. Raised coin: coin.py → out/body.obj, glyph_top.obj, glyph_bot.obj, oddhobb_coin.stl/.glb
| Param | Value |
|---|---|
| Coin diameter | 40.0 mm (R=20) |
| Thickness | 3.0 mm |
| Rim width | 1.0 mm |
| Field recess (both faces) | 0.35 mm |
| Glyph relief | 0.35 mm (+0.02 overlap), top and bottom; bottom rotated 180° about X, and the mark is mirror-symmetric |
| Reeded edge | 160 grooves, Ø0.32 mm cylinders, height T−0.5 |
| Cylinder segments | 512 |

### B. Engraved coin: variants.py → out/var/eng_body.obj, eng_fill.obj
Same body, field recess 0.25 mm. Glyph **engraved 0.7 mm** into both faces, plus a 0.06 mm "enamel" fill object at the engraving floor (rendered as gloss black).

### C. Chunky mark: variants.py → out/var/chunky.obj, oddhobb_chunky.stl
The canonical glyph and ring only, with no coin. **36.3 × 36.3 × 10.0 mm**, extruded 10 mm and centred on Z. Watertight.
At render time (and baked into the GLB): Blender bevel modifier, width 0.45, 3 segments, angle limit 50°, harden normals, smooth by angle 40°.

## 3. Materials (Principled BSDF, vrender.py)
| Variant | Base colour (linear) | Metallic | Roughness | Extra |
|---|---|---|---|---|
| gold coin body / glyph | (1.0,0.66,0.24) / (1.0,0.76,0.36) | 1 | 0.30 / 0.06 | anisotropic 0.4 on body |
| silver engraved | (0.92,0.92,0.93) + fill (0.01,0.01,0.012) | 1 / 0 | 0.18 / 0.35 | fill coat 1.0 |
| chunky orange | (0.8,0.1,0.0) | 0 | 0.35 | coat 1.0 (roughness 0.03) |
| chunky chrome | (0.95,0.95,0.96) | 1 | 0.05 | |
| chunky gold | (1.0,0.66,0.24) | 1 | 0.12 | |
| chunky black (gloss) | (0.02,0.02,0.022) | 0 | 0.32 | coat 1.0 |
| **chunky matte (web pick)** | **(0.06,0.06,0.065)** | **1** | **0.40** | matte anodised look |
| original coin (spin.py) | body (0.018,0.018,0.02) / glyph (0.92,0.92,0.93) | 1 | 0.32 / 0.12 | aniso 0.4 |

## 4. Scene / camera / lights
- Object pose: pivot rotated 76–80° about X (stands the disc up), then spun about Z by −28° (coins) or −34° (chunky).
- Camera: orthographic at (0,−150,0) looking +Y, ortho scale 48 (coins) or 50 (chunky).
- World: a gradient ramp (dark 0.12, mid 0.35 at 0.55, white 1.0), strength 1.6, or 2.2 for matte. It's only seen in reflections; the film is transparent.
- Standard lights (area, location / size / W): (−60,−80,70)/60/90k, (10,−220,40)/140/260k, (80,−60,20)/40/40k, (0,60,90)/70/50k, (0,−90,−60)/80/15k.
- **Matte lights (soft, even):** (−90,−120,90)/120/420k, (110,−90,30)/120/200k, (0,40,130)/140/160k, (0,−150,−60)/160/60k.
- Stills: 1400 px (variants) or 1800 px (matte), 96 samples, adaptive threshold 0.03, 6 bounces.

## 5. Stills post (comp.py, inline PIL)
- Crop to the alpha bbox, fit the longest side to 1500 px (shadowed variants) or 1640 px (matte, no shadow), and centre on a 2000×2000 canvas.
- Drop shadow (variants only): alpha × 0.55, offset (+40,+70), Gaussian blur 45, under the object.
- Backgrounds: white #FFFFFF, brand orange #EE7410 (charcoal #18181A for the orange variant), and transparent.
- Matte web files have no shadow: oddhobb-matte-black-{white,transparent}.png, plus transparent .webp at q90 (~190 KB).

## 6. Spin loader (vrender.py `<variant> 600 spin 36`)
- 36 frames, a **180° turn** (the mark is mirror-symmetric, so half a turn loops perfectly), 600×600, 40 samples, transparent.
- ffmpeg at 24 fps (1.5 s):
  - WebM with alpha: `-c:v libvpx-vp9 -pix_fmt yuva420p -b:v 0 -crf 30 -auto-alt-ref 0`
  - MP4 on white: `color=white` overlay, `libx264 -crf 20 -movflags +faststart`
  - GIF: overlay on white, scale 320, palettegen/paletteuse, `-loop 0`

## 7. Emerge loader (emerge.py + emcomp.py)
- Front-on perspective camera at (0,−260,0), 135 mm lens, 480×480. The chunky mark's extrusion axis points at the camera, with the back face on a shadow-catcher plane at y=0.
- Hierarchy: spinE (pivot at the object centre) → popE (back plane, scales along Y) → mesh.
- **Timeline, 132 frames at 30 fps = 4.4 s, seamless:**
  | Frames | Action | Easing |
  |---|---|---|
  | 0–12 | blank white (object hidden) | — |
  | 12–36 | extrude depth 0.002 → 1 | ease-out-back (c1=1.7) overshoot |
  | 22–44 | white (0.95) → matte black (0.06), metallic 0 → 1, roughness 0.5 → 0.4 | smoothstep |
  | 36–50 | lift 16 mm toward the camera (clears the plane for the spin) | smoothstep |
  | 50–96 | 360° spin about vertical, plus a 12° tilt (sine bump) | smoothstep |
  | 96–110 | lower back to the plane | smoothstep |
  | 104–124 | black → white | smoothstep |
  | 110–128 | retract depth → 0 | smoothstep |
  | 128–132 | blank white | — |
- Two passes per frame: `obj` (40 samples, plane hidden, world white at strength 0.35) and `sh` (8 samples, object invisible to the camera but still casting shadow onto the catcher).
- Composite (emcomp.py): shadow alpha blurred (res/60 px) × 0.45 × min(1, depth/0.35), coloured #141418, on white, with the object over it. This removes the noisy catcher and the ghost at depth 0.
- Encode at 30 fps: MP4 `libx264 -crf 18 yuv420p +faststart`, WebM `libvpx-vp9 -crf 32`, GIF at fps 20 and 320 px with palette.

## 8. Commands (from logo3d/)
```
python3 coin.py                         # raised coin meshes
python3 variants.py                     # engraved coin + chunky meshes
blender -b --python spin.py -- still    # original black/silver coin still
blender -b --python spin.py -- spin 32  # original coin spin frames
blender -b --python vrender.py -- <gold|silver_engraved|chunky_orange|chunky_chrome|chunky_gold|chunky_black|chunky_matte> 1400
blender -b --python vrender.py -- chunky_matte 600 spin 36
blender -b --python vrender.py -- chunky_matte 600 glb   # → out/var/oddhobb-chunky_matte.glb
python3 comp.py                         # shadowed white/brand/transparent 2000px
blender -b --python emerge.py -- 480 all 40 obj
blender -b --python emerge.py -- 480 all 8 sh
python3 emcomp.py 480                   # → out/var/emerge_480_final/
```
Never run two Blender jobs at once. Full renders take about 1–2 min per still, and about 12 min for the 132-frame emerge loop at 480 px.

## 9. Gotchas
- The GLB is in mm exported as metres (36 m across). model-viewer auto-frames it; in three.js, scale by 0.001.
- Safari won't play VP9-alpha WebM, so use the MP4 fallback on white.
- `bpy` OBJ import uses forward_axis='Y', up_axis='Z'.
- The shadow catcher alone was too dark and noisy at low samples, hence the separate shadow pass plus blur.
