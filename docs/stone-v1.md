# Stonedoorway Stone V1 — hardware design (envelope, not prototype)

Saved 2026-10-09. Living object, not consumer electronics: river
stone feel, deep internal light, pulse-not-notification haptics.
Teaches breath/touch/imagination/voice sync, then reduces dependence.
Beauty + satisfaction when OFF is a requirement, not a finish.

## Envelope (locked)

78 × 58 × 29 mm, 95–125 g target. Soft asymmetrical lentil: fuller
left edge, tapered end, curved underside. Holds: palm cradle,
two-hand, thumb across. Matte, slightly grippy, never rubbery or
sticky. No corners, no top controls, no speaker V1, no visible LEDs
at rest. USB-C prototype; dock later. Service cover off the contact
surface.

## Construction

Interchangeable silicone sleeve (eventual; print can't reproduce its
feel — separate industrial-design experiment) → translucent diffuser
shell (no LED points visible) → rigid nylon frame (PCB, haptics,
charging) → underside service cover. 8001 translucent resin for
optical prototypes (bubbles/texture/UV/53°C limits noted); dye
service (green/brown/black mineral looks) needs optical testing.

## Electronics (BLE-first, phone holds the brains)

nRF52840 (BLE + timing), DRV2605L + 10–12mm LRA on RIGID structure
coupled to palm surface (never suspended in silicone — test three
mounts blind: direct underside, frame-under-skin, isolated
anti-rattle), 6–8 addressable RGB in curved layout with temporal
smoothing (8 points can't flow; cheat with motion), hidden press
switch, optional accelerometer, USB-C V1 / 300–500mAh protected LiPo
V2 + dedicated charger IC. ESP32-S3 only for talking creatures.
Voice/AI on phone. Timestamped patterns execute locally (BLE
latency is real).

## Cue language

Breath (global field expand/contract), attention ribbon (independent
moving point), mantra (tactile punctuation), silence (dark + still
while practice continues). Phone app owns voice/mantra cadence.

## Limits (designed around, not through)

Diffusion (cavity + shell), flow illusion (layout + timing),
localisation (temporal codes now, second actuator later), audio
(phone), breath sensing (proxy only), battery (USB first), sweat
(sealed surfaces), resin finish (prototype ≠ final contact),
assembly (JLC makes parts; we assemble), compliance (electrical,
battery, radio, safety before sale).

## Costs (bench planning)

Shells $15–60, breadboard $35–100, custom PCB + enclosure $80–250,
battery unit $120–350+. Excludes shipping/assembly/availability.

## First builds (implemented)

Parametric enclosure: `scripts/parametric_stone.py` → three shells
(River/Worry/Seed) in the 78×58×29 envelope with common electronics
cavity + diffuser, STL out. Test seated 20–30 min, dry + damp hands,
before any custom PCB. Parametric CAD is the deliverable that makes
feel testable instead of debatable.
