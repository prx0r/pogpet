# Remix + Royalty Ideas for OddHobb
I dug through the current `pogpet` data model as well as how Printify, Canva, Polotno and IMG.LY structure personalization. The correct answer is **not “add a canvas editor.”** The correct answer is to make OddHobb a **versioned personalization compiler**.

Printify's useful idea is predefined editable text/image layers + live preview + an approval gate. Canva's Autofill model is even closer: query the template's typed dataset, submit structured data, run an asynchronous generation job, then retrieve the populated design. Polotno explicitly recommends storing a template as JSON with variables, replacing those variables with real data, then rendering the resulting JSON. IMG.LY separates template creators from end users through locked/editable roles. Those are all variations of the same architecture. [Printify](https://help.printify.com/hc/en-us/articles/47155179072145-How-do-I-set-up-automated-personalization-for-Printify-Pop-Up-Store?utm_source=chatgpt.com)

## The canonical OddHobb pipeline

```text
PERSON
  │
  ├── profile facts
  ├── relationships
  ├── interests / memories / humour
  ├── photos
  │    ├── detected faces
  │    ├── confirmed identities
  │    └── derived crops / cutouts
  └── meshes
       │
       ▼
CREATIVE BRIEF
occasion + recipient + context + available assets
       │
       ▼
TEMPLATE MATCHER
occasion × style × scene × joke recipe × asset requirements
       │
       ▼
SCENE INSTANCE
immutable structured data
       │
       ├──────────────┬───────────────┬─────────────────┐
       ▼              ▼               ▼                 ▼
2D compositor     AI image        3D/mesh          AI/mesh video
       │              │               │                 │
       └──────────────┴───────┬───────┴─────────────────┘
                              ▼
                        ARTIFACT STORE
              preview / print / social / mp4
                              │
                              ▼
                        VALIDATION / QC
                              │
                              ▼
                    PRODUCT / CHECKOUT
```

The **scene instance is the centre**, not the card, mesh, image or video.

That is the key architectural decision.

---

# 1. Fix the person model first

There is an important schema problem in the current repo.

You already have the correct identity object:

```text
studio_subjects
    id
    owner
    name
    kind
```

and the correct links:

```text
photo_subjects
mesh_subjects
```

But `subject_profiles` is currently keyed by:

```text
(owner, mesh_id)
```

That's backwards.

Dad is not a mesh.

Dad might eventually have:

```text
Dad
 ├── 27 photos
 ├── 4 face crops
 ├── brick mesh
 ├── realistic mesh
 ├── Christmas mesh
 └── voice reference
```

So change the canonical profile to:

```sql
subject_profiles_v2 (
    owner,
    subject_id,
    relationship,
    birthday,
    profile_json,
    updated_at,
    PRIMARY KEY(owner, subject_id)
)
```

with something like:

```json
{
  "name": "Dad",
  "relationship": "dad",
  "interests": ["golf", "Liverpool", "coffee"],
  "personality": ["competitive", "dry humour"],
  "nicknames": ["Big T"],
  "memories": [
    "always falls asleep after Christmas lunch",
    "takes family mini golf far too seriously"
  ],
  "likes": [],
  "dislikes": [],
  "humour": {
    "roasting": 0.8,
    "absurd": 0.9,
    "sentimental": 0.3
  }
}
```

`mesh_subjects` and `photo_subjects` then hang assets from that identity.

Your existing `/cards/gallery` currently does effectively:

```text
photo → find mesh → find mesh profile → name
```

That should become:

```text
photo
→ confirmed photo_subjects
→ studio_subject
→ subject_profile
```

A person must **not need a mesh to get personalized cards**.

---

# 2. Separate raw assets from derived assets

Do not mutate uploads.

An upload becomes an immutable source asset:

```text
asset
  id
  owner
  kind = photo | audio | mesh | video
  sha256
  storage_key
  metadata
  provenance
```

Then derivations become their own assets:

```text
photo_123                      RAW
 ├── facecrop_22               DERIVED
 ├── cutout_31                 DERIVED
 ├── thumbnail_480             DERIVED
 └── print_normalised_2400     DERIVED
```

Your existing `photos`, `photo_faces`, `card_cutouts`, `meshes` can continue to operate; I would introduce an `assets` registry above them gradually rather than rewriting them now.

Critically, keep **identity confirmation separate from face detection**. Your current Studio library already does this correctly: detection proposes boxes; the customer confirms identities. For AI render jobs, use confirmed subject assets rather than attempting to silently identify people.

---

# 3. Templates become data, not Python functions

Right now:

```python
TEMPLATES = {
    "breaking_news": {...},
    "christmas": {...}
}
```

is too primitive.

`christmas` is an occasion.
`breaking_news` is a scene/style family.

They should not occupy the same namespace.

Your attached examples should become something like:

```text
STYLE
newsparody
sportspresser
xmasaisketch
photorealstudio

SCENE
news_anchor
holiday_press_conference
weather_reporter
special_investigation
sideline_interview
trophy_lift
locker_room
pundit_desk

OCCASION
christmas
birthday
fathers_day
retirement
general

JOKE_RECIPE
tired_parents
gift_optimiser
agents_invade_santa
dad_game_winner
family_scandal
profile_roast
```

So a real template version could be:

```json
{
  "id": "holiday_press_conference",
  "version": 3,

  "taxonomy": {
    "occasion": ["christmas"],
    "styles": ["newsparody", "photorealstudio"],
    "topics": ["family", "christmas"],
    "tone": ["ross", "mock-serious"]
  },

  "requirements": {
    "subjects": 1,
    "face_photos_min": 1,
    "mesh": false,
    "voice": false
  },

  "slots": {
    "star": {
      "type": "subject",
      "required": true
    },
    "headline": {
      "type": "text",
      "max_chars": 42
    },
    "subheadline": {
      "type": "text",
      "max_chars": 90
    },
    "location": {
      "type": "text",
      "default": "NORTH POLE HQ"
    }
  },

  "renderers": {
    "preview": "composite2d",
    "hero": "identity_image_v1",
    "print": "composite2d",
    "video": "talking_scene_v1"
  }
}
```

Polotno's dynamic-variable system is almost exactly this model: create the design, export structured JSON, store it, inject real variables when generating a design, then render it. [Polotno](https://polotno.com/docs/dynamic-template-variables?utm_source=chatgpt.com)

---

# 4. Separate the **template manifest** from the visual layout

This is important.

Do **not** make Polotno JSON, Konva JSON or a Photoshop file the canonical OddHobb object.

Your canonical object is the OddHobb template manifest.

Then it can reference:

```text
layout/
    card.polotno.json

assets/
    studio-background.webp
    desk-overlay.png
    lower-third.svg
    mask.png

motion/
    motion.json

prompts/
    image.txt
    video.txt
```

That gives you freedom to replace the renderer later.

The template manifest says **what**.

Polotno/Konva says **where**.

The image model says **how to generate the photoreal layer**.

The video engine says **how it moves**.

---

# 5. AI must fill fields, not design pixels

This is another important boundary.

Do **not** ask the LLM:

> design a funny card for Dad.

Ask it:

```json
{
  "template": "holiday_press_conference:v3",
  "headline": "CHRISTMAS MORNING UNDER REVIEW",
  "subheadline": "Dad denies allegations he assembled everything at 2:14am",
  "scene_variables": {
    "agenda_item_1": "PRESENTS?",
    "agenda_item_2": "BATTERIES?",
    "agenda_item_3": "WHO ATE THE MINCE PIES?"
  },
  "inside_message": "Merry Christmas Dad."
}
```

The LLM never moves a title box.

It never changes bleed.

It never decides print DPI.

It never decides where Dad's face belongs.

That geometry belongs to the template.

IMG.LY's creator/adopter model formalizes the same idea: creators define the scene and constraints; users work within those limits. [IMG.LY Support](https://support.img.ly/how-to-create-templates-for-users-to-edit-in-ce-sdk?utm_source=chatgpt.com)

---

# 6. Create a real **Creative Brief**

Before matching templates, compile everything relevant into one temporary structured object:

```json
{
  "occasion": {
    "id": "christmas",
    "date": "2026-12-25"
  },

  "recipient": {
    "subject_id": "sub_dad",
    "name": "Dad",
    "relationship": "dad",
    "interests": ["golf", "football"],
    "humour": ["dry", "absurd"],
    "memories": [
      "falls asleep after lunch"
    ]
  },

  "available_assets": {
    "photos": 17,
    "confirmed_face_photos": 8,
    "good_portraits": 4,
    "meshes": ["brick", "realistic"],
    "voice": false
  },

  "request": {
    "tone": "funny",
    "budget_cents": 1200
  }
}
```

That object gets thrown at the **matcher**, not directly at the renderer.

---

# 7. Matching needs to be deterministic first, AI second

Each template gets machine-readable eligibility:

```text
requires one person
supports Christmas
good for dads
proud of dads
works with sports interest
requires portrait-quality photo
video-capable
mesh-capable
cost class 2
```

Then score:

```text
occasion match          30
relationship match      10
interest match          15
humour match            15
asset quality            10
novelty                  5
historical engagement   10
profit / cost            5
```

Then use an LLM only for softer ranking and explanation.

This gives you:

> Recommended for Dad because he's into football and likes ridiculous mock-serious humour.

rather than an opaque AI result.

---

# 8. The canonical saved object becomes `creative_revision`

Your current `card_designs` + immutable `card_revisions` model is actually one of the best bits of the repo.

Keep that concept, but generalize it.

```text
creative_projects
    id
    owner
    subject_id
    latest_revision

creative_revisions
    project_id
    revision
    template_id
    template_version
    brief_snapshot_json
    scene_json
    created_at
```

A revision might look like:

```json
{
  "scene_version": "oddhobb.scene.v2",

  "template": {
    "id": "sideline_interview",
    "version": 4
  },

  "subjects": [
    {
      "slot": "star",
      "subject_id": "sub_dad",
      "asset_ids": ["photo_12", "photo_19", "photo_31"]
    }
  ],

  "copy": {
    "headline": "POST-MATCH INTERVIEW",
    "caption": "Dad reacts after carrying Christmas for another season"
  },

  "render_intent": {
    "style": "sportspresser",
    "occasion": "christmas"
  }
}
```

Once revision 4 exists, **never mutate it**.

Editing creates revision 5.

Orders continue referencing revision 4.

Your existing cards system already does this correctly.

---

# 9. Rendering is a DAG

A creative revision should not directly “call AI.”

Compile it into jobs:

```text
scene revision
     │
     ├── copy_validate
     ├── source_select
     ├── preview_compose
     │
     ├── identity_render
     │       └── identity_qc
     │
     ├── final_compose
     │       ├── web_preview
     │       └── print_master
     │
 └── video
             ├── script
             ├── voice
             ├── animation
             └── mux
```

Each node gets a deterministic cache key:

```text
sha256(
 template_version
 + creative_revision
 + renderer_version
 + source_asset_hashes
 + output_contract
 + provider_parameters
)
```

If Dad's card was already rendered, opening it again costs nothing.

If the user only changes the headline, you don't regenerate Dad in the sports stadium.

You only re-run the final compositor.

**That is the cost-saving architecture you want.**

---

# 10. Generated photographs should have NO generated typography

For the kinds of cards you attached, AI should generate:

```text
Dad
stadium
microphone
reporter
lighting
crowd
pose
```

It should **not** generate:

```text
POST-MATCH INTERVIEW
Dad has done it again
```

Those stay deterministic layers.

So:

```text
AI scene plate
       +
template overlays
       +
real typography
       =
final card
```

This gives you:
- perfect spelling
- editable caption
- consistent brand
- proper print resolution
- same lower-third can animate in the video
- localization later

It is a much better system than asking an image model to regenerate the whole card every time.

---

# 11. You actually want three personalization renderers

| Renderer | Use | Cost / latency |
|---|---|---|
| `composite2d` | cutout/photo inserted into designed scene | essentially instant |
| `identity_image` | Dad genuinely appears in a photoreal sports/news/comedy scene | paid/slower |
| `mesh_scene` | Dad's OddHobb character performs inside a scene | render cost |

A template can support any subset.

So `newsparody.breaking_news` may have:

```text
composite2d   ✓
identity_image ✓
mesh_scene     ✓
```

This means every template is progressively enhanced.

A customer might get the instant simple version while the fancy image is rendering.

---

# 12. Video is not a second content system

The same creative revision drives it.

For your sports example:

```text
scene = sideline_interview
star = Dad
headline = POST-MATCH INTERVIEW
joke = Dad reacts after assembling all presents
```

Static path:

```text
scene → PNG → print PDF
```

AI-video path:

```text
scene
→ identity image/keyframe
→ script based on same joke
→ Dad voice if available
→ image-to-video / lip sync
→ broadcast lower third
→ MP4
```

Mesh path:

```text
scene
→ Dad mesh
→ reusable sideline interview animation
→ reusable stadium room
→ generated/recorded voice
→ MP4
```

Same scene. Same joke. Same revision.

The current `videos` table should eventually gain:

```text
creative_project_id
creative_revision
renderer
```

instead of being a second island keyed mostly on `mesh_id + scene`.

---

# 13. Output artifacts need first-class records

Don't infer whether an output exists by looking for a file.

Use:

```sql
render_artifacts (
    id,
    owner,
    project_id,
    revision,
    renderer,
    output_kind,
    cache_key,
    storage_key,
    mime,
    width,
    height,
    dpi,
    duration,
    status,
    qc_status,
    cost_cents,
    provider,
    provider_job_id,
    created_at
)
```

Then one creative revision can expose:

```text
preview.webp
card-front.png
print-5x7.pdf
instagram.jpg
motion.mp4
voice-video.mp4
mesh-performance.mp4
```

Polotno's server renderer already demonstrates that one structured design can emit images, PDFs and MP4s.

---

# 14. Print needs its own output contract

Do not bake “5×7 = some pixels” into scene templates.

Have:

```json
{
  "id": "card_5x7_folded_v1",
  "trim_mm": [127, 177.8],
  "bleed_mm": 3,
  "safe_mm": 5,
  "dpi": 300,
  "pages": ["outside", "inside"],
  "supplier": null
}
```

Then later:

```text
generic_5x7
prodigi_xxx_v1
printify_xxx_v1
local_printer_v3
```

The **creative scene is independent of fulfilment**.

That lets the same design be sent to different suppliers.

Printify follows the same broad principle by defining personalizable layers in the product creator, letting the user's data fill those layers, then holding/reviewing the personalized result before it proceeds to production. [Printify](https://help.printify.com/hc/en-us/articles/28903711308177-What-is-product-personalization-on-Printify?utm_source=chatgpt.com)

---

# 15. Add a proper QC gate

Every renderer produces an artifact plus machine checks.

For cards:

```text
text overflow
missing required field
face crop inside safe area
photo DPI
bleed coverage
correct dimensions
font available
asset URL resolves
```

For AI identity scenes:

```text
job succeeded
correct number of subjects
face region exists
source/template compliance
manual approval if necessary
```

For video:

```text
duration
audio exists
dimensions
codec
subtitle/text bounds
```

Orders should reference only artifacts with:

```text
qc_status = passed
```

Printify similarly lets merchants review personalized output before production, and incomplete personalization can hold an order instead of blindly manufacturing it. [Printify](https://help.printify.com/hc/en-us/articles/47155179072145-How-do-I-set-up-automated-personalization-for-Printify-Pop-Up-Store?utm_source=chatgpt.com)

---

# 16. Template authoring itself gets a pipeline

This is where Polotno is useful.

```text
AUTHOR TEMPLATE
     ↓
visual editor
     ↓
export layout JSON
     ↓
attach OddHobb manifest
     ↓
schema validation
     ↓
fixture renders
     ↓
visual review
     ↓
publish immutable template version
```

Test fixtures should include:

```text
Dad
Mum
pet
very long name
short name
one portrait
five portraits
missing interest data
extremely long generated caption
```

A template doesn't become `live` until all required fixtures render.

Canva's own Autofill architecture follows essentially the same typed-field approach: retrieve the template dataset, inspect allowable field types, submit those structured values to an async autofill job, then retrieve the finished design. [canva.dev](https://www.canva.dev/docs/apps/rest-apis/reference/autofills/?utm_source=chatgpt.com)

---

# The exact changes I would make to `pogpet`

| Current | Change |
|---|---|
| `studio_subjects` | **keep; canonical human/pet identity** |
| `subject_profiles(mesh_id)` | migrate → `subject_profiles(subject_id)` |
| `photos` | keep as immutable raw uploads |
| `photo_faces` | keep |
| `photo_subjects` | keep; this is identity provenance |
| `meshes` + `mesh_subjects` | keep |
| `card_scenes.TEMPLATES` | replace with versioned template registry |
| `card_designs/revisions` | generalize concept to creative projects/revisions |
| `/cards/gallery` | replace hardcoded 3-template loop with template matcher |
| `card_jobs` | migrate toward generic render jobs |
| `videos` | attach to creative revision |
| `card_orders` | order exact validated artifact/revision |
| R2 | raw/derived/template/creative namespaces |

And I would add:

```text
backend/creative/
    briefs.py
    templates.py
    matcher.py
    compiler.py
    jobs.py
    artifacts.py
    qc.py

backend/renderers/
    composite2d.py
    identity_image.py
    mesh_scene.py
    motion.py

templates/
    schemas/
        template.schema.json
        scene.schema.json

    newsparody/
        breaking_news/
        holiday_press_conference/
        weather_report/
        investigation/

    sportspresser/
        sideline_interview/
        trophy_lift/
        locker_room/
        pundit_desk/

    xmasaisketch/
        agents_invade_workshop/
        gift_optimizer/
        personality_engineering/
```
