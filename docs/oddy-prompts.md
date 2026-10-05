# Oddy — Meshy concept prompt pack (NO SPEND without approval)

Asset B of the brand system: a living mascot derived from the logo, never a
separate character. Asset A (exact mark + chip) is already built
deterministically in `scripts/factory/mark.py` — Meshy must NEVER recreate
the logo (drift). All prompts below are **concept exploration only**.

## The design language (paste into every prompt)

> Soft rounded vinyl-collectible creature. Two large loop eyes like figure-8s,
> two outer rails rising like ears or horns, one tiny mouth. Minimal face,
> toy-like silhouette, friendly game-token stance. Front-facing, centered,
> plain background.

## Spend plan (ask first, prototype-only first)

Each concept = 6cr prototype (image). Build ONLY the approved one (30cr).
Suggested order: run 1–3 as prototypes (18cr), pick one, build once (30cr).

1. **oddy-vinyl-neutral** — "...matte vinyl designer-toy finish, cream and warm
   brown, neutral expression, studio lighting, product photo"
2. **oddy-clay** — "...hand-sculpted claymaquette look, visible thumbprint
   texture, soft daylight"
3. **oddy-wooden** — "...turned beechwood desk toy, visible grain, minimal paint
   on the eyes only"
4. **oddy-plush** — "...round plush doll, embroidered loop eyes, soft pile
   texture" (merch probe, not print)
5. **oddy-cheeky** — winner of 1–4 re-posed: "...one eye loop winking (lid
   half down), tiny smirk, dynamic slight tilt"
6. **oddy-blink-frames** — "...same creature, eyes closed (loops as lashes),
   for the blink frame" (pairs with neutral for the loader blink)
7. **oddy-sleepy** — "...nightcap, drooping loops, pastel stars" (empty-state art)
8. **oddy-surprised** — "...loops wide, tiny o mouth" (order-success moment)

## Expression system (post-concept, Blender-side)

Neutral + blink + happy + wink + sleepy + cheeky + surprised, built as
shape keys or mouth/eye swaps on the approved mesh — never new generations
per expression. Arms/feet stay optional nubs; squash & stretch carries motion.

## After approval

1. Prototype winner → build (30cr) → GLB to `data/3dprint/masters/oddy/`
2. Validate watertight (factory validate.py), measure, register adapter
3. Onboarding, empty states, stickers, social — Asset B goes to work
4. Loader storyboard (SVG etch → chip → coin → Oddy blink → logo) renders
   from the real assets, never placeholders
