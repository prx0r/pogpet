# Programmable physical products + procedural Pogtown avatars (verbatim founder paste, 2026-10-10)

## Reusable electronics core thesis

More defensible than individual 3D prints: a reusable electronics core
turning almost any customised 3D-printed object into an interactive
product. Standardise electronics, mounting, sensors, power, firmware;
customers/agents design compatible shells in Blender. Illuminated
trading-card stands this Christmas; expressive homes/bodies later on the
same infrastructure.

## Illuminated podium market (real demand)

- Lumint Onyx: 3D-printed translucent card holder, 16 colours, CAD $59.99
  — printed shell + simple electronics.
- AuraSlab: modular slabs, magnetic, 20 addressable LEDs/unit, auto module
  ID — the plug-together interface to study.
- Nanoleaf EXPO: stackable illuminated cases, app lighting, magnetic door
  sensing, smart-home — $239.99, larger scale.
Moat isn't backlighting: any compatible shape around one functional core
+ agent SDK controlling behaviour.

## OddHobb Cores (standardise)

Interchangeable shell (card holder, figurine podium, fairy house,
grimoire stand, agent habitat). Standard mounting/electrical interface
(dims, mounts, diffusers, cutouts, thermal). Core Light (RGB + USB);
Core Sense (ESP32 + touch/NFC/sensors); Core Voice (mic + speaker +
button); Pogtown Device SDK (lighting, presence, touch, voice, sensors,
agent events). Start: cheap off-the-shelf USB light module; Sense/Voice
as compatible replacements/expansions. Value compounds in stable
mechanical + software interfaces.

## Keenan Crane / GLSL avatars (unverified viral post — see note)

Post specifically unverified; found earlier shader work only (2022
graphics/simulation thread; complex-number GLSL visualisations). Reading
of the genre: procedural shader avatars (SDF + time + character params)
vs rigged GLB (bones/skin/blendshapes). Ghosts/blobs/orbs: procedural
excellent, rigging often unnecessary. Humans/clothing: rigging usually
still needed; guitar-playing: hybrid. Marching cubes/dual contouring can
convert SDF to printable polygon meshes (still needs manufacturing
validation). Recommendation: three avatar backends (procedural GLSL/WGSL,
rigged GLB, generated visual like Atlas/splats) behind one behaviour API
(look_at/speak/smile/walk/gesture/perform/sleep); agents never know which
body they have. Send the link/screenshot and the technique gets analysed
properly.

## Eight products on OddHobb Cores

1. GlowBase (figurines/brick characters/sculptures; RGB; future NFC scenes).
2. CardGlow (angled trading-card holder; sleeved/top-loaded/graded adapters).
3. MemoryLight (pet/portrait/name/location engraved acrylic; voice messages, AR).
4. Living House (cottage/tower/studio/agent home; RGB + voice module).
5. Ochema Ritual Stand (grimoire/brass/crystal platform; study sequences, narration).
6. Stonedoorway BreathStone (breathing rhythms; optional sensing/feedback).
7. Glimling Garden Habitat (moisture sensor + lighting; Pogtown gardener).
8. Pogtown Expression Core (LED eyes, speaker, 1–2 micro-servos; custom bodies later).

## Templates describe capabilities, not just geometry

Mechanical (mounts, enclosure, diffuser, fastening) + electrical (USB 5V,
capabilities) + optional modules + agent_permissions (allowed commands,
brightness caps, no strobe) + manufacturing (process, approved core,
validation required). Dimensions in versioned CAD, not inferred YAML.
Agents design within bounds; compiler checks fit/port access/diffuser/
thermal/assembly; JLC shells it, Shenzhen electronics supplier wires it,
consolidator boxes it.

## Moat

Verified hardware modules + reusable mechanical interfaces + agent control
SDK + manufacturability validation + Shenzhen fulfilment. Library of
known-compatible templates (pedestal, altar, habitat — one electronics
unit). Invest in the standard before bespoke robotics.

## Build now: GlowBase v1

USB light module + printed base + diffuser + replaceable top; exact
mechanical interface; two tops (figurine platform, trading-card holder).
v2: ESP32 exposing setColor/setBrightness/playAnimation/onTouch through a
Pogtown device gateway (no arbitrary agent code on controller). Then a
fairy-house shell on the same core. Then audio/sensors/screens/motors.
Progression: GlowBase → interactive display → expressive fairy house →
custom habitat → robot embodiment. GLSL avatars evolve independently of
the physical standard.
