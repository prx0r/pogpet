# Muse Gadgets device layer (founder research, verbatim 2026-10-10)

> Imported from chat. Gold reference for the agent-to-device strategy:
> Meta owns agent connectivity; OddHobb owns design-to-manufacturing.
> Pairs with `vision/living-house-001-spec.md` and `studio/` (imported
> `oddhobb-studio-v0.zip` — the mood-lamp trial simulator).

## 1. Meta released almost exactly the SDK layer described

A complete agent-to-device simulation: ESP32-C3 controller, 12 WS2812B RGB
LEDs, BH1750 light sensor, contextual agent events, simulated
electrical/safety constraints over 56 seconds. The agent expresses an
intention, the device SDK translates it into bounded physical behaviour,
and the simulator verifies the result before manufacturing.

Meta launched **Muse Gadgets** (gadgets.muse.ai) on October 2, 2026, with a
public open-source device SDK: `facebookincubator/muse-gadget-sdk`
(Apache 2.0, ~1.6k stars). Meta supplies ESP32 firmware, a Linux SDK,
device pairing, custom commands and a local graphical simulator, and
explicitly invites developers to create custom displays, buttons, sensors
and actuators its Muse agent can operate.

## 2. What Meta's SDK includes

- **ESP32 Device SDK** — boards with LEDs, buttons, screens, audio
  depending on hardware. Commands registered (e.g. reading a sensor,
  controlling a relay). ESP-IDF 6.0.1, several ESP32 variants.
- **Desktop simulator** — production gadget UI + avatar renderer in a
  virtual display. Scripted screenshots, mouse/keyboard input, no hardware
  needed. Test character expressions and display interfaces pre-PCB.
- **Linux Device SDK** — Muse interacts with hardware/services via Linux
  devices incl. Raspberry Pi and Home Assistant. A local gateway from one
  Muse agent to many OddHobb products.
- **Avatar tooling** — pixel-art Muse avatar for device displays, then
  build + flash (`tools/muse/avatar.py`). Direct overlap with Pogtown
  multi-embodiment characters.

Agent connection via `link.register`: firmware advertises a bounded
capability (e.g. `house.set_expression {expression, intensity}`), Muse
invokes it, the device decides the physical rendering. Same intent/
implementation split as Pogtown. Study the protocol as an optional
adapter — never depend the architecture on a Muse account or proprietary
pairing.

## 3. Adjacent open-source projects (different layers)

| Project | Layer |
|---|---|
| ESPHome | declarative ESP32 firmware, sensors, lights, HA integration |
| Wokwi Part Tests | automated simulation/tests for components, LEDs, displays, ESP32 |
| Home Assistant MCP / config MCP | expose devices to assistants; author/test automations |
| Muse Gadget SDK | agent-to-device integration, firmware, simulator |

None gives the full loop: beautiful enclosure design, known-compatible
components, behaviour preview, fabrication quote, finished-product order.
That loop is OddHobb's.

## 4. Simulator: three independently testable layers

- **Layer A — agent behaviour**: correct SDK use, supported actions,
  permissions, tool-failure recovery.
- **Layer B — firmware + electrical**: current limits, timing, comms
  failures, event handling. Sim-model passes are not bench truth: PCB
  supply current, wiring, thermal, power sag, optical flash safety need
  real measurements; low event frequency alone never proves
  photosensitive safety.
- **Layer C — physical optical experience**: real GLB in Blender, LED
  emitters behind windows, diffuser materials, identical event trace
  through the lighting rig.

Goal: replay one trace across software sim, firmware tests, Blender
scene, and physical prototype; compare intended vs observed.

## 5. The OddHobb device manifest (provider-independent)

```json
{
  "device_type": "oddhobb.living_house.v1",
  "capabilities": {
    "lighting": {"zones": 4, "rgb": true, "max_brightness": 0.8},
    "ambient_light": {"unit": "lux", "sensor": "BH1750"},
    "audio": {"speaker": true, "push_to_talk": true}
  },
  "integrations": ["pogtown", "home_assistant", "muse"]
}
```

Adapters: **Pogtown** (expressions, activities, stories), **Muse Gadgets**
(discovery of approved capabilities), **Home Assistant** (local light,
sensors, routines), **MCP** (other authorised agents), **Studio Simulator**
(testing without manufacturing). Caution: Muse pairing credentials +
terms required; OSS licence grants no avatar-asset rights; ESP32 voice
path is unproven for full bedside storytelling — LiveKit or another
verified audio pipeline may still win for Pogtown.

## 6. The moat: agent-native physical device registry

Every approved component a reusable template: mechanical CAD + mounting
interfaces, real parts + pin mappings, supplier/part-number refs, firmware
driver + capabilities, simulator + test scenarios, optical/audio render
config, manufacturing/assembly instructions, verified prototype
measurements + revision history.

Agent: "make me a mushroom cottage that glows when I'm happy, four rooms,
press the door to speak" → studio picks a validated core, checks zones,
generates the exterior around the locked interface, simulates agent use,
requests a JLC quote. Verify electronics once, manufacture many designs.

Next step: study `muse-gadget-sdk` alongside the mood-lamp simulator and
implement one `oddhobb.device.v1` capability contract with both a Muse
adapter and a Pogtown adapter. If the 56-second trace runs identically
through both with the same safety bounds and virtual lighting response,
that is the reusable foundation for Living House, GlowBase, and future
expressive robots.
