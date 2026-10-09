# Stone breath sensing — vision (nasal phase + airflow)

Saved 2026-10-09 (founder vision, lightly cleaned). Factory mapping:
`docs/factory-breath-sensor.md` (what the factory can make vs procure).
Related: `docs/stone-portal-optics.md`, `docs/stonedoorway-thesis.md`.

Breathing phase (inhale/exhale/pause timing + rhythm) is established
technology; the challenge is small, comfortable, unobtrusive sensing that
pairs with the Stone. A tiny nose-mounted sensor is genuinely promising.

Two signals: **phase** (when + shape + rhythm — what art needs) and
**airflow** (rate/volume — for advanced pranayama, left/right-nostril work).

## Six approaches

1. **Nasal thermistor** (first nose prototype): temp sensor under nostrils,
   exhale warmer than inhale. Proven monitoring; measures temperature, not
   airflow; placement + response speed matter.
2. **Nasal pressure cannula** (best airflow waveform): sleep-study standard,
   sensitive breath-by-breath waves; pressure ≠ calibrated volume.
3. **Chest/abdomen belt** (best unobstructed sensing): inductance
   plethysmography, well established; volume needs calibration.
4. **Thermal airflow sensor** (best micro-wearable experiment): heated
   element, demonstrated left/right-nostril resolution at ~60mW (research
   feasibility, not a product).
5. **Flowmeter mouthpiece** (quantitative reference): calibrated
   pneumotachograph for validating prototypes, not daily wear. Sensirion
   makes calibrated flow sensors; most respiratory models are too large
   for a nose clip.
6. **Chest motion patch** (convenient, indirect): IMU on chest; easy to
   wear, vulnerable to motion/posture.

## The nose bridge concept

Not a clip that squeezes nostrils shut: a miniature removable bridge with
two sensing tips just below the nostrils, electronics carried somewhere
comfortable. Independent L/R channels unlock nostril-asymmetry observation
(published precedent: independent nasal pressure channels over time) —
phase + duration, L/R activity, transitions, smoothness, relative flow
strength with calibration. A companion to Swara Yoga / nostril-awareness
practice, without metaphysical claims. Mouth breathing is out of scope
for a nose device — flag the uncertainty.

## Build order

A: two fast NTC thermistors + MCU — can we track per-nostril phase
comfortably? B: cannula + pressure transducer — how much better is the
waveform? Run A and B in parallel; C (micro calorimetric) only if A/B
justify it.

## Stone response

Nasal sensor → L/R waveforms → breathing engine (phase, amplitude,
asymmetry, confidence) → Stone light + haptics, computed on-device over
Bluetooth (no cloud latency). E.g. left inhale → blue current grows left;
right inhale → gold right; exhale → currents descend and dissolve; steady
breathing → coherent flow pattern. Later: interchangeable sensor modules
(belt, pulse, EMG, EEG) on one experience engine. Rule: the light follows
the user — instrument, not timer. Belt stays the accuracy benchmark;
validate timing before miniaturising.
