# Multimedia generation stack (founder research, verbatim 2026-10-10)

> Discovery: build substantially less image-generation infrastructure
> than assumed. fal = supermarket + LoRA lab + emergency ComfyUI; Alibaba
> = cheap high-volume core + editing; Higgsfield = identity + marketing
> imagery; OddHobb = transformation recipes + product recipes + taste +
> commerce. Upload Cathy once → hundreds of tasteful products, no giant
> stack. Implemented: `transforms/`, `backend/creative/transform.py`,
> capability routes in `providers/router.py`.

## Platform roles

| Platform | OddHobb use | Notes |
|---|---|---|
| **Alibaba Model Studio** | high-volume transformations + edits | Qwen Image 3 (generation + editing, 1–3 refs, 6 variants, dense layouts/small text), Wan 2.7 (9 refs, character-consistent sets, interactive editing; Pro to 4K). Singapore pricing example: Qwen 3 standard $0.003/input + $0.03/1K out, Pro $0.003 + $0.04; Wan 2.7 $0.03, Pro $0.075. fal-hosted Qwen 3 is $0.075/image — so direct Alibaba is the plausible cheap default worker. |
| **fal.ai** | unified layer + experiments + LoRAs + utilities | FLUX 2 (Pro Edit: 9 refs, plain-language compositing), Qwen 3 behind one SDK, Recraft style IDs (1–10 refs → reusable `style_id`, $0.005, SVG output), BiRefNet cutout/masks, fast FLUX LoRA trainer (~$2/run), Kontext/Qwen Edit + LoRA, hosted ComfyUI deployment. |
| **Higgsfield** | persistent people + finished marketing imagery | Soul ID (1–100 photos once → persistent `custom_reference_id`, Soul 2 image-to-image ~$0.0032–0.0057/image, ID creation $2.50 — promote frequent subjects only). Marketing Studio / Product Shots / Marketplace Design presets fetched at runtime — do not build our own listing-image system; render the accurate product, send it for hero/lifestyle imagery. Apps catalog (Packshot, Poster, Macro, Angles, Background Remover, Character Swap, 3D Figure, ad transforms) is a recipe mine. |

## Progression (not all at once)

```text
Prompt only → Prompt + reference → Reusable Recraft style ID
    → LoRA only when a style earns permanent specialization
reference images → Higgsfield Soul ID only for high-frequency humans
```

Alibaba SFT-LoRA (Wan 2.7, some Qwen) is P2 — interesting once we hold a
large proprietary transformation dataset.

## Transformation library (built as `transforms/*.json`)

None of these is a product. One expensive transformation becomes reusable
inventory across recipes — and matters for credit economics.

| Transformation | Input | Implementation | Unlocks |
|---|---|---|---|
| `subject_cutout_v1` | photo | fal BiRefNet | wrap, stickers, tags, cards |
| `pet_santa_v1` | pet refs | Qwen 3 edit | wrap, cards, poster, tags |
| `editorial_gouache_v1` | person refs | Qwen / Recraft style | cards, prints |
| `sports_champion_v1` | person refs | Soul 2 / FLUX multi-ref | cards, posters |
| `news_portrait_v1` | person ref | Qwen / FLUX | cards |
| `christmas_badge_v1` | person/pet | Qwen + cutout | wrap, labels, stickers |
| `oddhobb_woodcut_v1` | subject | Recraft style ID | cards, wrap, print |
| `product_packshot_v1` | finished render | Higgsfield Product Shots | Etsy/Shopify |
| `marketplace_listing_v1` | finished render | Higgsfield Marketplace Design | Etsy/Shopify |
| `natural_edit_v1` | finished asset | Qwen / FLUX edit | "brown paper" etc. |
| `scene_set_v1` | 1–9 refs | Wan 2.7 image set | card series, comics |
| `oddhobb_style_lora_v1` | curated outputs | fal FLUX LoRA | entire catalog |

```text
pet_santa_v1 → wrap recipe + card recipe + poster recipe
```

## ComfyUI: mine it, host on fal, don't operate GPUs

Official `Comfy-Org/workflow_templates` (1000+ commits, workflows +
subgraph blueprints with declared inputs/outputs = visual capabilities)
plus ComfyUI native subgraphs/templates/App Mode/API, `comfy-cli`,
InvokeAI as internal workstation, diffusers for IP-Adapter/ControlNet
reference, ai-toolkit + OneTrainer for LoRA, Impact-Pack, SwarmUI. Avoid
Fooocus (SDXL LTS-only) and IPAdapter_plus/InstantID (maintenance-only)
as new critical deps. Flow: experiment visually → freeze graph + models
→ fal deploy → ordinary HTTP endpoint. Ignore Alibaba's visual workflow
builder (Singapore gating, Beijing-only templates) — own orchestration,
use their models as workers.

## Provider router (built)

Never `fal_provider`/`alibaba_provider` from the product's view.
`transform(capability, references, instruction, contract)`; router picks:

```text
identity_transform human → Soul 2 if Soul ID exists, else Qwen 3
text_heavy_art → Qwen 3
consistent_image_set → Wan 2.7
brand illustration → Recraft style
bespoke chain → fal-hosted ComfyUI
listing hero → Higgsfield Marketing Studio
```

Steal the preset architecture: transforms declare id/capability/
references/instruction/preserve/output/qc; recipes cite `transform_id`,
never giant prompts.

## Pet Santa wrapping experiment (the demo)

1. Upload 3–5 pet images, confirm identity. 2. Rank best refs.
3. Direct Alibaba Qwen 3, 1–3 refs: exact eyes/markings/muzzle/ears +
   tasteful Santa hat, plain background. 4. BiRefNet → transparent motif.
5. Three deterministic repeats: classic, scattered, badge. 6. Finished
   previews. 7. "Brown paper, remove candy canes" → change background/
   decoration layers only, never regenerate the pet. 8. "Knitted green
   hat" → edit just the ingredient. 9. Save revision, buy. This demos the
   whole company: identity → transformation → reusable ingredient →
   constrained product → natural-language edit → physical object.
