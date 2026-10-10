Here is the comprehensive peer review I would hand to the coding agent. The current repo is much closer structurally than the screenshots make it look, but the screenshots expose a major problem: **the backend architecture has become more sophisticated than the actual creative output being shown to the customer.**

## Executive verdict

At current HEAD `936d60e`, three things are true at once:

| Area | Verdict |
|---|---|
| Product-pack/gating architecture | **Very strong direction. Keep it.** |
| Card commerce/data architecture | **Mostly solved. Stop redesigning it.** |
| Actual card art direction | **Still placeholder-grade and should be replaced.** |
| Generative transformation architecture | **Much improved, but still not truly executable end-to-end.** |
| Site shell | **Good underlying idea, currently fragmented by several competing CSS systems.** |
| Seasonal/world theming | **Easy once the shell is reduced to design tokens.** |

The critical strategic correction is:

> **Stop treating the six existing PIL birthday layouts as finished products just because the card pipeline is finished.**

Your system successfully answers:

> “Can I deterministically create, revision, preview, buy and fulfil a card?”

It does **not yet** answer:

> “Is this a card anybody would actually choose?”

Those are separate gates.

---

# 1. Why the cards look this bad despite all the AI infrastructure

The screenshots make complete sense after reading `backend/card_scenes.py`.

The cards on the shelf are mostly **not using generative AI at all**.

They are being created by code that literally does things like:

```python
d.rectangle(...)
d.ellipse(...)
_scatter(...)
_sticker(...)
_frames(...)
text_block(...)
```

The available visual asset library is currently:

```text
balloon-border
birthday-cake
colored-balloons
pink-bow
frame
```

There are only a handful of generic CC0 PNG assets under:

```text
assets/card-art/
```

Your first screenshot is therefore exactly what the code asks for:

> stock balloon border + uploaded photograph + Fraunces text.

The dots card is:

> procedurally scattered circles + photograph + black rectangle + text.

The gold card is:

> dark background + procedurally scattered dots + circular photograph + text.

This is not a model-quality failure.

**The models aren't being asked.**

---

# 2. There is supposed to be generated card artwork — but it doesn't exist

This part is particularly revealing.

`card_scenes.py` contains:

```python
TEMPLATE_BACKDROPS = {
    "birthday_arch": "birthday party balloon sky...",
    "birthday_dots": "pastel polka confetti field...",
    "birthday_news": "dark navy broadcast studio glow...",
    "birthday_gold": "dark champagne celebration bokeh...",
    "birthday_wall": "warm cream party garland..."
}
```

And the comment literally says:

> generative backdrops: beauty is generated ONCE per template

That's the correct idea.

But the renderer looks for:

```text
assets/card-art/backdrops/<template>.png
```

and **there is no `backdrops/` collection in the repo**.

So every one of those falls back to the primitive flat design.

That is one major reason we've spent hours architecting generation while the UI still looks like 2004 clipart.

---

# 3. You also deliberately disabled the one generative element that does exist

The compiler can call:

```python
_attempt_title_art(...)
```

and generate the decorative middle title.

But the website shelf was intentionally compiled with:

```text
title_art = false
```

while stabilising P0.

That was sensible for commerce testing.

It is no longer sensible to treat those outputs as the final visual catalogue.

Right now the shelf is showing the **safe fallback** and we're judging it as though it were the intended product.

---

# 4. The best card architecture in the repo is barely being used

There is already a much more interesting template:

```text
birthday_fullbleed
```

And its art direction says:

> rich editorial gouache, vintage poster crossed with a New Yorker cover

It supports reference imagery and full-bleed generated art.

This is significantly closer to what you actually want.

But currently:

- it isn't in `BIRTHDAY_TEMPLATES`;
- it isn't one of the six published birthday recipes;
- the main shelf compiler isn't creating its art;
- it requires attached art;
- the good generation path is essentially dormant.

So the repo already contains the beginnings of the answer while the customer is being shown the fallback templates.

---

# 5. The other great ideas are sitting disconnected in `templates/catalog.json`

This is where the frustrating part becomes obvious.

You already have genuinely good concepts such as:

```text
Late-night couch interview
Family roast stage
Mock documentary confessional
Post-match sideline interview
Trophy lift
Pundit desk analysis
Breaking news
Holiday press conference
Christmas morning chaos
Domestic action hero
Family biopic
```

Those are **vastly more compelling personalized card concepts** than:

> photo in oval + dots.

We correctly removed the old “Pick a format / Use this idea” browser from the buying journey.

But we threw away the wrong thing.

The mistake wasn't those concepts.

The mistake was showing **concept metadata instead of finished cards**.

The right progression is:

```text
internal concept
    ↓
generative scene recipe
    ↓
tested template
    ↓
finished personalized card
    ↓
customer shelf
```

Not:

```text
internal concept
    ↓
customer chooses an idea
```

And not:

```text
discard concepts entirely
    ↓
use balloons
```

---

# 6. The card compiler itself is still flattening all the creative diversity

Another important issue:

Every recipe currently gets this logic:

```python
base = OCCASION_TITLES["birthday"]
title = f"{base}, {label}!"
```

So your six completely different card recipes all become:

> Happy Birthday, Dad!

The screenshot proves it.

The compiler also currently gives all of them:

```text
title_vibe = playful_balloons
```

regardless of whether the card is:

- news;
- gold;
- sports;
- editorial;
- four-photo.

That defeats the point of recipes.

The recipe should own a **creative contract**, not merely a renderer name.

For example:

```json
{
  "id": "birthday_press_conference_v1",

  "copy": {
    "headline_strategy": "mock_sports_press",
    "inside_strategy": "dry_affectionate"
  },

  "scene": {
    "transform_id": "sports_press_subject_v1"
  },

  "typography": {
    "style": "broadcast"
  }
}
```

Then:

```text
Dad likes golf
+
birthday
+
press-conference recipe

→ "LOCAL MAN REFUSES TO RETIRE FROM THE BACK NINE"
```

rather than:

> Happy Birthday, Dad!

on six different backgrounds.

---

# 7. The correct next generation of Cards

Do **not** delete the deterministic renderer.

Change what it deterministically composes.

The winning architecture is:

```text
AI creates the visual ingredient
        ↓
OddHobb validates it
        ↓
OddHobb adds typography/layout/bleed deterministically
        ↓
exact print master
```

For a scene card:

```text
Chris reference images
        ↓
identity-preserving scene transformation
        ↓
Chris at a late-night interview desk
        ↓
validated full-bleed plate
        ↓
OddHobb overlays headline + inside message
        ↓
Front / Inside / Back
```

For a conventional photo card:

```text
Chris photos
        ↓
deterministic 4-photo grid
        ↓
generated title art
        ↓
Front / Inside / Back
```

Both models can coexist.

---

# 8. The AI should make scenes, not text

I would alter `birthday_fullbleed` immediately.

Its existing prompt asks the model to generate:

> Large hand-lettered cream title

Don't.

You have a deterministic typography engine.

Image models still occasionally produce:
- wrong wording;
- duplicate letters;
- inconsistent spelling;
- slight text corruption.

Instead ask the model for:

> no text, no letters, no watermark, leave clean title space.

Then render the headline yourself.

This gives you insane AI artwork **without sacrificing print determinism**.

---

# 9. Your “generate template then face-swap/person-swap” idea is exactly the next unlock

There should be a distinction between **template authoring** and **customer personalization**.

Template authoring can use expensive, chaotic AI because it happens once.

Example:

```text
"late-night birthday interview"
        ↓
generate 30 compositions using Qwen / FLUX / Higgsfield
        ↓
judge/rank
        ↓
choose one excellent composition
        ↓
lock:
camera
set
lighting
headline region
safe area
subject position
        ↓
PUBLISHED TEMPLATE
```

Then runtime personalization is constrained:

```text
published template
+
Dad references
        ↓
identity_scene_inject
        ↓
Dad appears correctly in template
        ↓
live typography
```

This is dramatically better than generating the entire card from scratch for every customer.

You get:

**AI quality + template consistency + deterministic print.**

---

# 10. Don't call this only “face swap”

Use a capability abstraction:

```text
identity_scene_inject
```

because sometimes you want:

### Simple face replacement
Useful where body / pose can stay fixed.

### Reference image editing
Qwen / FLUX can make the whole person naturally belong in the scene.

### Soul/identity model
Useful for recurring people.

### Original photograph
Useful where no generation is needed.

The recipe asks:

```text
identity_scene_inject
```

The provider router chooses the method.

That way “late night host”, “golf champion”, “Christmas press conference”, etc. don't care which model wins next month.

---

# 11. I would replace the current birthday shelf creatively, not architecturally

Keep the shelf/API/checkout.

Replace what feeds it.

The first high-quality shelf I would ship is:

| Recipe | Creative treatment |
|---|---|
| Four Memories | current deterministic 4-photo, but with generated title art |
| Late Night Birthday | generated interview scene |
| Birthday News | generated editorial/news portrait + deterministic graphics |
| Trophy Lift | generated recipient lifting absurd trophy |
| Family Biopic | generated cinematic/editorial scene |
| Birthday Portrait | tasteful generated editorial portrait |

That is a legitimate collection.

The current balloon/dots/gold stuff can remain:
- debug recipes;
- fallback if generation unavailable;
- cheap/free-credit modes.

They should not define the brand.

---

# 12. Product Packs are one of the strongest things you've built

I like this concept a lot.

The central idea is correct:

> A product isn't “done” because an agent says it's done. It is done because deterministic evidence gates pass.

That becomes incredibly powerful for autonomous agents.

Your levels:

```text
DRAFT
PRINT_READY
LISTABLE
PROVEN
```

are exactly the right abstraction.

And your current rule:

> paid ads only for PROVEN products

is especially good.

It means a marketing agent can't accidentally spend money promoting a product:
- we've never received;
- whose cost is an estimate;
- whose personalization doesn't fit;
- whose listing images aren't from the production file.

That is excellent autonomous-agent infrastructure.

---

# 13. The Product Pack needs to become the single truth for marketing too

I would extend the doctrine to:

```text
PRODUCT PACK
     ↓
manufacturing agent
store agent
Etsy agent
SEO agent
Pinterest agent
ad agent
video agent
email agent
```

All of them read the same proven object.

A marketing agent should never independently invent:

- dimensions;
- price;
- material;
- delivery time;
- product claims;
- personalization options;
- product imagery.

Those come from the pack.

The marketing agent is only creative about:

> how to present proven facts to the right audience.

That is a fantastic boundary.

---

# 14. However: Pack v2 is currently too 3D-specific

This needs correcting before packs become universal.

The schema assumes:

```text
geometry:
  dims_mm
  volume_cm3
```

And G05 assumes dimensions and volume measured from a physical model.

That works for:

- Croc charms;
- figures;
- dart stands.

It is a weird abstraction for:

- greeting cards;
- wrapping paper;
- posters;
- stickers.

Don't create an entirely separate gating system.

Split pack validation into:

```text
CORE GATES
+
DOMAIN GATES
```

For example:

```text
manufactured_mesh
flat_print
multi_panel_print
digital_media
```

A greeting card's production truth should be:

```text
trim dimensions
bleed
safe area
dpi
panel order
colour space
supplier SKU
print PDF hash
```

not:

```text
volume_cm3
```

Wrapping paper should validate:

```text
sheet px
repeat coverage
dpi
bleed
colour
supplier SKU
```

The **pack concept stays universal** while the artifact validator changes by process.

---

# 15. Add one thing to Product Packs: creative/marketing truth

I would extend the pack with something like:

```json
{
  "marketing": {
    "positioning": "Your pet's face, all over their presents.",

    "audiences": [
      "dog owners",
      "pet parents",
      "Christmas gift buyers"
    ],

    "angles": [
      "funny",
      "cute",
      "stocking-season"
    ],

    "claims": [
      "made from your photo",
      "printed to order"
    ],

    "forbidden_claims": [
      "next-day delivery",
      "waterproof"
    ],

    "hero_assets": [...],

    "hooks": [...],

    "motion_recipes": [...]
  }
}
```

Marketing agents are then constrained by facts.

This is how you safely automate marketing.

---

# 16. The Product Pack should also certify generative personalization

For a generated product, the pack needs to pin:

```text
transform id + version
prompt id + version
renderer id + version
QC contract
sample outputs
```

For example:

```text
Pet Santa Wrapping Paper

transform:
    pet_santa_v1

renderer:
    wrap_repeat_v1

QC:
    identity preserved
    one pet only
    correct dimensions
    alpha valid

supplier:
    WRAP-1-50X70
```

Then a LISTABLE generated product means:

> we have proven the entire transform → renderer → print path.

That is much more meaningful than merely having a prompt.

---

# 17. Recent transformation push: major improvement

`936d60e` fixed almost every issue I raised in the previous review.

It now has:

- no fake `local.composite` identity transform;
- canonical prompt loading;
- standardized ready/running/failed semantics;
- persistent transformed asset records;
- cache reuse;
- mechanical QC;
- actual wrapping-paper renderer;
- exact Prodigi sheet dimensions;
- route SKU fix for card fulfilment;
- country selector.

That was a very productive push.

But two serious runtime problems remain.

---

# 18. `compile_wrap()` currently cannot actually generate Santa

This is the biggest current transformation bug.

It calls:

```python
transform(
    tid,
    ...,
    policy="free"
)
```

But you just correctly removed the fake free identity provider.

The identity route is now:

```text
Higgsfield
Alibaba
fal
```

which are paid.

Therefore a real:

```text
pet → Santa
```

compile will fail by design unless `motif_path` is manually injected.

Your offline test passes because it injects:

```text
motif_path=santa.png
```

So the architecture test is green while the actual customer path is still blocked.

The next implementation needs:

```text
generation_policy
credit authorization
or subsidized P0 generation
```

passed into the compiler.

For P0 I would simply subsidize a tiny number of generations.

Don't build the full credit economy before seeing one real sheet.

---

# 19. Async generation is also not handled end-to-end yet

Your normalized provider contract now correctly supports:

```text
running(job_id)
```

But `compile_wrap()` currently expects:

```text
artifact now
```

If FAL or Alibaba returns a queued job, `transform()` returns a running state and `compile_wrap()` treats that as failure.

You need:

```text
compile job
  ↓
transform queued
  ↓
poll/worker
  ↓
artifact ready
  ↓
QC
  ↓
resume recipe
  ↓
render wrap
```

This same job model will be useful for cards.

Build it once.

---

# 20. Provider artifacts should be ingested into OddHobb storage

Do not build product recipes directly from temporary remote model URLs.

The current transform code may retain:

```text
https://provider/.../temporary.png
```

A reusable transformed asset should instead be:

```text
provider output
    ↓
download
    ↓
QC
    ↓
hash
    ↓
OddHobb R2/storage
    ↓
stable asset ID
```

Only then:

```text
qc_status = passed
```

and only then should product recipes consume it.

This is critical for:

- reproducibility;
- cache;
- orders next week;
- marketing reuse;
- provider URL expiry.

---

# 21. The current wrapping renderer is fine as P0 — don't beautify it yet

`backend/renderers/wrap.py` is exactly the right kind of code:

```text
motif in
→ deterministic repeat
→ exact Prodigi dimensions
```

It's simple.

That's good.

Get:

> Biscuit wearing Santa hat → real sheet → real order

before making 40 sophisticated repeat algorithms.

---

# 22. Site design: the large empty space has an exact cause

This isn't mysterious.

`site-shell.css`, which loads after the inline CSS, contains:

```css
body.studio-chrome .panel .panel__inner {
    max-width:1200px;
    padding:110px 28px 70px;
}
```

Your old top banner/search bar has mostly disappeared.

But **110px of reserved header space remains**.

That is the giant useless blank strip in the screenshot.

Delete it.

For the current shell I would make this approximately:

```css
body.studio-chrome .panel .panel__inner {
    max-width:1200px;
    padding:24px 28px 70px;
}
```

Then explicitly reserve horizontal space for floating controls instead of vertical dead space.

---

# 23. You currently have several design systems fighting each other

This is another major frontend problem.

The main `index.html` contains a huge inline stylesheet using:

```text
Playfair Display
Inter
JetBrains Mono
```

Then you have:

```text
site/styles/tokens.css
site/styles/base.css
site/styles/components.css
```

which define:

```text
Instrument Serif
Inter
```

Then `site-shell.css` overrides many of those rules again.

The main app doesn't even consistently load the newer tokens/base/components system.

So right now typography/color/layout depend on:

> which selector loaded last.

That is why parts of the product feel like separate websites.

Do a CSS consolidation before adding themes.

---

# 24. The typography you like on the Art page is basically Inter

This is a useful discovery.

`art.js` creates:

```html
<h3 class="oc-art-title">
```

But there is **no dedicated `.oc-art-title` style** in the stylesheet.

So it falls through to the site body:

```css
font-family: Inter
```

and browser heading weight.

That's what you're liking in the screenshot.

Not Playfair.

I'd make that the canonical OddHobb UI typeface.

Use:

```text
Inter 400 — body
Inter 500 — controls
Inter 600 — section headings
Inter 700 — big UI headlines
```

Actually load 700 rather than relying on synthetic bold.

Then use:

```text
JetBrains Mono
```

only for:
- IDs;
- technical statuses;
- receipts/debug.

And keep serif/hand fonts **inside products**, not as the basic app chrome.

This would immediately make the site feel more coherent and modern.

---

# 25. I would remove Playfair from the actual application UI

The product cards themselves can absolutely contain:

```text
Fraunces
Caveat
Courier
generated lettering
```

because those are creative products.

But OddHobb itself should be neutral enough to showcase wildly different things.

I would use the Art screenshot as the reference:

> clean Inter, black, lots of confidence, no forced whimsical serif.

That gives the generated art room to be weird.

---

# 26. Your floating-sidebar idea is much better than the current rail

You're also surprisingly close to it already.

You already have:

```html
<button id="brand-btn" title="Switch world">
```

with a:

```html
<div id="switcher">
```

So the “click logo to switch OddHobb/Pogtown” architecture already exists.

It just needs to be visually separated from the navigation.

Canonical layout:

```text
[OddHobb logo]                         [ account ][ cart ]

        ╭────────╮
        │ quick  │
        │ studio │
        │ shop   │
        │ cards  │
        │ video  │
        │ ...    │
        ╰────────╯


              MAIN CANVAS
```

Logo belongs directly on the canvas.

Rail floats below it.

Account/cart float top-right.

No fixed full-height wall.

---

# 27. Exact shell I would implement

Conceptually:

```css
.world-logo {
    position: fixed;
    left: 16px;
    top: 14px;
    z-index: 100;
}

.tabrail {
    position: fixed;
    left: 12px;
    top: 74px;
    bottom: 14px;
    width: 58px;

    border-radius: 22px;
    background: var(--chrome-bg);
    border: 1px solid var(--chrome-border);
    backdrop-filter: blur(18px) saturate(130%);
    box-shadow:
        var(--chrome-glow),
        0 12px 40px rgba(0,0,0,.12);
}

.acct-float {
    position: fixed;
    top: 14px;
    right: 14px;
}
```

And panels no longer start at:

```text
left: 72px
```

They own the whole canvas.

Their content simply has a safe left inset where appropriate.

---

# 28. Seasonal themes become trivial if you do the shell this way

Do **not** create separate Halloween pages.

Define semantic tokens:

```css
:root {
  --canvas: #faf9f6;
  --text: #202020;

  --chrome-bg: rgba(255,255,255,.66);
  --chrome-border: rgba(30,30,30,.10);
  --chrome-glow: 0 0 0 transparent;

  --accent: #c4891a;
}
```

Halloween:

```css
body[data-theme="halloween"] {
  --canvas: #080707;
  --text: #f6eee4;

  --chrome-bg: rgba(20,12,8,.68);
  --chrome-border: rgba(255,111,24,.30);
  --chrome-glow: 0 0 28px rgba(255,92,12,.24);

  --accent: #ff721b;
}
```

Christmas:

```css
body[data-theme="christmas"] {
  --canvas: #08130e;
  --text: #f8f2df;

  --chrome-bg: rgba(10,35,23,.65);
  --chrome-border: rgba(218,174,82,.30);
  --chrome-glow: 0 0 26px rgba(196,36,45,.20);

  --accent: #d8ad57;
}
```

Then the entire application transforms without any structural changes.

Exactly the vibe you described:
- black Halloween canvas;
- orange-lit floating islands;
- seasonal product art on top.

---

# 29. Pogtown should use the same shell

Do not build another interface.

Make:

```text
Shell
 ├── OddHobb world config
 └── Pogtown world config
```

The world config chooses:

```text
logo
navigation
routes
theme defaults
account/cart equivalents
```

Then the brand button opens:

```text
OddHobb
Pogtown
```

Same spatial memory.

Different world.

That's much stronger than two independently evolving sites.

---

# 30. Current Product Pack doctrine + site theme + generation actually fit together beautifully

The architecture can become:

```text
SUBJECTS
who are Dad / Chris / Biscuit?

       ↓

TRANSFORMATIONS
what reusable visual forms do they have?

       ↓

RECIPES
what creative products can we compose?

       ↓

PRODUCT PACK
is this thing actually safe / profitable / listable?

       ↓

SHELF
show finished things

       ↓

COMMERCE
buy

       ↓

PROVEN PACK
real sample passed

       ↓

MARKETING AGENTS
ads / Pinterest / Etsy / content
```

This is finally coherent.

---

# Coding-agent directive

I would paste the following into the agent essentially verbatim:

```text
ODDHOBB PEER REVIEW — FREEZE ARCHITECTURE, FIX CREATIVE QUALITY + SHELL

1. CARDS: DO NOT BUILD ANOTHER CARD SYSTEM.

Current card commerce architecture is good:
subject → recipe matcher → compiler → immutable revision →
Front/Inside/Back → basket → Shopify → Prodigi.

Keep it.

The current visual shelf is NOT good enough and must not be treated
as finished merely because the card pipeline works.


2. EXPLAIN CURRENT BAD VISUALS CORRECTLY.

The current six birthday cards mostly use deterministic PIL drawing:
rectangles, circles, scatter dots, generic CC0 balloon/cake assets,
flat colour and live type.

TEMPLATE_BACKDROPS references generated artwork but the actual
assets/card-art/backdrops library does not exist, so these templates
fall back to flat primitive designs.

The gallery also deliberately compiles with title_art=False.

Do not attempt to "improve" these cards by drawing more PIL confetti.


3. BUILD THE NEXT CARD GENERATION AROUND SCENE PLATES.

Use AI for visual ingredients and OddHobb for product geometry.

Template authoring flow:

concept
→ generate 8–32 candidate scene plates
→ select/approve one
→ lock subject region, safe areas and title region
→ publish template

Runtime:

published scene template
+ subject reference photos
→ identity_scene_inject capability
→ QC-passed visual plate
→ deterministic live typography
→ card renderer
→ exact print master.

Never ask image generation models to render final product typography.


4. USE THE GOOD CONCEPT LIBRARY.

templates/catalog.json already contains valuable concepts:
late-night interview, roast stage, trophy lift, post-match interview,
family biopic, breaking news, Christmas press conference, etc.

These are internal recipe seeds.

Do NOT expose "Use this idea" to customers.

Graduate good concepts into executable published card recipes.


5. FIRST AI CARD RECIPES.

Create only enough to prove the approach:

birthday_late_night_v1
birthday_trophy_lift_v1
birthday_family_biopic_v1
birthday_news_scene_v1

Keep birthday_four_photos as the deterministic baseline.

Every AI recipe returns the same existing card object:
Front / Inside / Back / print export.

No new card API.


6. FIX RECIPE COPY DIVERSITY.

compiler.py currently effectively generates:
"Happy Birthday, <label>!"
for every birthday recipe.

Recipes must own copy strategy.

A press-conference recipe should produce press-conference copy.
A news recipe should produce headline copy.
A biopic should produce biopic copy.

Do not hardcode one occasion headline across every renderer.

Likewise title_vibe must not always be playful_balloons.


7. REPURPOSE birthday_fullbleed.

birthday_fullbleed is the closest existing architecture to the desired
AI-card system.

Change its generated scene instruction to require:
NO text
NO lettering
NO logos
clean typography-safe area.

All text is rendered live by OddHobb after the artwork exists.

Publish scene recipes on top of this renderer rather than adding another
rendering engine.


8. TEMPLATE QUALITY GATE.

A card template is publishable only after being tested across multiple
different identities/photos.

Minimum:
- 8 subjects
- identity retained
- exactly expected subject count
- no gibberish text in generated art
- no watermark
- safe title region
- image resolution pass
- crop/face visibility pass
- deterministic print export pass

Taste is curated when the template is authored.
Runtime generation should vary identity, not redesign the composition.


9. PRODUCT PACKS: KEEP THIS SYSTEM.

Product packs are the canonical launch gate.

DRAFT → PRINT_READY → LISTABLE → PROVEN stays.

Marketing agents may:
- create organic/listing material from LISTABLE;
- spend on paid ads only for PROVEN.

Agents consume pack facts; they do not invent product truth.


10. GENERALISE PACKS BY DOMAIN.

Current schema/G05 is 3D-centric.

Keep one Product Pack concept but support domain validators:

manufactured_mesh
flat_print
multi_panel_print
digital_media

Flat-print validation should check:
dimensions, DPI, bleed, safe area, colour mode, print hash and supplier SKU,
not volume_cm3.

Do not create an entirely separate Card gate system.


11. ADD GENERATIVE PROVENANCE TO PACKS.

A personalised generative product pack pins:

transform_id + version
prompt_id + version
renderer_id + version
QC contract
supplier SKU
approved sample outputs

A model/prompt update must produce a new version and revalidate.


12. MARKETING AGENTS READ PACKS.

Add a controlled marketing section:

positioning
audiences
angles
approved claims
forbidden claims
hero assets
hooks
motion recipes

Marketing outputs must cite the pack revision/source hashes internally.

No paid ads below PROVEN.


13. TRANSFORMS: CURRENT PUSH IS GOOD BUT FINISH THE RUNTIME.

936d60e correctly added:
- prompt canonicalization
- transformed_assets
- caching
- output normalization
- mechanical QC
- real wrap renderer
- removal of fake free identity provider.

Do not add new transform families yet.


14. FIX compile_wrap REAL GENERATION.

compile_wrap currently invokes identity transformation with policy="free".

There is intentionally no free identity_transform provider anymore.

Therefore the true Pet Santa path cannot currently execute.

Add an explicit generation policy / credit authorization.
For initial P0 it is fine for OddHobb to subsidize a small number.


15. ADD ASYNC TRANSFORMATION JOB RESUME.

A provider may return running(job_id).

Do not treat that as transformation failure.

Implement:
compile request
→ queued transform
→ worker/poll
→ artifact
→ ingest
→ QC
→ resume recipe
→ render finished product.


16. INGEST PROVIDER OUTPUTS.

Never make product recipes depend on expiring provider URLs.

provider URL
→ download
→ mechanical QC
→ hash
→ store in OddHobb storage
→ stable transformed_asset
→ mark qc_status=passed.

Only qc_status=passed transformed assets may enter product renderers.


17. DO NOT EXPAND WRAPPING PAPER YET.

The deterministic wrap renderer is good enough.

First proof:
real Biscuit photo
→ real pet_santa transform
→ stable transformed asset
→ repeat renderer
→ exact Prodigi sheet
→ purchase one.

Then add natural language edits.


18. SITE: REMOVE 110PX DEAD HEADER SPACE.

site-shell.css currently overrides panel content with:

padding: 110px 28px 70px

despite there no longer being a 110px header.

Change the shell so pages begin near the top of the canvas.


19. CANONICAL SITE TYPEFACE = INTER.

The Art-page typography the founder likes is effectively the site's
default Inter because oc-art-title has no special font rule.

Make Inter the canonical application typography:

Inter 400 body
Inter 500 controls
Inter 600 section headings
Inter 700 major headings

Load actual 700 weight.

JetBrains Mono only for technical/receipt/status data.

Remove Playfair as general application UI typography.
Creative product artwork may still use Fraunces/Caveat/etc.


20. CONSOLIDATE CSS BEFORE THEMES.

There are currently competing systems:
- giant inline index.html stylesheet
- site-shell.css
- styles/tokens.css
- styles/base.css
- styles/components.css

Choose one token source and remove selector warfare.

Do not add Halloween CSS separately throughout components.


21. BUILD FLOATING CHROME.

Move OddHobb logo out of the tab rail.

Logo:
fixed top-left on bare page canvas.

Navigation rail:
floating vertical rounded glass panel,
left: 12–16px,
top below logo,
bottom: 14px,
backdrop blur,
soft border/shadow.

Account + basket:
existing floating pills top-right.

Panels:
full canvas behind the chrome, not offset by a solid sidebar.


22. WORLD SWITCHER.

brand-btn / switcher already exists.

Expand it to:
OddHobb
Pogtown

Both worlds use one shared shell/layout and supply different nav/routes/
brand/theme config.

Do not fork the frontend.


23. THEMES ARE TOKENS.

Add semantic variables:
--canvas
--text
--chrome-bg
--chrome-border
--chrome-glow
--accent
--surface

body[data-theme=halloween]:
black canvas + orange glow.

body[data-theme=christmas]:
deep green/near-black canvas + gold/red glow.

No DOM/layout differences between themes.


24. NEXT ACCEPTANCE TESTS.

A. CARDS
Create Chris with four photos.
Birthday shelf must include:
- at least one excellent AI scene card
- at least one excellent deterministic photo card
- 5+ visibly different finished options.
Each must open exact Front / Inside / Back and buy at £2.99.

B. TRANSFORM
Upload Biscuit.
Pet Santa transform must create one stable qc-passed transformed asset.
Wrapping-paper recipe reuses it without spending twice.

C. PACK
Generated wrapping-paper product must have a pack/gate path that can
eventually reach LISTABLE and PROVEN.

D. SHELL
No empty 110px header.
Logo floats top-left.
Rail floats independently.
Account/cart float top-right.
Switching Halloween theme changes only tokens.
Mobile remains usable.

25. STOP CONDITIONS.

Do not build:
- another card API
- another card renderer
- another generic creative browser
- another transform family
- more wrapping repeat modes
- more hardware abstractions

until:
one AI-quality card is genuinely excellent,
one paid card physically arrives,
one real Pet Santa wrap preview is generated from a provider,
and the new shell is coherent.
```

The highest-leverage change now is **not more platform code**. It is to take one of your genuinely good concepts—I'd use **Late-night Interview** or **Trophy Lift**—generate an exceptional locked scene template with the models you already have access to, personalize Chris into it, and put that next to these balloon cards.

The contrast will make the problem immediately obvious: the card pipeline itself is no longer the bottleneck. **Art direction is.**