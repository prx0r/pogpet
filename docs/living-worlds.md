# Living Worlds — fairy house with something inside it (2026-10-10)

Strongest near-term idea: presence beats motion. A cottage with
expressive lighting, a voice, a little door and occasional sound reads
as inhabited for the price of LEDs. Progression: historical miniature
gifts → personalised worlds → living fairy houses → expressive
companions → custom agent-linked robots. Same Shenzhen model throughout;
suppliers sophisticate, compiler stays constant.

## Famous rooms (differentiation required)

Historic-workshop book-nooks exist (da Vinci kits with gears + lights),
so don't make another lookalike room. Picks: Churchill war room
(maps + conference table + educational digital layer), da Vinci workshop
(buildable engineering projects + inventor agent), Tesla lab (low-voltage
lighting + experiments companion), Darwin study (specimens + botanical
packs), Van Gogh bedroom (printable variants + AR composition layer).
Also: Curie lab, Beethoven room, Jung library, alchemist workshop,
scriptorium, Apollo control, naturalist cabinet. Rights rule: historic
people/old designs often usable; museum photos/scans/layouts/modern
reconstructions are separately rights-held. Model from lawful references,
licence museums where apt. Museum licensing partnerships are a live
channel (UK museums pursuing commercial experiences).

## The fairy house (Tamagotchi with a house, not a screen)

Humming from inside, glowing upstairs window, shadow past curtains.
"Jenny, are you awake?" → "Unfortunately. I've been trying to finish
this song for an hour." Guitar request → lights dim, music plays, window
pulses with rhythm. Performed through the house audio (+optional AR),
not a miniature guitar. Closed house invites imagination — implied
activity exceeds hardware. Controller + cloud voice/agent; local
firmware does safe predictable actions only.

## Five hardware levels (same identity + event system throughout)

1. Heartbeat (USB LEDs, patterns, exterior; optional phone AR).
2. Voice (speaker/mic + live agent voice).
3. Presence (touch, window display, silhouettes, responsive light).
4. Visible resident (animated eyes/head-turning/shell character).
5. Movement (servos, locomotion, sensors, docking, safety).
Character memory/personality survives upgrades.

## Prototype hardware (checked 2026-10-10, prices ex-ship/tax)

- M5Stack AtomS3R AI Chatbot Kit ($21.50 reported): mic/speaker/motion,
  voice-assistant support. Jenny's voice starting point.
- Tobi ESP32 robot (open-source, GitHub): OLED eyes, touch, sleep modes,
  printable enclosure. Minimum viable expressive resident reference.
- Petoi Bittle X ($319): reference only — far too elaborate for v1.
- Rolife illuminated houses (~$30–55): price anchor proving the aesthetic.
- Prototype: voice module + addressable LEDs + printed enclosure + decent
  speaker; cloud agent decides, local firmware acts.

## Command architecture (adopted)

Agent events → authorised device commands → local ESP32 → light/audio/
movement. NEVER raw LLM output to servos/electrics. Our objects
set_state IS this layer (validated event names, owner-enforced); device
command allowlists per capability come later.

## Supplier split (roles, not one vendor)

JLC3DP shells/precision · Makerfabs electronics+enclosure+assembly+test
(coordinates partner factories) · Seeed sourced components + hardware
kits (5-kit entry) · Elecrow boards/LED fixtures/future mechanisms ·
consolidation partner boxes all of it. Neither the exact product ready
nor the services imaginary — prototype to prove.

## Catalogue strands (shared walls/doors/lights/interfaces/packaging)

History Rooms (build + learn) · Memory Rooms (preserve + stories) ·
Living Worlds (persistent inhabitants). Hundreds of distinct experiences
from a small verified component catalogue — the margin engine.

## First experiment: Living Cottage 001 — Jenny's House

Three prototypes, ONE exterior: passive (shell + windows + USB light) /
connected (ESP32 + speaker + mic + patterns) / expressive (+ silhouette
or servo door). Same manifest + agent identity. Measure presence per
pound: if passive compels → decorative business; if voice transforms →
connected hardware; movement only if it earns it. Longer term: portable
identity across cottage/speaker/AR/robot body; buy home, expand, commission.
Next supplier milestone: Makerfabs/Elecrow deliver ONE assembled tested
voice cottage (custom JLC shell, parts list, firmware version, packaging
spec, unit-cost quote). Recipe: living_cottage_001 (this repo).
