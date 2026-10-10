# Famous rooms + expressive robots (brainstorm 2026-10-10)

Two product lines, one endgame: custom expressive robots linked to
digital agents, built on supplier connections. Display commoditizes
(phones now, glasses later) — identity, rooms and the event protocol
are the durable layers.

## Famous rooms (splat → stylized miniature → agent home)

Honesty rules: splat is REFERENCE, never print source (canonical:
reconstruct-then-redesign watertight CAD). Real places need permission;
imagined places need none. Stylized "inspired-by" beats literal replica
for engineering, IP and cost.

| Room | Real/imagined | Splat path | Agent resident |
|---|---|---|---|
| Churchill War Rooms, London | real (IWM — permission needed) | visit + scan w/ consent | strategist |
| Da Vinci studio | imagined | pure creation | inventor |
| Van Gogh's Arles bedroom | painting (public domain) | paint as texture source | artist |
| Darwin's Down House study | real (English Heritage) | visit + scan w/ consent | naturalist |
| 221B Baker Street sitting room | museum + fictional | stylized set | detective |
| Jane Austen writing desk, Chawton | real museum | visit + scan w/ consent | novelist |
| Tesla Wardenclyffe lab | imagined/historic | stylized lab | inventor |
| Apollo mission control | historic (NASA) | reference photos | flight director |
| Frida Kahlo Casa Azul studio | real museum | stylized | artist |
| Edison Menlo Park lab | historic replica exists | reference | inventor |
| Jazz club (any era) | imagined | pure creation + QR playlist | musician |
| Childhood kitchen (customer's) | personal photos | remembered-place pipeline | family memory |

Personal rooms (rebuild-a-remembered-place) outrank famous ones for
gifting: sentiment beats fame. Famous rooms win as agent homes and
collectibles. Human review where photos hide geometry; mark guesses.

## Expressive robots, staged (each stage shippable)

1. **Glow** (now): fairy house + LED diffuser + PIR. Pet inside implied
   by light. Trivial cost, no movement, no battery drama (USB).
2. **Voice** (next): M5Stack Atom Echo-class speaker/mic + online TTS
   (our edge-tts pipeline). "Jenny, play guitar" — intelligence online,
   device plays. Natural voice = server-side models, not the chip.
3. **Wiggle** (next): one LED + one micro servo wave/nod. Single
   actuator, USB powered, no battery shipping rules.
4. **Pet** (WHAT THIS UNLOCKS): M5Stack ATOMIC Motion Base (4 servos +
   2 DC, battery, I2C, ~$23 class) or Seeed XIAO + Grove servos + $4.90
   servo driver. Guitar-strum = 2 servos + speaker. Rusty jokes = TTS.
5. **Companion** (later): vision/PIR + servo face + cloud persona with
   memory. Seeed XIAO vision AI + servo feedback boards exist.
6. **Custom robot** (endgame): JLC/Slant enclosures + Elecrow assembly +
   provisioned identity + test plan. Full device workflow.

## Supplier reality (checked 2026-10-10)

- M5Stack: motion bases in stock, modular, documented I2C servo protocol.
  Component supplier (never assembly) — matches our Glimling lesson.
- Seeed: XIAO ecosystem + Grove servos/sensors + $4.90 servo driver with
  position feedback; starter kit $52.99. RFQ houses for custom kits.
- Elecrow/Makerfabs: assembly + firmware + testing when servos meet
  custom shells. That's the pet-manufacturing conversation.
- Batteries: 18350/16340 lithium in the motion bases — shipping rules +
  toy regs apply the moment a robot has a cell. USB-first stages dodge
  this; battery stages need compliance work (canonical §3.4).
- Voice quality lives server-side. Never promise on-device smarts the
  chip can't deliver; sell the shell + the online character.

## The fairy-house illusion (why it works)

Presence is cheaper than motion. A lit window + a shadow that moves +
a voice that answers = a resident, for the cost of LEDs. Stages 1–3
are the business; stages 4–6 are the moat. The object record
(backend/objects.py) already carries capabilities + event states, so
today's glow-house graduates to tomorrow's pet without re-registration.
