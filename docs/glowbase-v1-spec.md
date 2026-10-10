# GlowBase v1 spec — backlit podium platform (2026-10-10)

Status: SPEC (not quoted, not prototyped). Goal: the composable bread and
butter — one core, swappable tops (figurine platform, card holder,
cottage shell later). science: same electronics + interface everywhere.

## Shell (Meshy/Atlas → parametric mount)

- Source: Meshy AI concept sculpt OR Atlas-generated room/object view as
  visual reference. Either way, rebuild the mount zone in parametric CAD
  (build123d): core cavity, diffuser seat, USB-C cutout, top interface
  ring. Never print raw generative mesh for the mount.
- Tops v1: (a) figurine platform 80mm disc, (b) trading-card holder
  angled 70° with 63×88mm sleeved slot. Both key to the same ring.
- Diffuser: required, translucent (natural PLA/PETG ≥1.2mm or acrylic).
- Fixed interfaces (frozen v1): cavity 56×56×22mm, ring Ø64mm, USB-C
  aperture 12×6mm rear, vent slots ≥8cm², wall ≥2mm, M3 brass inserts ×4.

## Electronics BOM (JLC-orderable, USB-first, no battery v1)

| Part | Spec | Source |
|---|---|---|
| Controller | ESP32-S3 dev module (USB-C, Wi-Fi) | JLCPCB assembly or Seeed |
| Light | Addressable RGB strip/ring, 8–12 LED, 5V | 1688/Seeed, diffuser-matched |
| Button | Tactile 6×6mm, front panel (push-to-talk) | LCSC |
| Power | USB-C 5V in, no cell (v1 rule) | cable off-the-shelf |
| Optional v2 | mic + speaker + NFC reader | M5Stack-class modules |

Button behavior (always-on solved): idle dim → press latches listening,
light goes solid → release or 8s timeout returns to ambient. No
continuous mic: push-to-talk only, hardware mute trace on PCB.

## Agent template bounds (publish for Pogtown designers)

- Envelope: Ø110 × 70mm max; keep-out above cavity + vents.
- Mounts: ring Ø64 + 4×M3 pattern (positions in CAD, not prose).
- Thermal: 5W max inside shell; diffuser gap ≥3mm from LEDs.
- Power: USB-C rear only; no batteries without re-validation.
- SDK: setColor/setBrightness/playAnimation/onTouch (+ speak/listen on
  Voice) via device gateway; brightness cap 0.8, strobes disabled.
- Validation: fit check, port access, diffuser coverage, assembly order,
  costed BOM — compiler gates before manufacture.

## Voice per agent (the value-add)

Resident voice = server-side TTS voice ID bound to the object record;
fairytales/stories served as audio + booklet text. Voice picker at
onboarding (resident select → voice), editable later. Pog housing: invite
places a message in the room queue; room light cues on arrival.

## Validation checklist (before manufacture)

Fit ✓ · port access ✓ · diffuser ✓ · assembly order ✓ · BOM costed ✓ ·
button behavior ✓ · brightness cap ✓ · beauty shot + AR anchor ✓.
Then: JLC shell quote → electronics kit quote → consolidation pack →
presale.
