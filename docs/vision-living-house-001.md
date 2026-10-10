# Living House 001 — first hardware specification (verbatim founder paste, 2026-10-10)

Miniature architectural object with voice + expressive interior lighting —
not a smart speaker in a fairy costume. Innovation = customisable shell +
standard electronics module + Pogtown SDK turning light/audio into a
resident. Shell changes; electronics + SDK stay compatible: the reusable
foundation for all future hardware.

## 1. Physical design: Jenny's Cottage

Exterior ~140 × 115 × 155 mm incl. roof (bedside scale; 100 mm version
later pending sound tests). Illusion chamber: hidden electronics, zone
lights, speaker cavity, replaceable windows. Separate zones (bedroom,
study, fireplace, door): reading → study glows; sleeping → upstairs
dims; speaking → warm flicker. Activity without mechanism.

## 2. Optical trick: layered windows, not holograms

Translucent inserts + independently controlled light + shadows; false
depth via curtains/silhouettes/reflective surface. Pepper's Ghost possible
later (alignment-sensitive, volume-hungry). JLC 8001 resin warns on
bubbles/texture → separately sourced diffusers or laser-cut acrylic for
optical surfaces, never raw printed resin. Prototype A/B/C: frosted
(simplest) → shadow theatre (preferred: silhouette + footsteps + voice
beats a cartoon face, preserves mystery) → hidden micro-display (future).

## 3. Prototype electronics: M5Stack Atom VoiceS3R ($14.50, currently out
of stock)

ESP32-S3 + mic + codec + amp + speaker + Wi-Fi + button, 24×24×16.8mm,
2× GPIO + 5V/GND expansion. Integrated 1W speaker OK for conversation
tests, NOT assumed good enough for premium bedtime — speaker/enclosure
acoustics get their own cycle. Integrated button = first push-to-talk
(needs exterior access).

Living House v1 BOM: VoiceS3R + 3–5 individually controlled RGB LEDs +
LED daughterboard/breakout + momentary front button + hardware mic mute +
frosted acrylic/diffuser + JLC3DP resin/nylon shell + black baffle frame
+ 5V USB-C + screws/inserts. Quote two versions — A: off-shelf module +
custom LED PCB (low risk); B: integrated ESP32-S3 board (mic, codec,
amp, button, LED drivers), assembled + tested (better economics later).
No unit pricing confirmed until manufacturing quotes.

## 4. Split manufacturing

JLC3DP: shell, roof, chassis, baffles, button. JLCPCB: LED daughterboard,
later full custom electronics. M5Stack/procurement: VoiceS3R + connector.
Shenzhen materials: grille, diffusers, wiring, screws. Shenzhen assembly:
install, light/audio test, firmware flash, pack. JLC minimums: 0.8mm SLA,
1.0mm SLS/MJF — design 1.5–2mm walls, extra at mounts.

## 5. Template standard (canonical day one)

Agents design exteriors; functional core is protected. Atlas/Meshy shape
→ Blender/build123d integrate mechanics. Contract: envelope
[140,115,155]; protected electronics cartridge, USB, mic port, speaker
chamber, button, service panel; lighting zones (bedroom/study/fireplace/
entrance); customisable roof/textures/windows/details/furniture/palette;
validation (clearance, thickness, speaker opening, light leakage, access,
thermal). Thousands of exteriors, one cartridge (lighthouse, mushroom,
library, observatory...).

## 6. Pogtown Home SDK (intent → bounded commands)

Jenny "going upstairs to read" → {activity, expression, location,
lighting_scene, soundscape} → gateway checks house capabilities →
home.setLight("study", ...)/playSound/setActivity. Agent never learns
whether it inhabits cottage, lighthouse or digital room.
Voice identity: voice_profile_id + speaking_style + modes (conversation,
storytelling, whisper, singing); runtime-managed, licensed/consented;
TTS for speech, separate pipeline for song. LiveKit ESP32 SDK starting
point (developer preview — validate before production).
Push-to-talk default: idle (mic dead) → hold (capture + bright window +
stream) → release (response + playback lighting). Separate physical mute,
honest capture LED. Offline-capable alarm: locally scheduled, persistent
clock; AI greeting optional enhancement.

## 7. First experiences

Knock (light to door + answer) · bedtime story (study on, dim-down read) ·
morning (gradual bright + alarm + greeting) · Pog visit (doorway/guest
lights, two voices) · working (workshop lit + digital progress) ·
sleeping (upstairs fade + offline) · magical message (window glow on
approved arrival) · digital pet (sounds + light imply movement).

## 8. Build sequence (4 builds, 1 acceptance test)

Design (3 exteriors → 1 + parametric cartridge) → optical (JLC shells +
inserts, light/shadow before voice) → voice (VoiceS3R + PTT + LEDs + one
Pogtown character) → manufacturing (exact BOM, revision, firmware,
assembly, QA for Shenzhen). Acceptance: press door → study lights →
Jenny answers → fairy tale → lights dim while reading. No AR/film/robot/
custom PCB needed for the demo. Thesis: OddHobb = beautiful homes for
digital inhabitants; Pogtown = inhabitants, voices, stories, activities.
Priority now: ONE validated electronics-and-optics cartridge, not more
house variations.
