# cardgen — OddHobb cards, agent-first and generative

> A card is generated art of *your actual people*, from *your actual photos*,
> with one joke that fits them. It is never a photo pasted into a clip-art frame.

This replaces the PIL template system (`backend/card_scenes.py`,
`backend/card_grammars.py`, `recipes/birthday_*`, the arch/dots/gold/news/wall
shelf). Code never draws a card. Code only prepares the inputs, calls the model,
checks the result, and sets out the print file.

## The pipeline (one card)

```
 photos (uploaded)                     template (JSON, authored once)
      │                                         │
 1 INDEX   faces, people, shot type,           │
           quality, who-is-who (SFace)          │
      │                                         │
 2 CAST    template.cast ──► pick the photos ◄──┘
           (solo face / couple / group of N / full body / pet)
      │
 3 WRITE   LLM fills template.copy slots (title, sub, inside message)
           within hard limits; 3 options, the agent picks one
      │
 4 GENERATE  capability `identity_scene`: reference photos + filled prompt
           ──► full-bleed 5:7 front art, lettering INCLUDED in the art
           (a provider router: fal nano-banana/edit → seedream edit → kontext)
      │
 5 QA      a. OCR: the art's text == the copy, nothing extra (tesseract)
           b. likeness: SFace cosine of each cast face vs the source ≥ 0.30
           c. faces: count == cast size; no extra people
           d. vision critic: joke readable, hands/eyes OK, no artefacts
           FAIL ──► targeted edit (remove stray text / fix face) ──► recheck, max 2
      │
 6 SPOT    inside-left vignette in the same style (generated from the front)
      │
 7 UPSCALE ≥ 1563×2161 (5×7 + bleed at 300 dpi), capability `upscale`
      │
 8 IMPOSE  print master (Prodigi 7×5 JPG/PDF) + 3 previews: front, inside, back
           inside-right message = LIVE type (editable per order, never baked)
           back = renderer-owned oddhobb.com mark
      │
 9 FREEZE  revision = template@version + photo ids + copy + art hashes
           ──► checkout pins the revision (existing Shopify/Prodigi path)
```

PIL appears in step 8 only, the way a printer uses a guillotine. It never designs.

## Templates read from photos, not from coordinates

A template has no geometry. It declares a **cast** (who must be in it and from
what kind of photo), a **scene** prompt with slots, **copy** slots with limits,
and **QA** expectations. See `templates/*.json`, schema in `template.schema.json`.

| Template | Cast | Photo it reads | Front |
|---|---|---|---|
| `golf_lip_v1` | 1 hero | solo face (+ full body if present) | gouache caricature, ball on the lip |
| `movie_poster_couple_v1` | hero + partner | couple selfie | 1950s romance poster |
| `band_album_group_v1` | hero + 1-4 | group photo, all faces ≥ 60 px | 70s LP cover, hero as frontman |
| `comic_shock_v1` | 1 hero | an expressive face (open mouth / wide eyes) | pop-art comic panel |
| `pet_portrait_royal_v1` | 1 pet | clear pet face | Renaissance oil portrait |
| `xmas_family_v1` | whole family 2-6 | group photo | snow-globe family scene |

## Casting rules (step 2)

- Shot types come from the index: `solo` (1 face ≥ 8% of the frame), `couple`
  (2), `group` (3-6), `full_body` (1 face, body visible), `expressive`
  (mouth-open/eyes-wide score), `pet`.
- The hero must be identified by SFace against the subject's tagged faces. A
  group photo is only used when every cast member is recognised or the template
  says `unnamed_ok`.
- More reference photos of the hero improve likeness: pass up to 3 solo crops
  plus the group photo.
- If no photo fits a template, the template is not offered. Never fall back to
  a collage.

## Copy rules (step 3)

- Title ≤ 28 chars, sub ≤ 36, inside message ≤ 240, signature ≤ 40.
- Jokes come from the person's profile (interests, relationship, tone). Every
  template ships 3 example jokes as style anchors, and the LLM writes new ones.
- The art carries title + sub as lettering. The inside message and signature
  are live type, so the buyer can edit them without regenerating.

## The agent's loop

`run.py make --subject chris --occasion birthday --n 4`
1. rank templates by cast feasibility × profile fit (golf ⇒ golf_lip high)
2. for the top N: cast → write → generate → QA (retry) → spot → upscale → impose
3. return N finished cards, each three previews + a print master + a price

The customer sees "I made these 4 for Dad", picks one, optionally edits the
inside message, and buys.

## Providers (capabilities, not vendors)

| Capability | Primary | Fallbacks |
|---|---|---|
| `identity_scene` | fal `fal-ai/nano-banana/edit` | `fal-ai/bytedance/seedream/v4/edit`, `fal-ai/flux-pro/kontext/max/multi` |
| `edit_fix` | same as above, with an edit prompt | — |
| `upscale` | fal `fal-ai/clarity-upscaler` | `fal-ai/esrgan` |
| `copy` | openrouter LLM | — |
| `critic` | openrouter vision LLM | — |

Cost per card is about 3-6 image calls (front, ≤2 fixes, spot, upscale). Only
the card the customer picks is upscaled and imposed at print size.


## Wired to the backend (engine.py), the canonical path

```
POST /api/cardgen/recommend {subject_id, occasion}   ready: templates these photos can make, with photo ids
                                                     blocked: "needs a happy couple photo with them in it"
POST /api/cardgen/make {subject_id, template_id}     -> job_id (202), worker thread
GET  /api/cardgen/jobs/<job_id>                      step: index > write > generate > qa0..2 > spot > upscale > freeze
                                                     ready: design_id + revision, front/inside/back views, £ price, checkout
MCP  oddhobb_make (public)                           cardgen first; legacy PIL shelf only if cardgen can't start
     oddhobb_card_recommend / oddhobb_card_generate  keyed tier; oddhobb_get(design_id=cgj_...) polls a job
```

| Step | Backend piece it uses |
|---|---|
| index | `photos`, `photo_faces` (YuNet), `face_embeddings` (SFace), `photo_subjects` (confirmed tags) |
| labels | `backend/photo_labels.py`, L5 expression and framing per face. One vision call per photo, cached, fail-closed |
| cast | `template.wants` per role (shot, identity, people, expression, framing, min_face_px, refs) |
| refs | the cast photo first, then the hero's clearest tagged solos (R2 presigned, 1 h) |
| generate / fix / spot / upscale | `backend.creative.providers.fal` `_submit`/`_result`, each call logged via `log_spend` |
| QA | tesseract OCR (no stray words), YuNet face count + SFace likeness ≥ 0.30, vision critic. Fail = targeted edit, max 2, then the job fails (never attaches a bad card) |
| freeze | `cards.attach_art(front 5:7, inside 10:7)` → `birthday_fullbleed` revision → existing preview/spread/export jobs, £2.99, Shopify checkout, Prodigi |

The fullbleed renderer in `card_scenes` owns the inside message type, the signature and the back.
cardgen never draws type on the inside or the back.

`python -m cardgen.demo_offline <photos+art dir> <out> labels.json` is the acceptance harness. It runs
real photos through YuNet + SFace into a throwaway DB, casts, runs the engine with pre-made art in place of fal,
attaches through the real `cards.attach_art`, and renders through the real fullbleed renderer.

### Same spec for products
`wants.to_requires(template["wants"])` gives `subject_assets.select_for_template` its `requires`, and the
selector now honours `emotions` and `framing` (L5 is live). So a product can say "a laughing solo, waist up"
the same way a card does.

## Files

- `templates/*.json`: the card templates (immutable; a change is a new `_vN`)
- `photos.py`: index + shot types + casting
- `providers.py`: capability router (fal), fail-closed without a key
- `qa.py`: OCR text gate, face-count + likeness gate
- `impose.py`: Prodigi 7×5 print master + front/inside/back previews
- `engine.py`: the backend-wired pipeline (index, cast, write, generate, QA, spot, upscale, attach_art)
- `wants.py`: the photo wants spec shared with products
- `demo_offline.py`: the acceptance harness
- `run.py`: the original standalone loop (superseded by engine.py)
- `proof/`: the first four cards made with this pipeline (Chris, Oct 2026)
