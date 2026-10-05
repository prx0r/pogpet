# Pogtown Character Rig (spec, v1)

Template rigs only, validated binding only. We never blind-rig a random
Meshy mesh — a companion binds to this rig or it doesn't ship as a performer.
A Dot-shaped blob doesn't need a Mixamo skeleton; it needs squash, eyes, and
a mouth.

## Skeleton

```text
ROOT
├── BODY            squash/stretch, rotate, bounce
├── EYE_L / EYE_R   look targets, blink lids
├── MOUTH           open 0..1 (jawOpen morph or socket swap)
├── ARM_L/R         optional nubs (wave, hold, shrug)
└── LEG_L/R         optional nubs (bounce, march)
```

Missing limbs are fine — Oddy ships BODY + eyes + mouth only, and the actor
API never asks for what isn't there.

## Expression channels (shape keys or socket swaps, never new generations)

happy · excited · confused · thinking · sad · surprised · sleepy · talking ·
listening · working · celebrating

## Actor API (the only surface Pogtown programs against)

```text
actor.expression("thinking")
actor.lookAt(user)
actor.say(text)          # jawOpen envelope from audio
actor.gesture("explain")
actor.moveTo(shop)
actor.hold("gift_box")
```

## Mesh split (at generation time, not later)

- `avatar_performance.glb` — textures, rig, eyes, mouth, clips. Screen only:
  Pogtown, AR, cards, videos, live.
- `avatar_print/` — OBJ + STL + print manifest via
  `mesh_export.export_print_bundle` (watertight repair upstream of it).
  Attachments (jibbit stem, keyring loop, ornament hanger) join here.

## Rules

1. Blob-first: squash/stretch + eyes + mouth carries 90% of performances.
2. Humanoid limbs only when the mesh actually has them (validated at bind).
3. Expressions are data on the approved mesh, never re-generations.
4. Old rigs version; new bindings never rewrite shipped performers.
