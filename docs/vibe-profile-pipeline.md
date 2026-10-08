# Vibe-to-profile pipeline (spec — not yet built)

Decode vibe from images, video and voice into profile facts. Never ask;
observe. Stages run cheapest-first; each stage is optional and appends,
never overwrites, profile fields.

## Stage 0 — local heuristics (no keys, build first)

Per photo: palette histogram (3 dominant colors), brightness indoor/outdoor
heuristic, face count, text presence (signage), aspect/era markers. Per
account: setting distribution, palette signature, social density.
Writes: `profile.vibe.{palette, settings[], social}` + confidence 0.5.

## Stage 1 — omni-grade reading (needs DashScope key)

Qwen3.8-Omni-Flash over photos/voice notes/videos: scene description,
social context, register (goofy/posed/candid), energy, era markers.
Structured prompt returns fixed-schema JSON straight into
`profile.{interests, style, occasions[]}` with confidence 0.8+.
Voice notes: prosody → persona axis (warm/dry/chaotic) → caption voice.

## Stage 2 — video energy (needs DashScope key + ffmpeg, exists)

10s clips: movement pace, laughter timing, dominant speaker, music.
Writes `profile.energy` + occasion triggers (group event → birthday engine).

## Consumers (already live, waiting for data)

- `products_for(subject)`: interests/motifs rank lines.
- Card gallery headlines: occasion + relationship aware.
- `figg_creative_brief`: recipient facts in.
- Ledger: vibe tags join premise weights (which aesthetics convert).

## Rules

Profiles are append-only evidence with confidences; a human edit always
wins. Real people, real permission: vibe data never leaves the account,
never trains shared models. Stage 0 first; Stages 1–2 behind keys.
