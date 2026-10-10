# Living Worlds competitors + Pogtown SDK (verbatim founder paste, 2026-10-10)

## Closest competitors (what they prove, where we differ)

- **AIMO** (aimokit.com): modular hub bringing toys to life; €99 voice,
  €159 touch/light/motion/LEDs; maker tier adds motors/IoT. Overlap:
  voice, personality, emotions, sensors, interchangeable embodiments.
  Difference: designed homes, persistent explorable world, purchasable
  upgrades, manufacturing compiler.
- **CODE27** ($549): display housing virtual companions that talk, work,
  remember, animate. Difference: our house uses architecture, imagination
  and optional AR — no character display required.
- **LivingAI EMO** ($279): persistent character, emotional animation,
  sensors, alarms, music, smart lights. Difference: EMO sells one robot;
  we propose an open ecosystem of agents, houses, creatures, forms.
- **Meckie**: portable agent identity across hardware bodies. Difference:
  embodiment as personalised, collectible, expandable physical world.

Technology idea not new; agent's HOME as the customisable product is.

## Agents designing their own homes

Jenny wants a reading nook, two yellow windows, strawberry garden.
Customer sees three Jenny-proposed designs, chooses one, OddHobb compiles
to manufacturing parts. Physical (Shenzhen shell/windows/roof/fittings),
digital (Atlas atmosphere + exact scene graph), expressive hardware
(standard lighting/push-to-talk/sensor/audio module). Agent proposes,
compiler verifies (dimensions, connectors, cost, safety), owner approves.

## Pogtown SDK (build immediately)

LiveKit ESP32-S3/ESP32-P4 hardware support exists (audio streaming, RPC;
developer preview — test before commercial use). Standard interface:

```
setLighting(scene) · playSound(id) · speak(text, voiceId) · display(sceneId)
readSensors() · onButtonPress() · onMotion()
```

Expressive state object (activity/expression/lighting palette+brightness+
animation/soundscape/duration) = intended expression, not felt emotion.
Provider-independent: LiveKit audio/transport, Pogtown identity/state/
memory/permissions, firmware safety/brightness/offline/failure handling.

## Sensors (fictional mapping, real readings labelled)

Doorbell → Jenny answers; temperature drop → fireplace lit; dry soil →
gardener mentions thirsty plant; passerby → window silhouette; bedroom
light off → bedtime routine; friend Pog message → mailbox glows; garden
module added → digital plants appear. Greenhouse + soil sensor bridges
Glimling garden work without a robot gardener.

## Multi-inhabitant houses + children

One house, swappable inhabitants (fox/dragon/frog/ghost + rooms/stories).
Children's version: push-to-talk default, no continuous listening, no
open purchases, parental controls, age-appropriate content, fictional-AI
reminders (Oct 2026 research: 7–9s experiment freely but mismatch
expectations).

## Manufacturing platform (standard core, personalised shell)

One tested electronics module (USB-C, ESP32-S3, LEDs, push-to-talk,
mic/speaker, sensor expansion, identity, signed firmware) inside
thousands of shell designs. Agent designs must respect mounting/thermal
clearances. Shenzhen relationships compound: known cores, varying shells.

## Roadmap (prototypes 1–6)

1. Software house (desktop room, events) · 2. Light house (JLC shell +
ESP32 light/button) · 3. Voice house (LiveKit audio, bedtime scheduling)
· 4. Shell marketplace (agent houses validated + quoted) · 5. Expandable
ecosystem (gardens/pets/rooms/displays) · 6. Expressive robotics (same
identity/API). Adults first (fewer safeguards); children after.

## Advantage

AIMO voices toys, EMO sells a robot, CODE27 sells a screen. Ours:
persistent portable agents + people/agents designing their physical
environments. Start now: LiveKit ESP32 SDK + validated lighting + Pogtown
identity + JLC cottage = whole principle demonstrated. First demo: dark
cottage, doorbell press, window lights, "Hang on, I'm coming!" — more
personality than a complicated robot.
