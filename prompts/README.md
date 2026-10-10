# Prompt library — transformations, not generations

Each file is one reusable tasteful transformation: a categorised face (or
graphic) in, a styled variant out, via reference image-to-image (fal.ai or
Alibaba satisfy the capability — recipes never name providers).

Contract per prompt file:
- `id`: `area/name-vN` (matches recipe `prompt_id`), stored at
  `prompts/area/name-vN.md`
- `capability`: the named capability it satisfies
- `input`: what it takes (face cutout, graphic, …)
- `prompt`: the exact transformation text
- `negative`: what must never appear (extra text, extra faces, …)
- `output`: size/aspect/alpha expectations the renderer relies on

Recipes reference prompts by id + version. Prompts are versioned and
immutable like recipes: fix by shipping v2. Final customer edits ("brown
paper") are image-edit calls against the generated graphic, spending
OddHobb credits — same library, `edit` method.
