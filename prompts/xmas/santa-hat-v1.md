# xmas/santa-hat-v1

- `id`: `xmas/santa-hat-v1`
- `capability`: `face_styled_variant`
- `method`: reference image-to-image
- `input`: categorised face cutout (square, subject centred, transparent or plain background)

## prompt

> Keep this exact pet's likeness, face shape and expression. Put a
> classic red Santa hat on their head at a jaunty angle, fluffy white trim
> and pom-pom. Clean studio-lit portrait style, soft festive warmth,
> plain background, no other animals.

## negative

Extra animals, extra hats, text, letters, watermarks, distorted features,
different pet, photorealistic fur texture change.

## output

- Square portrait, subject head + hat with margin for tile bleed.
- Likeness preserved: same eyes, nose, mouth geometry as the reference.
- Used by: transform `pet_santa_v1`, recipe `wrap_pet_santa_repeat_v1` (motif), future card/graphic recipes.
