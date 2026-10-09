# Stonedoorway thesis — the endgame (OddHobb flagships + cheap fillers)

Saved 2026-10-09. OddHobb stocks cheap fillers for volume and builds
its own flagship products for identity. Stonedoorway Stone V1 is the
first flagship: phone-held intelligence, physical sensation device.

## Architecture (shared core, many bodies)

Phone app (AI voice, meditation logic, live data, cloud) over BLE to
a shared electronics core: nRF52840-class BLE MCU, DRV2605L-class
haptic driver + LRA, 1–4 RGB LEDs, optional IMU, USB-C first
(rechargeable only after usage validates), JLC translucent-8001 shell
(>0.8mm walls; bubbles/texture possible; no heat/extended UV).
ESP32-S3 path only for standalone talking creatures (adds mics,
amps, speakers, firmware). Voice/AI/personalisation stay on the
phone; no always-listening hardware in V1.

## Cue language (the actual product)

Breath (inhale rise / pause hold / exhale fade), mantra (exact
cadence + count + cue sequence), focus (silence except agreed
intervals). Hardware must disappear into practice, not demand
attention. Input layer stays sensor-agnostic: stream → timestamped
observations → practice state → cue generator → hardware. EEG
(Muse/OpenBCI via BrainFlow) becomes a data source later, with
labelled uncertainty — scalp signals never claim thoughts, states,
or energy locations.

## Staged sensing (honest)

V1 open-loop (timed cues, no sensors). V2 watch/HR via HealthKit /
Health Connect (stored records ≠ live breath streams). V3 EEG
experiments. V4 adaptive guidance from measurements + explicit
feedback + validated prefs.

## Device ladder

Stone V1 (palm, pulse + light + tap, USB prototype first) → NFC
amulet (passive, no battery) → desk companion (BLE + behaviour) →
wearable (validated sensors only) → kinetic instrument (motors,
bearings — hardest, last). Common firmware/protocol/identity
system throughout; unique IDs per object (PCB QR/serials).

## Costs (bench planning, not quotes)

Dev board $10–25, haptics $5–20, LEDs $2–10, USB shell $5–20,
accessories $5–15 → first bench $27–90. Custom PCB + battery later.
JLCPCB assembly ($8 setup) helps at small batch. Sales need
electrical/battery/radio/safety compliance — JLC manufactures, never
certifies end to end.

## Catalog rule (implemented)

Every line carries tier flagship/filler. Fillers = volume
(accessories, charms, game bits). Flagships = identity (Stone,
Alive kits, NFC amulets). Stone enters as concept (not orderable)
until bench prototype validates the experience.
