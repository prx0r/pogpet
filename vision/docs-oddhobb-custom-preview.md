# OddHobb custom preview — plan

> Status: PLAN ONLY (2026-10-01). Focus now = **accurate stills that match the mesh**.
> Prompt UI / animation / AR come after the image pipeline is trusted.

## What we’re building

One Meshy mesh per pet. Customisation is **assets + prompts on top**, not a new
mesh every time:

| Layer | What | How it ships |
|---|---|---|
| Body | approved pet mesh | Meshy once (gated spend) |
| **Coat** | fur colour (cream / golden / chocolate / black / fawn / grey / hex) | Blender grade for previews; multi-colour print quoted live |
| **Hat** | xmas / santa / beanie / none | Blender prop on the skull (free preview) |
| **Text** | e.g. name or “lucky” on the hat band | texture/decal on the prop |
| **Hardware** | printed loop only | same plastic as the pet — **never metal** |

### Combos (customer picks)

- body only
- body + coat
- body + hat
- body + coat + hat
- optional: hat text (`lucky`, pet name, date)

Example prompt on the site: *“chocolate coat, santa hat, say lucky”*.

## Branding

- OddHobb = **white + warm brown** (current site + cream fur reads correctly)
- Gallery / store pages stay on that palette; product shots on pure white
- Draggable mesh is the hero — same GLB the stills are rendered from

## Keychain vs ornament (locked)

| | Ornament | Keychain |
|---|---|---|
| Design | same body + printed loop | **same design, smaller** (60–80 mm) |
| Hole | 5.0 mm | 4.0 mm |
| Hardware | printed plastic hook (tree prop in renders) | **printed plastic ring/link — no metal** |
| Pack | ribbon + box | backing card only |

POD rule: **we never ship metal.** Loop + ring print in the pet colour family.

## Store experience (later phases)

1. **Stills** (now) — accurate renders, downloadable, gallery per line
2. **Coat + hat assets** — prop library + coat presets in the render script
3. **Prompt box** — site text → coat/hat/text args → preview stills (Blender, 0 credits)
4. **Drag mesh** — already live on `/products.html`
5. **Animation** — Meshy/UniMate stage (gated) e.g. stand-up clip under the viewer
6. **Greeting cards + AR** — same mesh, portal card, AR message (existing figg pipeline)

## Accurate-image rules (non-negotiable)

1. **Never recolour the body mesh in a way that isn’t in the GLB** — no painted
   discs on the back (loop stays fur-textured).
2. Hardware props are **separate objects**, clearly “printed plastic”, tinted to
   the coat when `--hardware printed`.
3. **Santa hat must sit on the measured skull** before any santa still is
   published. Until then: no santa frames in the store gallery.
4. Coat previews are **material grades** on the existing texture — fine for
   marketing; production colour is a live farm quote.
5. QC every set: white bg, no black wedges, product matches mesh silhouette.

## Build order (do not skip ahead)

```
1. Accurate ornament + keychain stills (coat cream, printed hardware)  ← now
2. Coat library stills (golden / chocolate / …) on the key frames
3. Santa hat geometry locked to skull → then publish hat stills
4. Hat text decal (“lucky”)
5. Prompt → preview stills on the site
6. Animation + AR cards
```

## Open

- [ ] Production 80 mm STL + live quotes (Makr3D / Printie / 3D Vikings)
- [ ] Brick mesh (75 mm) when ready
- [ ] Shopify `model-viewer` metafield once store token is live
- [ ] Santa hat placement (blocked until mesh-accurate)
- [ ] Coat multi-colour purge quotes (Makr3D AMS)

## Existing assets we can apply (searched 2026-10-02)

Stored under `figgsite/data/assets/hats/`. **No Meshy credits** — import +
fit only.

| Asset | Path | Licence | Notes |
|---|---|---|---|
| **OpenGameArt Santa Hat** | `hats/oga-santa/santa_hat.fbx` + `.png` | **CC0** | 170 verts, ~242×335×230 mm in FBX units — **scale to skull** (~40–50 mm brim on 80 mm pet). Simple, print-friendly. |
| **Khodrin Christmas Hat** | `hats/khodrin-christmas/christmas_hat.fbx` + Albedo/Normal | Author: edit + **redistribute** (free asset pack) | Higher detail, PBR textures 2K. Fit in Blender before any store still. |
| Khodrin Christmas Scarf | khodrin.com/christmas-scarf | same author | Future coat/accessory layer |
| KayKit Holiday Bits | itch.io (CC0 pack) | **CC0** commercial | Props/presents — not hats; optional scene dressing later |
| BlendSwap CC0 hats | blendswap.com/blend/23602, 22372, wad247 fur hat | **CC0** | Download needs BlendSwap account — queue if OGA/Khodrin not enough |
| Meshy community “Santa Hat 67” | meshy.ai model page | **CC0** preview | Only if we already have Meshy access; still no credits without asking |

**Rule:** only ship store stills after the hat **sits on the measured skull**
(same rule as before). Procedural cone props stay as fallback when no asset
file is loaded (`--prop santa`).

### Fit pipeline (once asset is good)

```
import FBX → measure bbox → scale so brim ≈ head width × 1.05
→ seat on skull (z = mesh zmax − embed, y = head mid)
→ optional tilt for floop → material = coat-aware red/white or custom
→ render mini set (hero / front / back) → QC against mesh silhouette
```

`render_product.py --hat-asset data/assets/hats/oga-santa/santa_hat.fbx`
implements the import+scale+seat path; procedural hat remains if the file is
missing.
