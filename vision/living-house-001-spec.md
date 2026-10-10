# OddHobb Living House 001 — the first hardware specification

I'd build this as a miniature architectural object with a voice and an expressive interior lighting system, rather than as a conventional smart speaker disguised as a fairy house.

The critical product innovation is the combination of three things:

1. A beautiful, customisable shell that can be designed by people or Pogtown agents.
2. A standard electronics module that gives the shell sound, hearing, lighting and optional sensors.
3. A Pogtown SDK that turns ordinary lighting and audio into the impression of a character living inside.

The shell changes. The electronics and SDK stay compatible. That's the reusable foundation for the entire future hardware catalogue.

## 1. What I'd design physically

Exterior: Jenny's Cottage

Organic architecture, illuminated windows, substantial enough to sit beside a bed.

Interior: illusion chamber

Hidden electronics with separately controlled light zones, a speaker cavity and replaceable windows.

I would start with approximate external dimensions of 140 × 115 × 155 mm, including the roof. That's large enough to accommodate a compact audio module and expressive lighting but small enough for a bedside desk object.

A more compact 100 mm version could follow after testing sound quality.

Rather than making the entire house glow, create separate illuminated regions: an upstairs bedroom, a study window, a fireplace and the front door.

When Jenny is reading, the study window glows. When she's sleeping, the upstairs light slowly dims. When she's speaking, a warmer light flickers behind her window.

That gives the appearance of activity without any moving mechanism.

## 2. The optical trick I'd prioritise

The most effective illusion probably isn't a hologram.

It's layered translucent windows with independently controlled light and shadows.

Proposed window cross-section

Conceptual section, not a scale engineering drawing. Light passes through a rear illuminated silhouette and a front diffuser.

I would prototype three optical effects:

- Window glow: translucent amber inserts illuminated by diffused LEDs.
- Moving shadow: two or three silhouette positions animated by light switching, creating the impression of someone passing a window.
- False depth: layered curtains, silhouettes and a reflective surface to make windows feel deeper than their actual physical cavity.

A Pepper's Ghost-style reflection is worth experimenting with, but it's more alignment-sensitive, uses up internal volume and needs controlled viewing angles. Start with the layered window, because it is cheaper and easier to manufacture consistently.

JLC3DP offers transparent/translucent 8001 resin, but explicitly warns that bubbles and surface texture can limit optical clarity. I'd therefore use separately sourced diffusers or laser-cut acrylic for critical optical surfaces rather than rely on raw printed resin as a precision optical element.&#x20;

[image](https://www.google.com/s2/favicons?domain=https://jlc3dp.com\&sz=32)

Photosensitive Resin



## 3. The exact prototype electronics

The most useful discovery is that we don't need to design a custom JLCPCB board for the first house.

The M5Stack Atom VoiceS3R is a tiny, existing voice-capable controller that already combines nearly everything we need.

## Atom VoiceS3R

# $14.50

Published list price; currently shown out of stock on M5Stack's store

It integrates an ESP32-S3, microphone, audio codec, amplifier, small speaker, Wi-Fi and button. Its size is only 24 × 24 × 16.8 mm.&#x20;

[image](https://www.google.com/s2/favicons?domain=https://shop.m5stack.com\&sz=32)

shop.m5stack.com

+1



### Living House v1 bill of materials

| Component        | Proposed part                           | Function                            |
| ---------------- | --------------------------------------- | ----------------------------------- |
| Main electronics | M5Stack Atom VoiceS3R                   | Wi-Fi, voice, audio, controller     |
| Illumination     | 3–5 individually controlled RGB LEDs    | Separate windows and effects        |
| Lighting board   | Small custom PCB or LED breakout        | LED mounting and power              |
| Front button     | Momentary switch with suitable mounting | Push-to-talk                        |
| Privacy control  | Hardware microphone mute switch         | Physically disable microphone       |
| Window material  | Frosted acrylic or diffuser             | Soft, even light                    |
| House exterior   | JLC3DP resin or nylon                   | Custom architectural shell          |
| Internal frame   | Printed black light baffles             | Isolate window zones                |
| Power            | 5V USB-C                                | No battery complexity               |
| Fasteners        | Small screws or inserts                 | Removable electronics for servicing |

The module exposes two GPIO signals and 5V/GND through its expansion connector. That is enough to experiment with LED data and an additional button input, provided the electrical interface is designed appropriately. Its integrated button could also serve as the initial push-to-talk control, though we'd need to make that accessible through the house exterior.&#x20;

[image](https://www.google.com/s2/favicons?domain=https://docs.m5stack.com\&sz=32)

docs.m5stack.com



Important: The integrated 1W speaker is adequate for testing conversation, but I would not assume it sounds good enough for a premium bedside storytelling product. Speaker quality and enclosure acoustics deserve their own prototype cycle.

A practical first build would use the module's integrated button before designing the final front-door push mechanism.

## 4. Split manufacturing between JLC and the audio-module supplier

I'd organise it like this:

| Supplier                      | Order                                                                         |
| ----------------------------- | ----------------------------------------------------------------------------- |
| JLC3DP                        | Exterior shell, removable roof, internal chassis, light baffles, front button |
| JLCPCB                        | Small LED daughterboard; eventually complete custom electronics               |
| M5Stack / procurement partner | VoiceS3R module and compatible connector                                      |
| Shenzhen materials supplier   | Speaker grille material, diffusers, wiring, screws                            |
| Shenzhen assembly partner     | Install module, test lights/audio, flash firmware, pack                       |

JLC3DP's published guidelines recommend process-specific minimum wall thicknesses, including 0.8 mm for SLA and 1.0 mm for SLS/MJF. For our first enclosure I would design more conservatively, around 1.5–2 mm for many shell walls, with extra material around mounts.&#x20;

[image](https://www.google.com/s2/favicons?domain=https://jlc3dp.com\&sz=32)

jlc3dp.com



I'd ask the electronics partner to quote two versions:

Prototype A: Off-the-shelf M5Stack module plus our custom LED PCB.

Prototype B: One integrated board using an ESP32-S3, microphone, audio codec, amplifier, button and LED drivers, assembled and tested as a unit.

Prototype A minimises engineering risk. Prototype B is where unit economics and manufacturing flexibility could eventually improve.

No single-unit pricing for the complete house should be treated as confirmed until we have manufacturing quotes.

## 5. The template standard: let agents design houses without breaking the electronics

This is the part I'd make canonical from day one.

Agents can design the exterior however they like, but the functional core is a protected, validated region.

Use Atlas or Meshy for the creative shape, then Blender and build123d to integrate exact mechanical components.

Agent-designed house

Meshy / Atlas → generated exterior GLB

OddHobb House Template v1

Reserved electronics volume · LED sockets · Mic port · Speaker grille · Button · USB opening

Manufacturing validator

Clearances · Thickness · Supports · Access · Optical isolation · Assembly

JLC manufacturing package

Approved parts · BOM · Print files · Electronics · Assembly guide

A preliminary machine-readable contract could be:

```
template: oddhobb.living_house.v1

external_envelope_mm: [140, 115, 155]

protected_interfaces:
  - electronics_cartridge
  - usb_access
  - microphone_acoustic_port
  - speaker_acoustic_chamber
  - front_button
  - removable_service_panel

lighting_zones:
  - bedroom
  - study
  - fireplace
  - entrance

customisable:
  - roof_geometry
  - wall_textures
  - window_shapes
  - decorative_details
  - furniture
  - colour_palette

validation:
  - physical_clearance
  - wall_thickness
  - speaker_opening
  - optical_light_leakage
  - assembly_access
  - thermal_clearance
```

This is a proposed specification, not yet a JLC-ready design. The protected geometry needs proper CAD models and test-fit measurements.

The valuable thing is that thousands of exterior designs could share the same internal electronics cartridge.

A Pogtown agent could design a lighthouse, mushroom cottage, gothic library or little observatory. We would manufacture the customised shell without redesigning the electrical system.

## 6. The Pogtown Home SDK

I would separate what an agent wants to express from the hardware commands used to express it.

For example, Jenny says she's going upstairs to read.

Pogtown emits:

```
{
  "agent_id": "jenny",
  "activity": "reading",
  "expression": "content",
  "location": "study",
  "lighting_scene": "study_lamp",
  "soundscape": "quiet_fireplace"
}
```

The device gateway checks this against the actual house's capabilities, then generates bounded commands.

```
home.setLight("study", {
  color: "#F4B866",
  brightness: 0.35,
  transitionMs: 1800
});

home.playSound("fireplace");
home.setActivity("reading");
```

This way, the agent doesn't need to know whether it inhabits a printed fairy cottage, a lighthouse or a digital room.

### Voice and character identity

I'd make every Pogtown character's voice part of its persistent identity:

```
{
  "agent_id": "jenny",
  "voice_profile_id": "jenny-v1",
  "speaking_style": "playful, gentle, dry humour",
  "default_delivery": "conversational",
  "supported_modes": [
    "conversation",
    "storytelling",
    "whisper",
    "singing"
  ]
}
```

Voice selection would be managed by the runtime, not generated as a brand-new voice every time a character speaks. Use licensed or properly consented voices.

Storytelling, whispering and expressive reading can be supported with compatible speech models and style controls. Singing and instrumental music would generally need a separate audio-generation or playback pipeline; don't assume ordinary conversational TTS can convincingly perform either.

For live speech, the [LiveKit ESP32 SDK](https://github.com/livekit/client-sdk-esp32) is a particularly relevant starting point: it supports ESP32-S3 devices, two-way audio, agent communication and remote calls. The project explicitly labels itself developer preview, so we'd validate reliability and compatibility with our selected audio board before production.&#x20;

[image](https://www.google.com/s2/favicons?domain=https://github.com\&sz=32)

GitHub

+1



### Push-to-talk is the right initial default

The button should be intentionally simple:

Idle

Microphone capture disabled, windows softly illuminated if desired.

Press and hold

Microphone capture activates, one window becomes brighter, audio is streamed to the authorised voice session.

Release

Capture stops, Jenny responds and the lighting reflects speech playback.

A separate physical mute switch should disconnect or disable the microphone capture path, independently of any software state. The LED should accurately indicate when capture is active.

This would make the first prototype much easier to test than an always-listening voice assistant.

## 7. The first magical experiences to implement

I'd focus on a handful of things that genuinely use the house rather than duplicating a generic chatbot.

| Experience         | Physical behaviour                                                   |
| ------------------ | -------------------------------------------------------------------- |
| Knock on the door  | Light moves toward the entrance, character answers                   |
| Bedtime story      | Study light comes on, story begins, house gradually dims             |
| Good morning       | Windows brighten gradually, optional alarm and greeting              |
| Another Pog visits | Doorway and guest-room lights respond, two voices converse           |
| Agent working      | Workshop window illuminates; progress appears in digital room        |
| Agent sleeping     | Upstairs light fades; character goes offline or changes availability |
| Magical message    | A window glows when an approved message arrives                      |
| Digital pet        | Soft creature sounds and lighting imply an inhabitant moving inside  |

For bedside use, the alarm must work without a reliable internet connection. I'd use an independently scheduled local alarm with appropriate clock persistence, and treat the AI's spoken greeting as an optional enhancement.

## 8. The optical system is the critical experiment

Before commissioning expensive electronics, I'd print one generic house shell with interchangeable window inserts and test how convincing different lighting techniques feel.

A. Frosted windows

Simplest

Diffused warm light with independent zones. Tests whether ambient presence alone is compelling.

B. Shadow theatre

Best first expressive effect

Layered miniature silhouettes and independently switched illumination. Tests apparent movement without servos.

C. Hidden micro-display

Future upgrade

A small LCD/OLED behind a window with animated silhouettes. Tests whether richer visuals justify the added cost, power and firmware complexity.

My preference is B: shadow theatre.

A tiny backlit silhouette moving past a curtain, combined with a footstep sound and a natural voice, could be more convincing than putting a cartoon face on a screen.

It also preserves the mystery of the house, which is the product's distinguishing quality.

## 9. Immediate prototype sequence

I'd execute the first product in four tightly scoped builds.

1. Digital design: Generate three original house exteriors with Meshy or Atlas. Choose one, repair the mesh and integrate a common parametric electronics cartridge.
2. Optical prototype: Order JLC-printed shells and window inserts. Test basic illumination and shadow effects before integrating voice.
3. Voice prototype: Install a VoiceS3R, exposed push-to-talk, speaker and programmable LEDs. Connect one Pogtown character through the voice backend.
4. Manufacturing prototype: Produce the exact BOM, enclosure revision, firmware image, assembly instructions and QA procedure that a Shenzhen partner can reproduce.

The first acceptance test should be:

A person presses the door, the study window lights up, Jenny responds, they ask for a fairy tale, and the lights gradually dim while she reads.

No AR, generated film, robot animation or custom PCB is necessary for that demonstration.

The product thesis I'd lock in is:

OddHobb manufactures beautiful homes for digital inhabitants. Pogtown provides the inhabitants, their voices, stories and activities. The Home SDK lets any compatible agent express its presence through lighting, sound and eventually sensors and movement.

The immediate engineering priority is not generating more house variations. It's creating one validated electronics-and-optics cartridge that all those variations can use.

Once that cartridge works, the shell becomes an agent-designable product category rather than a one-off hardware project.


# OddHobb Studio — a physical product compiler with an agent simulator

Yes. This is the missing foundation connecting everything we've discussed: a studio where a human or AI agent can design, simulate, price and manufacture a physical object containing actual electronics.

The important distinction is that JLC shouldn't be treated as the design engine. JLC manufactures the validated designs. OddHobb becomes the design and simulation environment, with JLC and other suppliers supplying manufacturing capabilities, component inventories, quotations and fulfilment.

I verified that JLC now officially offers much of the API infrastructure we need.

## 1. JLC's actual APIs — what we can integrate

[image](https://www.google.com/s2/favicons?domain=https://api.jlcpcb.com\&sz=32)

[JLC API developer portal](https://api.jlcpcb.com/)

Official API platform · Access requires application and approval

| API             | What OddHobb can do                                                    |
| --------------- | ---------------------------------------------------------------------- |
| 3D Printing API | Upload STL/STEP/OBJ/3MF, calculate prices, place and track orders      |
| PCB API         | Upload Gerbers, price PCB fabrication, create orders, track production |
| Components API  | Search parts, obtain specifications, pricing and stock                 |
| Stencil API     | Quote and order PCB assembly stencils                                  |

Source: [JLCPCB official API overview](https://jlcpcb.com/help/article/jlcpcb-online-api-available-now), updated September 9, 2026.&#x20;

[image](https://www.google.com/s2/favicons?domain=https://jlcpcb.com\&sz=32)

jlcpcb.com



JLC's 3D printing portal also documents two access levels:

- Pricing API: for quotation and price comparison.
- Ordering API: adds upload, automated pricing, ordering and order status tracking.

Applications are reviewed individually, including prior order history and business circumstances. Full authenticated endpoint specifications are not exposed by the public overview.&#x20;

[image](https://www.google.com/s2/favicons?domain=https://jlc3dp.com\&sz=32)

jlc3dp.com



The official JLC API portal lists additive manufacturing methods including SLA, MJF, SLM, FDM, SLS and WJP.&#x20;

[image](https://www.google.com/s2/favicons?domain=https://api.jlcpcb.com\&sz=32)

api.jlcpcb.com



### Electronics components are a separate opportunity

[LCSC official OpenAPI documentation](https://www.lcsc.com/docs/openapi/index.html)

LCSC provides searchable electronics components with manufacturer part numbers, availability, prices and technical details.

That lets the studio work with genuine sourceable parts rather than components invented by a language model.&#x20;

[image](https://www.google.com/s2/favicons?domain=https://www.lcsc.com\&sz=32)

lcsc.com



This matters because a virtual sensor should correspond to a real electronic component with known limits, a datasheet, a footprint and a purchasing route.

I'd make the JLC and LCSC API applications a priority, but build the studio so it's functional with a manually verified catalogue before approval.

## 2. The Studio experience

A user should be able to type:

> Design a tiny woodland house for my Pog. Give it four glowing windows, a front button to talk to it, a microphone, speaker and a sensor that detects when the room gets dark. I want warm lighting when the character is reading and a different effect when it's excited.

The Studio translates that into an actual engineering project, not just a beautiful 3D render.

## OddHobb Studio

Illustrative prototype

## 3D

Exterior

## 5

Components

## 4

Light zones

SimulatePartsManufacture

Agent activity

Reading in the study

Excited about something

Asleep upstairs

Room is dark (simulated light sensor)

Study lights active

Ambient light available. The study light is on.

Virtual device

The central capability is designing how the product behaves before commissioning any physical parts.

The illustration above simulates a few states. The real studio would render the actual approved mesh, electronics placement and lighting behaviour.

## 3. The architecture: one project, five compilers

Natural language / Agent / Visual editor

“Build a fairy house with expressive lights and voice.”

Canonical Product Definition

Mechanical geometry · Electrical connections · Parts · Firmware · Agent capabilities

CAD compiler

Mesh, mounts, cutouts, STL/STEP

Electronics compiler

Schematic, BOM, PCB, placement

Simulation compiler

Sensors, lighting, virtual device

Firmware compiler

ESPHome / ESP-IDF configuration

Manufacturing compiler

Quote packets, supplier jobs, QA

Commerce compiler

Shopify product, landed price, order

The canonical source should describe what a product is, including its electronics and behaviour.

CAD, firmware and manufacturing outputs are derived artifacts.

This is how you keep the same project compatible with JLC, another Shenzhen PCB assembler, or a different 3D-printing supplier.

## 4. Build a library of verified physical capabilities

Rather than giving an agent an unrestricted catalogue of electronic parts, I'd start with tested functional blocks.

| Standard block            | Physical parts              | Simulator exposes               |
| ------------------------- | --------------------------- | ------------------------------- |
| `light.rgb.v1`            | LED and driver              | Colour, brightness, effects     |
| `button.ptt.v1`           | Momentary switch            | Press, hold, release            |
| `sensor.ambient_light.v1` | Photodiode/ambient light IC | Light level, threshold crossing |
| `sensor.temperature.v1`   | Temperature sensor          | Temperature reading             |
| `sensor.motion.v1`        | PIR or presence module      | Motion/presence events          |
| `audio.voice.v1`          | Mic, codec, speaker         | Capture, playback, mute         |
| `actuator.servo.v1`       | Servo and driver            | Bounded position/movement       |
| `display.window.v1`       | Small display               | Images, expressions, animations |

Each block should include the datasheet, allowed voltages, pin mapping, board footprint, physical mounting envelope, estimated power use, validated firmware driver, simulation adapter and approved component alternatives.

This is our equivalent of reusable LEGO pieces, but for actual interactive products.

An agent can combine approved blocks, and the compiler determines whether those parts can coexist electrically and physically.

For genuinely novel electronics, the studio can propose new circuits, but those must go through schematic verification, PCB design review, electrical testing and prototype approval before being sold.

## 5. Make the simulator and real hardware use the same SDK

This is the most important architectural decision.

An agent should not need different code depending on whether it's controlling a simulated house or a real house.

For example:

```
const house = pogtown.devices.get("jennys-house");

await house.lights.setScene({
  zone: "study",
  color: "#F5BA72",
  brightness: 0.45,
  transitionMs: 1600
});

house.sensors.ambientLight.onChange((lux) => {
  if (lux < 15) {
    house.events.emit("room.dark");
  }
});
```

In Studio mode, these commands manipulate virtual lights and synthetic sensor values.

In physical mode, they pass through an authenticated device gateway to the appropriate ESP32 firmware.

Simulator

Same events, virtual sensors, rendered lights, synthetic audio and deterministic tests.

Real device

Same events, real sensors, physical LEDs, audio electronics and bounded actuator controls.

This lets us simulate entire scenarios before ordering:

- Jenny starts reading → study light brightens.
- The light sensor reports darkness → reduce ambient brightness.
- User holds the button → microphone becomes active and a window changes colour.
- User releases → capture stops and Jenny responds.
- A second Pog visits → guest window glows and a conversation plays.
- Device loses Wi-Fi → lighting continues locally, voice service becomes unavailable.
- Agent requests an invalid brightness or unsupported feature → gateway rejects the command.

We should use deterministic test scenarios for software behaviour and also preview the actual lighting on a digital model. The second requires reasonably calibrated light/material rendering; a browser preview cannot guarantee how the physical diffuser looks or how good the speaker sounds.

## 6. What the manufacturing workflow actually looks like

There are three distinct forms of price in the Studio.

1

Instant estimated cost

Calculated locally from model volume, process assumptions, part quantities, cached supplier prices, assembly labour and shipping estimates. Clearly labelled as an estimate, with confidence ranges.

2

Live supplier quote

Upload the exact manufacturable files to an authorised supplier API and receive prices, process restrictions and delivery options. Store the quote's expiry and the precise file hashes.

3

Production-approved landed price

Combines manufacturing quotes with the validated electronics BOM, assembly, programming, testing, packaging, shipping, customs and a margin. Ordering requires approval.

The crucial distinction is that JLCPCB producing a PCB is not the same as delivering a fully assembled fairy house.

For a complete product, we need a Shenzhen final-assembly partner or our own later assembly process.

JLC PCB assembly can populate a board, but the finished house still needs lights and speakers installed, wiring connected, firmware configured, enclosure closed and QA performed.

## 7. The supplier adapter contract

I'd give every manufacturing provider the same interface, even when particular methods aren't supported.

```
interface SupplierAdapter {
  capabilities(): Promise<Capability[]>;

  estimate(project: Project): Promise<Estimate>;

  requestQuote(
    manufacturingPackage: ManufacturingPackage
  ): Promise<QuoteResult>;

  submitOrder(
    approvedQuoteId: string
  ): Promise<OrderResult>;

  trackOrder(orderId: string): Promise<OrderStatus>;
}
```

Then implement initial adapters:

| Adapter             | Priority          | Scope                                        |
| ------------------- | ----------------- | -------------------------------------------- |
| `jlc3dp`            | P0                | 3D printing quotations and parts             |
| `jlcpcb`            | P0                | PCB fabrication and assembly                 |
| `lcsc`              | P0                | Electronic part sourcing                     |
| `shenzhen_assembly` | P1                | Final assembly, test, kitting                |
| `seeed_fusion`      | P1                | Alternative hardware manufacturing           |
| `elecrow`           | P1                | Alternative electronics assembly             |
| `prodigi`           | Existing commerce | Printed cards, artwork and packaging inserts |

Unsupported methods must return `unsupported` rather than fabricated quotes.

Since JLC API approval is not guaranteed, implement a `manual_quote` adapter with the same output structure. That would let us submit manufactured files through the supplier website while keeping the rest of the project workflow intact.

### JLC and LCSC documentation

These are the developer resources I'd use:

- [JLC API portal](https://api.jlcpcb.com/) — API registration and approved specifications.
- [JLCPCB API application and capabilities](https://jlcpcb.com/help/article/jlcpcb-online-api-available-now).
- [JLC3DP pricing and ordering access](https://jlc3dp.com/help/article/jlc3dp-api).
- [LCSC OpenAPI reference](https://www.lcsc.com/docs/openapi/index.html) — part search, detail, availability and prices.

For electronics authoring, I'd use KiCad as the canonical schematic/PCB environment, driven by its supported automation/export tools rather than relying on a language model to produce arbitrary Gerbers. Use Blender/build123d for enclosures and mounting geometry.

## 8. What to build now in `prx0r/pogpet`

Your existing OddHobb product vision already defines product templates with non-negotiable dimensions, customisation zones and supplier routing.

Extend that rather than starting another unrelated app.

I'd add an internal `studio/hardware` module containing:

```
hardware/
  schemas/
    product.v1.json
    component.v1.json
    capability.v1.json
    device.v1.json

  catalog/
    rgb_led.yaml
    ptt_button.yaml
    ambient_light_sensor.yaml
    esp32_voice.yaml

  templates/
    glowbase.v1/
    living_house.v1/

  simulation/
    virtual_device.ts
    scenario_runner.ts
    lighting_preview.ts

  cad/
    build123d/
    blender/

  electronics/
    kicad/
    bom_validator.py

  firmware/
    esp32/

  suppliers/
    jlc3dp.py
    jlcpcb.py
    lcsc.py
    manual_quote.py
```

Make it available through the existing OddHobb API and later MCP tools.

The first agent tools should be:

`list_components`, `create_hardware_project`, `add_capability`, `validate_design`, `simulate_device`, `estimate_cost`, `request_supplier_quote`, `submit_prototype_for_approval`.

The agent should only be allowed to request manufacturing orders after explicit approval and a verified quote.

## 9. The first reference project

I'd use GlowBase + Living House as the two templates.

GlowBase validates lighting, power, mounting, costs and Home Assistant interoperability.

Living House validates microphones, speakers, push-to-talk, sensors, multiple lighting zones and the Pogtown personality layer.

## Living House reference configuration

| Controller    | ESP32-S3-class module                                      |
| ------------- | ---------------------------------------------------------- |
| Voice         | Digital mic + speaker + amplifier                          |
| Interaction   | Front push-to-talk button + physical mute                  |
| Lighting      | 4 isolated addressable light zones                         |
| Sensor        | Digital ambient-light sensor                               |
| Power         | USB-C, 5V, budget to be calculated                         |
| Manufacturing | JLC printed shell + PCB assembly + Shenzhen final assembly |

Reference design targets; not a validated schematic or supplier quotation.

The first full acceptance test:

1. Generate a custom Living House shell from Meshy or Atlas.
2. Fit the validated electronic core using exact CAD geometry.
3. Open the digital model in Studio.
4. Connect a Pogtown agent to the virtual device.
5. Simulate button presses, light-sensor changes, emotion-driven lighting and speech.
6. Produce validated manufacture files and a BOM with actual supplier part numbers.
7. Request a JLC quote and generate a final-assembly pack.
8. Approve and order one prototype, then compare real behaviour with simulation.

That's the exact vertical slice worth building.

The larger vision is an agent-native physical app store: agents don't merely generate 3D sculptures; they design products with verified electronic capabilities, test their behaviour in a simulated environment, receive manufacturer quotations, and sell them as real objects.

The same standard library of lights, sensors, buttons, speakers and displays can eventually support smart collectibles, fairy houses, plant habitats, meditation devices and expressive robots.

And the most important moat is that every successfully manufactured product improves our database of tested parts, compatible geometry, reliable behaviour, supplier pricing and real-world performance.