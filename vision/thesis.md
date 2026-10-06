# OddHobb Thesis — MAKR3D-first one-shot printing

**MAKR3D/Yorkshire3D can handle considerably more than simple one-piece prints**, but for OddHobb I would deliberately design toward **one-shot printing wherever possible** because it makes the economics and automation much better.

MAKR3D treats a product as either one Part or multiple Parts, and explicitly says multi-part Products cover **kits and assemblies**. It accepts STL, OBJ, STEP and 3MF, and a Bambu/Orca 3MF can preserve orientation, supports, layer height and colour assignments. [Makr3D](https://makr3d.app/help/getting-started?utm_source=chatgpt.com)

More importantly, the actual factory behind it, Yorkshire3D, explicitly offers **multi-part assemblies, snap-fit parts, post-processing, threaded inserts and adhesive assembly**. They also print PLA, PETG, TPU and ASA on their broader B2B service. [Yorkshire3D](https://www.yorkshire3d.co.uk/services/custom-manufacturing?utm_source=chatgpt.com)

So there are effectively two production levels:

| Design | Use it for OddHobb? | Why |
|---|---:|---|
| **Single-piece print** | **YES — default** | Cheapest, fastest, easiest POD automation |
| **Print-in-place moving object** | **YES** | Still one production job; great where appropriate |
| **Several parts printed together that snap together** | **YES, selectively** | Fine for higher-value products |
| **Multiple separate parts shipped as a kit** | Sometimes | MAKR3D supports multi-Part products |
| **Factory snap-fit/assembly** | Sometimes | Yorkshire3D can do this, but adds labour |
| **Glue / magnets / screws / inserts** | Only when valuable | Yorkshire3D can do it, but destroys some of our beautiful low-touch economics |

## Therefore my OddHobb design rule would be

**If it can reasonably be one part, make it one part.**

For example:

**Mahjong line reader**
One PLA print. Perfect.

**Rummy rack**
One PLA print. Perfect.

**Mexican Train hub**
One PLA print. Perfect.

**Personalised dart stand**
One PLA print. Perfect.

**Card stand**
One PLA print. Perfect.

**Cribbage peg**
One PETG print. Perfect.

**Shoelace charm**
One PLA/PETG print. Perfect.

**Keycap**
One PLA/PETG print. Perfect.

**Golf marker**
One PLA print. Perfect.

This is exactly the stuff we should prioritise.

Something like a fancy Mahjong wind indicator with a rotating wheel could be two snap-fit components. That's still reasonable.

A deck box with a magnetic lid involving **6 magnets + glue + hinges + three prints** is less attractive unless we can charge substantially more.

## MAKR3D is unusually well suited to what we're building

Their automated service currently runs **PLA + PETG**, with 40+ stocked colours. PLA has the broader colour selection. Their own guide describes PLA as rigid, precise and giving the cleanest detail, while PETG is tougher and allows some flex before breaking. [Makr3D](https://makr3d.app/materials?utm_source=chatgpt.com)

So I'd effectively give our product engine two material flags:

**`PLA`**
- Mahjong racks
- line readers
- Mexican Train stations
- domino racks
- card stands
- dice trays
- controller stands
- dart holders
- decorative pieces
- names and embossed objects

**`PETG`**
- clips
- snap interfaces
- Croc/clog connectors
- keycap stems if testing shows benefit
- cribbage peg shafts
- shoelace attachment geometry
- thin flexible parts
- objects likely to be dropped/abused

And if we encounter something that genuinely requires **TPU**, we can move that specific product from automated MAKR3D fulfilment to Yorkshire3D's custom-manufacturing service, because they explicitly stock TPU. [Yorkshire3D](https://www.yorkshire3d.co.uk/services/custom-manufacturing?utm_source=chatgpt.com)

## 3MF should become our production format

This is important.

I wouldn't merely send random STLs to MAKR3D.

Our pipeline should eventually be:

**Printables/MakerWorld/reference mesh**
→ **Blender master**
→ modify to our own production geometry
→ add personalisation
→ validate manifold/tolerances
→ **OrcaSlicer**
→ choose exact orientation/supports/colours
→ export **production.3mf**
→ MAKR3D.

MAKR3D's Faithful 3MF mode specifically preserves the things we care about: **plate layout, orientation, supports, layer height, nozzle and colour mapping**. [Makr3D](https://makr3d.app/3mf-fidelity?utm_source=chatgpt.com)

That allows us to optimise each base **once**.

For example:

`mahjong-line-reader-v1.blend`

becomes:

`mahjong-line-reader-MARGARET.3mf`

The name changes. The manufacturing recipe doesn't.

## Also: keep most things ≤4 colours

MAKR3D has AMS-equipped printers and supports multicolour. Up to four colours fits naturally into their workflow; five or more gets routed for additional review. [Makr3D](https://makr3d.app/materials?utm_source=chatgpt.com)

That's actually perfect aesthetically:

**base colour + text colour + motif colour + accent**

Example:

sage Mahjong rack
cream `MARGARET`
pink flower
dark-green leaves.

Four filaments. Finished gift. **One print. No paint. No human finishing.**

That should become our visual design constraint.

## This changes what I want from Printables research

When I search Printables/MakerWorld/Cults/etc. for OddHobb now, I'm not primarily looking for finished products to resell.

I'm hunting **proven interface geometry**:

> Does this MX stem work?
> Does this straw diameter fit?
> Does this Mahjong channel hold real tiles?
> Does this card groove fit sleeved cards?
> Does this cribbage shaft fit 1/8″ holes?
> Does this clog connector survive insertion?
> Does this rack hold 40 tiles comfortably?

Once we've got that solved, **we own the visible object**.

So each OddHobb product should eventually contain something like:

`/base/functional.blend` — NEVER personalised
`/personalisation/name.blend`
`/personalisation/motif.blend`
`/personalisation/custom_mesh.glb`
`/production/orca_profile.3mf`

Then the same `golden_retriever.glb` can compile into:

**clog charm → keycap → shoelace charm → golf marker → cribbage peg → game piece → zipper pull → card-display ornament → keychain.**

That is dramatically better than the catalogue we started with. We're effectively building a **personalised-object compiler for physical hobby ecosystems**. [Makr3D](https://makr3d.app/help/api?utm_source=chatgpt.com)

And one operational rule: **every new base gets one real MAKR3D sample before we list it.** Their own documentation recommends exactly that because the sample goes through the identical farm/QA process as customer orders. [Makr3D](https://makr3d.app/help/getting-started?utm_source=chatgpt.com)

That means I can now evaluate every Printables/MakerWorld model we find against a strict filter:

**MAKR3D-compatible → one-shot if possible → PLA/PETG → ≤4 colours → minimal supports → no post-processing → proven interface → easy Blender personalisation → cheap enough to leave strong Etsy margin.**

That's the filter I'd use from here onward.
