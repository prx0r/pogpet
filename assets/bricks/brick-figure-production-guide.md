# Brick Figure: Photo to Full-Colour Print (Agent Reference)

Proven run on 9 Oct 2026: two 45 mm figures (pyjama, dress), printed in JLC3DP WJP full-colour resin. Scripts live in `bricks/` and `bricks/jlc/`.

## 0. Goal and quality bar
- The result should look like a classic yellow brick minifig, and you should be able to tell "that's my outfit" at a glance. It follows the photo in spirit, not as literal texture noise.
- Skin is always classic yellow, never photo skin tone. Clothing changes texture only. Only hair, bows and hats change geometry.
- One watertight, textured file per figure, about 45 mm tall, with the feet flat.

## 1. Inputs
- The source photo, one person, full body (e.g. `files/uploads/*.webp`).
- The generated textured GLB from the OddHobb brick-figure style (`brick-figure-<uuid>.glb`). It comes out already in mm, about 25.8 × 45.3 × 12.6 mm, Y-up, as 5 mesh parts: head/hair, torso, arms, legs.
- Pick the best generation per person. Reject any with a torso fused into the legs, stretched legs or stilts, long sleeves on a sleeveless outfit, or a broken back. Final bases: `…1bf3.glb` = pyjama, `…5504.glb` = dress.

## 2. Template rules (lock these for every figure)
- Proportions follow a real minifig: head about 0.57, torso about 0.58, hips plus legs about 0.62 of a unit height. The feet share one baseline.
- Skin is yellow. Target RGB (250,211,33) in `final.py`; spec #F2CD37. Head, hands and any bare arms or legs are skin.
- Material is metallic 0.1 and roughness 0.4 on every part, with one texture atlas.

## 3. Texture clean-up (`bricks/final.py`)
- Load the GLB with `glb.py` and edit the texture by face region. Each region is a predicate on face centre C and normal n, rasterised to a UV mask (`mask_for`) and dilated 4 px into uncovered texels (`dil`) so seams don't bleed.
- Three ops:
  - `recolour`: set a target colour, keeping shading with luminance ratio clipped to 0.9–1.05.
  - `clean`: replace outlier pixels more than 45 RGB away from the target.
  - `blue2`: recolour only the bluish pixels.
- Pyjama: arms y −0.03…0.19 to yellow; the torso back to clean SHIRT (160,192,239); the hip band to PINK (244,182,200); the back of the legs to blue (150,182,230).
- Dress: bare arms to yellow; the skirt to DRESS (150,183,226); bare legs to yellow; boots to TAN (203,172,131) on the outer, recess and interior faces; the interior/recess dress areas to DRESS.
- Run `python3 final.py p d`, which writes `prod/brick-figure-{pyjama,dress}-final.glb`.
- QA: render the four views (`bl_render.py`, Blender 4.3 Cycles CPU, denoise off) and compare them to the photo. No photo-tone skin, no dark smudges, sleeves match the photo.

## 4. Weld and export (`bricks/weld_export.py`)
- In Blender, remove doubles at 1e-4 and recalculate normals. Export `prod/*-production.glb` (textured master) and an `.stl`.
- The production GLB is the master. Every downstream file is made from it.

## 5. Choosing the print process (the key decision)
- **FDM / AMS (Printie, Bambu, 3D Vikings): don't use for faces.** At 45 mm the eyes, lashes and mouth are 0.3–1 mm, about one 0.4 mm filament line. Painted 3MFs at 7 colours and 0.12 mm layers came out jagged and blobby. AMS Lite also caps at 4 colours. Use FDM only for single-colour or faceless versions.
- **Use full-colour inkjet resin (WJP / PolyJet-type).** It prints the GLB texture per voxel: real face, outfit, gradients, no colour limit.
- Supplier: **JLC3DP WJP Full Color Resin.** It takes a ZIP of OBJ+MTL+PNG, 3MF, or PLY, but not GLB. FullColor3DPrint (US) takes GLB directly and is the alternative.
- Pros don't print faces in filament. LEGO pad-prints, and customisers UV-print or use waterslide decals.

## 6. Convert to the JLC package
1. Use trimesh to load the production GLB, concatenate the parts, and export `brick-figure-<n>.obj`, which writes `material.mtl` and `material_0.png`.
2. Downscale the texture from 16384×4096 to **8192×2048 RGB** (LANCZOS). The 14–16 MB zips failed upload, while 6–7 MB works. 8k is still far beyond what the print can resolve.
3. Slim the OBJ: drop `vn` lines, use 4 dp for `v` and 5 dp for `vt`, and make faces `v/vt`.
4. **MTL fix:** trimesh writes `Kd 0.4`, so set `Kd 1.0 1.0 1.0` and `Ka 1.0 1.0 1.0`, otherwise the texture may print dark. `map_Kd material_0.png` must stay.
5. Zip the three files flat, at the zip root: `cd dir && zip -9 ../name.zip *`.

## 7. Geometry repair, making it watertight while keeping UVs (`bricks/jlc/repair2.py` + fan fill)
- Check the topology on a **position-welded** copy: unique on vertices rounded to 5 dp. Texture seams duplicate vertices, so unwelded checks lie.
- Found: stray flap triangles whose three edges were all bad (3-face edges plus 1-face edges). Pyjama had 3 open and 7 non-manifold edges; dress had 5 and 10. **Fix: delete any face whose every edge is non-2-manifold.**
- If a 4-face pinch edge remains (pyjama had one), delete one face pair at it, then close the 4-edge boundary loop with a **centroid fan**. Add one vertex at the loop centroid with the mean UV of the loop, and orient each fan triangle (b, a, c) against the boundary edge a→b.
- trimesh `fill_holes` re-created the same bad edge, so don't use it there. Iteratively deleting and refilling made things worse.
- Pass bar: 0 open edges, 0 non-manifold edges, `is_watertight` and `is_winding_consistent` true. Size is unchanged, the texture is still 8192×2048, and the MTL is linked.
- Each figure is 7 closed shells (head, hair, torso, arms, hands, legs). They all overlap, so nothing floats, and WJP fuses them on print. No boolean union is needed for JLC.
- Deliverables: `bricks/jlc/brick-figure-{pyjama,dress}-fullcolour-repaired.zip`.

## 8. Final visual QA
- `bricks/jlc/views.py` renders front, ¾, side and back of the exact OBJ being uploaded. `face.py` renders a face close-up with ortho scale 0.36×H, centred 0.17×H below the top.
- Check that the faces are crisp, eyes have no halos, the bare-skin areas are yellow, and the outfit reads clearly from the front and back.

## 9. Ordering on JLC3DP (the user orders manually)
1. Go to `jlc3dp.com/3d-printing-quote` and upload each **zip as is**. Don't unzip it, or the colour is lost.
2. The thumbnail is always grey geometry. What confirms the texture loaded is the **"Multicolor | MTL"** tag.
3. Settings: WJP(Resin), Full Color Resin (not Tough), Multicolor, qty 1, Surface Finish **Oil Spraying**. That's a clear gloss coat and is included in the price.
4. The size should read about 4.51 × 2.63 × 1.25 cm. JLC reads the OBJ numbers as mm and shows them in cm, and there's no unit prompt.
5. Tick the "Thin walls detected" printing-risk box. It shows at every size (45 to 100 mm).
6. Packaging is a JLC-logo box or a Blank Box only, with no custom logo or message. Choose Blank and add your own card.
7. A JLC reviewer checks full-colour files and confirms before production. The build is 5 days.

## 10. Costs (quoted 9 Oct 2026, qty 1, US)
| Height | Per figure | Volume |
|---|---|---|
| 45 mm | $6.91 | 5.3 cm³ |
| 60 mm | $11.00 | 12.4 cm³ |
| 80 mm | $24.19 | 29.4 cm³ |
| 100 mm | $47.10 | 57.4 cm³ |
- Price goes with resin volume, about $0.82/cm³ above the floor, so it grows with the cube of the height. No quantity discount.
- Shipping: Global Standard about $5.86–7.38 (8–13 business days), UPS Express Saver DDP about $26.55 (2–4 days). The quote page is country-level only, with no ZIP field.
- Chosen: 45 mm, both for $19.87 delivered (standard). 60 mm is the upgrade if faces need to be bigger.

## 11. Gotchas
- The sandbox is aarch64: install Blender through apt (`apt-get install blender`, 4.3.2), not blender.org. Use Cycles CPU, since EEVEE needs libEGL. Set `use_denoising=False` (no OIDN), and give `render.filepath` an absolute path.
- pip and apt packages vanish between sessions. Reinstall trimesh, numpy, scipy, rtree, networkx and pillow, plus blender.
- Browser uploads over about 10 MB can fail with a transport error, so keep the zips around 6–7 MB.
- JLC WJP guidelines: minimum wall 1 mm (small) to 1.5 mm (50 mm scale); colour lines ≥ 0.4 mm; no hollow parts; no interlocking or assembled parts.

## Superseded lane (FDM painted 3MF)
- `colour_xfer.py` → `run_paint.py` (paint_map.py palette and regions) → `despeckle.py 0.8` → `design_pass.py` → `make_bambu_colour.py`. This produced 7-colour Bambu 3MFs at 0.12 mm layers. Keep it only for FDM/AMS suppliers, and expect weak faces at 45 mm.
