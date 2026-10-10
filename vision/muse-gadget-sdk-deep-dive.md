# Muse Gadget SDK deep dive: what developers will build, and where OddHobb should compete

I inspected the source tree, supported-board matrix, simulator, Linux integration, device skills and GitHub issue/PR activity for [facebookincubator/muse-gadget-sdk](https://github.com/facebookincubator/muse-gadget-sdk).

Muse Gadget SDK

Apache 2.0 SDK · First published October 2, 2026

1,922 stars · 396 forks · Active hardware contributions

Repository snapshot checked October 10, 2026. GitHub interest is not evidence of commercial sales.

My main conclusion: the obvious Muse gadget categories will become crowded very quickly. OddHobb should specialise in custom physical embodiments and modular agent habitats, not generic smart assistants with a screen.

The SDK is already making voice-enabled screens and desktop agents fairly easy to build. But it doesn't solve arbitrary customised enclosures, optics, manufacturing tolerances, pricing, kitting, or synchronising a physical product with a persistent fictional character's world.

Those are exactly the problems we're already working toward.

## 1. What developers are most likely to build

These are forecasts based on the repo's examples and early contributions, not measured market-share figures.

| Category                             | Likely developer activity           | OddHobb opportunity                      |
| ------------------------------------ | ----------------------------------- | ---------------------------------------- |
| Tiny AI displays                     | Very high                           | Avoid commodity screens                  |
| Smart-home agents                    | Very high                           | Build compatible decorative interfaces   |
| Voice-controlled desk pets           | High                                | Custom shells and distinctive characters |
| AI wearables                         | High                                | Later hardware modules                   |
| Sensor hubs                          | High                                | Modular sensor-aware habitats            |
| Embodied robot agents                | Growing, technically harder         | Long-term premium tier                   |
| Personalised illuminated objects     | Relatively underrepresented in repo | Immediate priority                       |
| Agent-designed manufactured products | Little evidence in SDK              | Potential platform differentiator        |

### Tiny AI screens and desktop companions

Round AMOLED companions: custom animated faces, captions, voice interfaces and notifications.

M5Stack desktop agents: desk assistants with push-to-talk, local controls, animated avatars and menus.

The SDK already supports Waveshare AMOLED boards, the M5Stack CoreS3, StickS3, Core2 and other boards with combinations of screens, microphones and speakers.

There's even an open PR for a multi-app launcher on the Core2, and work on getting spoken Muse replies playing through embedded speakers.

See [multi-app launcher #131](https://github.com/facebookincubator/muse-gadget-sdk/pull/131) and [spoken replies #146](https://github.com/facebookincubator/muse-gadget-sdk/pull/146).

These products will be relatively straightforward to replicate. You buy an existing board, print a housing, flash firmware, and customise the avatar.

It's appealing, but not a particularly differentiated first product for us.

### Home automation gadgets

This is the other obvious direction. The SDK's `skills/` directory already contains community integrations covering ESPHome devices, Zigbee2MQTT, Tuya and other smart-home systems.

There's also an active proposal for turning a Muse gadget into a Matter controller, making an ESP32 bridge between Muse and compatible home devices.

[Matter controller proposal #158](https://github.com/facebookincubator/muse-gadget-sdk/issues/158).

For OddHobb, this suggests our devices should support Home Assistant and local control from day one. A light shouldn't become useless if the owner stops using Muse.

### AI wearables

The contributions are already moving toward smart rings, watch-like gadgets and compact display devices.

For example, the open [SmartRing-Plus support #162](https://github.com/facebookincubator/muse-gadget-sdk/pull/162) proposes an ESP32-S3, 360 × 360 display, touch, microphone, speaker and battery monitoring.

That's strong evidence that developers want AI connected to devices more personal than a phone.

However, wearables introduce batteries, charging, heat, fit, ingress protection and more demanding safety requirements.

I'd leave them until OddHobb has proven the simpler module system.

## 2. The GitHub activity reveals what developers actually want

The repository is only eight days old, but its issues and pull requests are already informative.

Agent-controlled espresso equipment: a contribution connects an open-source grind-by-weight controller and coffee scale to Muse. This is exactly the trend toward agents controlling specialised equipment, not just answering questions.

[Espresso integration #128](https://github.com/facebookincubator/muse-gadget-sdk/pull/128)

Reachy Mini robot integration: several open contributions propose Linux SDK hooks, live speech streaming and turn tracking specifically to let a Reachy Mini communicate with Muse.

[Voice input #138](https://github.com/facebookincubator/muse-gadget-sdk/pull/138) · [Speech streaming #139](https://github.com/facebookincubator/muse-gadget-sdk/pull/139) · [Public SDK hooks #142](https://github.com/facebookincubator/muse-gadget-sdk/pull/142)

Lighting and home equipment: the community skills catalogue already lists 43 integrations, including Philips Hue, Lutron, ESPHome, Zigbee2MQTT, Sonos, Apple TV and robotic vacuums.

[Device skills catalogue](https://github.com/facebookincubator/muse-gadget-sdk/blob/main/skills/CATALOG.md)

Security and reliability tooling: developers are improving token handling, request correlation, power measurement and permission guards. One contribution proposes an additional execution-approval layer for Muse commands on Linux.

[Runtime execution guard #153](https://github.com/facebookincubator/muse-gadget-sdk/issues/153)

This suggests three emerging developer behaviours:

Hardware porting. People take whatever ESP32 board they own and add Muse support.

Tool bridging. People expose existing device APIs to an AI agent.

Embodiment. People give an agent a physical display, voice interface or robotic body.

OddHobb's idea is related to the third category but goes further: the physical body itself becomes something an agent can design, customise, manufacture and sell.

## 3. What the SDK does well — and where it stops

| Capability                           | Muse SDK today                       | What OddHobb must add                                      |
| ------------------------------------ | ------------------------------------ | ---------------------------------------------------------- |
| Agent-to-device communication        | Yes                                  | Provider-neutral device protocol                           |
| Wi-Fi/BLE pairing                    | Yes, on supported devices            | Product onboarding and device ownership                    |
| Voice on supported boards            | Yes, with hardware-dependent support | Persistent Pogtown voice/identity                          |
| Buttons and screens                  | Yes                                  | Physical template interfaces                               |
| Custom device commands               | Yes                                  | Bounded capability registry                                |
| Desktop UI simulation                | Yes                                  | Physical sensors, lighting, optics and assembly simulation |
| Automatic CAD enclosure generation   | Not in SDK                           | Meshy/Atlas → CAD compiler                                 |
| Electronics schematic/BOM generation | Not in SDK                           | KiCad and verified component blocks                        |
| Manufacturing quotations             | Not in SDK                           | JLC/LCSC/supplier adapters                                 |
| Customer purchasing                  | Not in SDK                           | OddHobb / Shopify                                          |
| Modular physical upgrade system      | Not in SDK                           | Core modules and compatibility registry                    |

The most important technical distinction is the simulator.

Muse's `esp32/simulator` compiles its actual user-interface components into a desktop program using SDL. It can simulate listening, thinking, speaking, pairing and display states, and run deterministic screenshot tests.

But its README explicitly states it does not simulate the ESP32 CPU, audio electronics, Bluetooth, Wi-Fi timing, memory pressure or power behaviour.

Your existing 56-second mood-light simulation is different: it models agent events, RGB LED output, changing lux measurements and estimated current limits.

That is an interesting opportunity to complement the SDK rather than duplicate it.

I would want one test manifest to drive all three:

Agent scenario → virtual electronics/optical behaviour → hardware-in-the-loop measurement.

For example, an agent says it is excited. The simulated fairy cottage brightens its windows. The firmware receives the same command. The real prototype's LEDs are measured to check that physical current and brightness stay within verified limits.

The virtual simulation is useful, but it cannot replace electrical and optical testing.

## 4. Where Muse is still immature

I wouldn't assume its developer ecosystem is production-ready yet.

There are currently open reports of:

- [Microphone capture returning silence (#173)](https://github.com/facebookincubator/muse-gadget-sdk/issues/173) on one Waveshare board.
- [Linux gadget commands not reaching the device (#154)](https://github.com/facebookincubator/muse-gadget-sdk/issues/154) despite successful pairing.
- [Voice-session authentication failure (#151)](https://github.com/facebookincubator/muse-gadget-sdk/issues/151) after token refresh.
- [Regional app availability blocking pairing (#157)](https://github.com/facebookincubator/muse-gadget-sdk/issues/157).

These are early user reports, not proof that every supported configuration has the same issues.

They're still relevant to a product business. A consumer shouldn't need to understand BLE tokens, debug serial logs or repair a firmware build.

For OddHobb, Muse should be an integration target, not the sole runtime the product requires.

This matters especially because your living houses could eventually be gifts for people who have no interest in Meta, home automation or software development.

## 5. What I think OddHobb should actually build

I'd prioritise products by three factors: physical desirability without AI, degree of reusable hardware, and how naturally the agent adds value.

P0 · Bread-and-butter hardware — 1. OddHobb GlowBase: a universal smart illuminated base for existing figurines, custom pets, trading cards, crystals and miniatures. Core: ESP32, addressable LEDs, USB power, optional NFC. Agent value: signals activity, incoming messages, achievements and moods. Commercial value: sell one base, then many inexpensive compatible attachments.

P1 · Flagship product — 2. OddHobb Living House: a custom miniature home with independently glowing windows, push-to-talk and a resident digital character. Core: audio controller, speaker, microphone, button, multiple LEDs. Agent value: conversation, storytime, visiting Pogs, expressive behaviour. Commercial value: custom houses, room expansions, new inhabitants and later hardware upgrades.

P1 · Sensor platform — 3. Living Garden: decorative plant habitat with soil moisture, ambient light and temperature readings. Core: same controller, sensor expansion and lighting. Agent value: a little fictional gardener responds to actual plant conditions. Commercial value: add-on sensors, greenhouse designs, planter shells and gift sets.

P2 · Distinctive optical hardware — 4. Living Windows: a module that creates the illusion of an inhabitant inside a building using light, layered silhouettes or a hidden micro-display. Core: LEDs, light baffles, optical inserts, optional display. Agent value: characters appear to walk, read, sleep, receive visitors or work. Commercial value: sell the illusion module to creators designing their own miniature buildings.

P3 · Robotics — 5. Expression Core: a standard moving/animated head with interchangeable agent-designed shells. Core: audio, LEDs/display, sensors and perhaps two servos. Agent value: physical presence, gestures and reactive expressions. Commercial value: designable robot personalities without reinventing every motor, controller and joint.

The fourth one — Living Windows — is the more unusual component I'd investigate seriously.

Most Muse developers seem to be putting an avatar on a small screen. We could create something that feels alive without displaying an avatar directly.

Imagine a standard 45 × 35 mm window module with programmable light, shadow layers and possibly a small removable silhouette cartridge.

It becomes a reusable component of fairy houses, book nooks, historic room models, miniature shops and agent habitats.

That's an actual physical invention and optical-design problem, where supplier testing matters.

## 6. The platform I'd build beneath those products

Call it OddHobb Physical SDK.

A product declares supported capabilities; Muse, Pogtown, Home Assistant or another agent consumes those capabilities through adapters.

```
const home = devices.get("jennys-cottage");

await home.express({
  state: "thinking",
  intensity: 0.6
});

await home.lights.setZone("study", {
  color: "#EFC17B",
  brightness: 0.45
});

home.on("button.pressed", async () => {
  await home.agent.startConversation();
});
```

Each capability has a simulator and a physical driver.

The design studio then becomes an experience in which the user can describe a product ("Build a tiny haunted library for my Pog, with glowing windows, a door button and a speaker."), generate an enclosure (Meshy/Atlas for visual design, Blender/build123d for precise mechanical interfaces), choose electronics (approved modules with real supplier part numbers and mounting requirements), simulate the agent (replay expression, audio, button and sensor events using the identical device interface), and estimate, quote and manufacture (JLC3DP/JLCPCB for appropriate parts, then supplier-approved assembly and packaging).

The differentiator isn't the Muse adapter. It's the validated relationship between software capabilities and physically manufacturable components.

## 7. Three concrete decisions I'd make now

First: use ESPHome-style local control for GlowBase, and keep Muse optional. That gives homelab users immediate utility while letting Muse and Pogtown express emotions through the same lighting interface.

Second: make the Living House's electronics cartridge removable and reusable. A customer should be able to upgrade their house without buying a whole new one. Fix the mechanical standard before letting agents design arbitrary exteriors.

Third: extend your existing 56-second simulation into a reusable test suite. Each new physical template should have a virtual device, bounded capabilities, recorded agent scenarios and eventual hardware-in-the-loop tests. Use the real GLB house model to preview the light effects.

The market signal from Muse is encouraging, but it also clarifies the competitive landscape. There will be thousands of developers making small Muse-connected gadgets if adoption continues.

Very few will want to handle a full process involving exact CAD, parts sourcing, PCB fabrication, enclosure manufacture, physical testing, branded packaging and fulfilment.

That's where OddHobb should sit: the factory and design studio for personalised physical embodiments of AI agents.

Start with a controllable light pedestal people can buy for their existing collectibles. Reuse its architecture for a Living House that can speak. Then let agents design increasingly complex compatible products around the hardware modules you've already validated.
