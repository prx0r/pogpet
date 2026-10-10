# External review: stereoframe + cards/transforms audit (verbatim 2026-10-10)

> stereoframe (MIT): GLB in, auto-framed shots (reveal/hero orbit/
> cinematic), multi-shot MP4 with DoF/bloom/grain, JSON-driven — evaluate
> for motion rigs. Cards verdict: architecture fixed, stop redesigning,
> finish commerce gaps. Transformations: schema good, not yet executable.
> Committed instruction: two vertical slices (Cards P0, Santa wrap).

## State (%)

Birthday architecture 90 · shelf UX 85–90 · Front/Inside/Back 90 · £2.99
consistency 95 · Shopify basket/checkout 80 · Value/Speedy 55–60 · paid→
Prodigi route 70 · Christmas ~10 (now 2 live recipes — ed) ·
transform schema/router 65 · reusable transformed assets 25 · Santa→wrap→
buy ~15.

## Cards: fixed

`_compiler_shelf()`: subject → profile → pool → matcher → published
recipes → compiler → immutable revisions → gallery. Six birthday recipes
£2.99, asset gating (1 photo → several, 2 → wall, 4 → four-photo). Viral
browser removed from P0 — do not undo. UI: Cards for Chris → View /
Different photos / Buy £2.99 → FRONT/INSIDE/BACK. Right product.

## Cards: four blockers

1. **Shipping money not wired.** Cart adds only the £2.99 variant; the
   £1.49/£9.49 selector is cosmetic unless Shopify charges it. P0 fix:
   Shopify owns Value/Speedy rates + payment; webhook reads the paid
   shipping line (Value → Standard, Speedy → Express). Show estimates
   pre-checkout only. No second shipping-charge system.
2. **US fulfilment bug.** Router quotes GLOBAL for US, but webhook always
   orders `CARD_PRODIGI_SKU` (CLASSIC). Fix: `sku = route.sku or
   CARD_PRODIGI_SKU`; frozen route owns sku + method + market.
3. **GB hardcoded** in gallery delivery call. P0: UK-only stated, or a
   country selector before Value/Speedy (address still at Shopify).
4. **`CARD_PANEL_CONFIRMED` gate.** Real acceptance = physical card at the
   door; freeze after.

Do not: new frameworks, editor controls, viral, preview types, card APIs.
FAL title art correctly deferred (gallery compiles `title_art=False`).

## Transformations: 8 bugs

1. `pet_santa_v1` "succeeds" via `local.composite` with no artifact.
   Fix: output contract (`artifact` or `job_id` or fail); drop composite
   from `identity_transform` unless it really transforms.
2. Adapters disagree: fal → `request_id`, Alibaba/Higgsfield → `task`.
   Normalize to `ready(artifact)` / `running(job_id)` / `failed(error)`.
3. Higgsfield `is_available False` even with key — placeholder, flip on key.
4. Wrap recipe invents `face_styled_variant` — use `transform_id:
   pet_santa_v1`; transform owns capability/prompt/routing/contract.
5. Prompt duplication + contradiction (`xmas-santa-hat-v1.md` says person/
   no animals for a pet transform). Prompt registry canonical; transform
   cites `prompt_id` only.
6. QC is metadata. Minimum mechanical QC first (decode, dims, aspect,
   alpha, subject count); identity similarity later. Failed outputs never
   enter print recipes.
7. No persistent `transformed_assets` object (id/owner/subject/transform/
   refs/artifact/provider/qc/created) + cache key over
   (transform, version, references, overrides). Generate Santa once.
8. Nothing calls `transform()` in production. Keep it internal: wrap
   recipe → transform → renderer. Never raw transforms on public MCP.

## Wrapping slice status

SKU ✔ quote ✔ prices ✔ recipe draft ✔ santa prompt ✔ registry ✔ router ✔
— transformation ✘ persistent asset ✘ renderer ✘ preview ✘ checkout ✘
fulfilment ✘. Next: pet photo → pet_santa → PNG → cutout → wrap_repeat →
preview → print master → quote. Then natural_edit, Soul, Marketing,
credits. Acceptance: pet photo → Santa sheet preview → reusable asset →
exact Prodigi print file.

## Sprint order

Card shipping/fulfilment → real card order → wrap_repeat renderer → one
real finished transformation → Santa preview → wrap order → back to
packs/hardware. Proof beats platform: one Dad card + one Santa sheet at
the door.
