# Stone One — paired presence, sky display, meditation guide, agent link

Saved 2026-10-09. One object, four jobs, same BLE+LED+haptics core.
Phone holds intelligence; stone holds attention. No screen, no
controls on top, no speaker, no visible LEDs at rest (V1 rules stand).

## Modes (one stone, switched by gesture + app)

1. SOLO — classic Stone V1: breath field, mantra punctuation,
   silence. Baseline behavior when unpaired or alone.
2. PAIRED — the other person's nervous state, rendered as light +
   pulse. Never live biometrics (surveillance, not comfort): the
   stone plays the partner's *learned calm rhythm*, recorded over
   the prior week. Receiving is always warmer than sending.
3. SKY — astrolocal display: planetary hours, lunar phase, aspects
   as slow light positions on the shell. Symbolic system, stated
   as such — never a measurement claim. Updates hourly, dims at night.
4. GUIDE — spoken meditation from the phone with stone-synced cues.
   Timestamped patterns execute locally (BLE latency is real).
5. AGENT — the stone as an AI agent's hand: an agent with permission
   may schedule a pulse, a light state, or a guide session. Agents
   propose; the holder disposes (tap to accept, hold to decline).

## Pairing ritual (the product's soul)

Two stones touched together, like a toast. Both pulse once in sync.
Done — no accounts screen, no QR code, no app funnel (app pairing
confirms afterwards, silently). Unpair: hold both together for five
seconds; both go dark. No log survives by default.

## The five pair behaviors (V1 firmware)

- CALM OFFERING: hold yours 3s → partner's stone breathes their calm
  rhythm for 60s. No notification on their phone. No receipt.
- WORRY TRANSFER: squeeze during your spike → partner's stone does
  one slow breath cycle. Asks nothing back.
- MISMATCH GLOW: both wound up simultaneously → both glow amber.
  Answers "is it just me" with no confession required.
- GOODNIGHT: fade together at the later holder's pickup time.
- STILL HERE: first pickup after a flagged rough patch sends one
  slow pulse, held until picked up, expiring in 24h unanswered.

## State machine (per stone)

IDLE (dark) → HELD (sense lift) → MODE (last used) → CUEING →
RETURN (settle to signature stillness) → IDLE. Interruptions:
tap = pause/resume, hold 5s with partner = unpair, hold alone =
decline pending agent action. Bounded waits everywhere: no infinite
waits for imaginary partners; cues time out to IDLE with a closing
settle.

## Phone protocol (indicative)

`{cmd: breath|pulse|glow|fade|hold, pattern_id, t_start_ms,
intensity_0_1, duration_ms, expires_ms}` over BLE; stone ACKs
receipt, executes on local clock. Agent path identical with
`proposed_by` + `requires_accept` flags. HealthKit/Health Connect
supply resting baselines only (stored records ≠ live streams).
Muse/OpenBCI via BrainFlow arrive as labeled-uncertainty streams.

## Constraints carried forward

No always-listening hardware. No live heart-rate mirroring (offers
calm, never surveillance). No receipts on emotional transfers.
Mixed motives dilute: taboo/framing rules from the comedy work apply
— relief framing in hard times, reward in good. Compliance
(electrical, battery, radio, safety) before sale. USB-powered bench
first; protected LiPo only after usage validates.

## Internal light design (the gorgeous-fluid recipe)

Rule: nobody ever sees an LED. Every photon bounces or diffuses at
least once before leaving the shell.

Stack, inside out: PCB ring with 6–8 side-view addressable LEDs
aimed INWARD at a central matte-white reflector core → 2–3mm air
gap → inner shell surface frosted (sandblast or matte clear coat;
8001 translucent alone is not enough) → outer tinted shell. The eye
sees the glowing cavity, never a point source. Standoff distance is
the whole game: LEDs closer than ~8mm to the shell print hotspots
no diffuser can hide.

Fluid motion without resolution: 8 points can't flow, but time can.
Run traveling sine waves (2–3s period), gamma-corrected (human eyes
are logarithmic — linear fades look steppy), with adjacent LEDs
cross-faded so the peak lives *between* diodes. Persistence of
vision does the rest. Breath = global sine on brightness; attention
ribbon = traveling peak; silence = true zero (leakage kills the
magic — verify in a dark room, not daylight).

Color: warm whites + ambers for calm (blue reads clinical, red
reads alarm — reserve both), full saturation only for mismatch
amber. Brightness ceiling for bedrooms: under ~5 lumens total.
Prototype bench test: white box + phone slow-mo to catch flicker
(PWM below ~1kHz strobes on camera and sensitive eyes; run 4kHz+).

## Compatibility: PiEEG today, everything tomorrow

Design rule: the Stone never integrates *devices* — it subscribes to
*capabilities* (signal type, rate, latency, uncertainty). Anybody
providing "calm-index 0..1 at 1Hz" drives the same cue path, whether
it comes from a PiEEG headband, Muse via BrainFlow, OpenBCI, an
Aura wristband, or HealthKit resting data.

PiEEG specifically (open-source MIT server, browser BLE, 100+
universities): three integration points, easiest first. (1) Webhook
Wizard — their relaxation peak fires our HTTP endpoint, Stone
breathes; an afternoon's work, no code on their side. (2) OSC —
their VRChat-proven stream format; our app listens for focus/calm
channels. (3) Cloud dashboard + self-hosted server for lab-grade
sessions. Their Aura EMG band is additionally the natural tap
replacement for users who can't reliably press. Lab-grade multi-
device sync goes over LSL, not bespoke sockets. Research-use-only
disclaimers flow through everywhere; our claims stay inside
wellness (no diagnosis, no states, no thoughts).

## Visualization source: DeityBody lab (verified 2026-10-09)

prx0r/deitybody's Three.js lab already emits everything the Stone
visual layer needs — verified in its source, not its marketing.
`engine/breath.js` publishes `{phase, expansion 0..1, velocity,
confidence, source}` with simulation/microphone/score sources;
pulse + sweep + breath events drive particle fields, Chladni
visuals, and ring/tone punctuation from mantra drills. Mapping:
breath expansion % ← breath state; attention ribbon ← pulse/sweep
events; mantra punctuation ← ringPing + tone events; silence ←
existing pause/hold states. To build: (1) cue exporter from lab
events to the Stone BLE timestamped protocol; (2) phone preview
via navigator.vibrate on pulse events (unused there today);
(3) confidence-gated fallback to timestamps when mic confidence
drops — their own code already recommends this. No rebuild, adapter
only.

## Proposed stack (V1 bench → product)

| Block | Pick | Why it works | Alternatives |
|---|---|---|---|
| Wireless MCU | nRF52840 module | Mature BLE 5 stack, Arduino/Zephyr support, enough timers/GPIO for LED+motor+button, proven in wearables | ESP32-S3 if Wi-Fi/voice later (hungrier); nRF5340 if dual-core headroom needed |
| Haptic driver | TI DRV2605L | Waveform library + closed-loop LRA tracking, braking, no PWM tuning by hand | DRV2604L (cheaper, fewer effects); raw GPIO PWM (only for dumb buzz, never) |
| Actuator | 10–12mm LRA | Controlled resonance vs ERM rattle; precise start/stop for punctuation | ERM coin (cheap, muddy — reject for flagship); piezo (thin, needs high voltage) |
| LEDs | 6–8 SK6812 MINI-E side-view | Addressable, warm-white channel for calm tones, tiny footprint for ring layout | WS2812B (bigger, no dedicated white); discrete RGB + drivers (more wiring, no gain) |
| Input | Hidden mechanical press switch | Zero standby draw, unmistakable click, no phantom triggers | Capacitive touch (sleeker, false wakes + moisture issues); IMU tap-detect (free if IMU present, less certain) |
| Motion (opt) | LIS2DH-class accelerometer | Lift/held detection, tap backup, ultra-low power | BMI270 (better, pricier); none in V1 if press switch suffices |
| Power V1 | USB-C 5V direct | No battery risk, simplest bench, desk use is the 80% case | — |
| Power V2 | 300–500mAh protected LiPo + charger IC | Days at our duty cycles; protection mandatory, never bare pouch | Li-ion coin (lower capacity); wireless charging (luxury, heat + cost) |
| Shell optics | 8001 translucent + frosted inner + matte core | Proven diffuser stack per light recipe | Dye-tinted 8001 for mineral looks (test optics); silicone sleeve later (feel experiment) |
| App link | BLE GATT + timestamped patterns | Phone-agnostic, offline execution, iOS survivable | Wi-Fi/MQTT (only for desk companion variant with wall power) |

## Test path

Bench: two USB stones + app simulator → MISMATCH + STILL HERE with
two testers long-distance → SKY accuracy vs ephemeris → GUIDE sync
drift under 100ms → agent proposal/decline round-trip → 20-minute
sit test (dry + damp) → quote JLC shell + PCB.

## Feasibility verdict (2026-10-09, competitive landscape checked)

Yes, it can actually work — every subsystem is proven somewhere,
though never combined the way Stone One combines them.

PAIRED TOUCH: proven at scale. Bond Touch (1M+ users, $49–89) does
exactly tap→cloud→buzz over BLE-to-phone relay, 4-day battery, and
their users report the anxiety-calming use case unprompted. Hey
Bracelet did the wrist-squeeze variant at $115 a pair. Our topology
is identical; our shell is bigger, which makes battery strictly
easier. No technical risk here beyond iOS background-BLE flakiness,
which Bond lives with and so can we.
MEDITATION HAPTICS: proven at premium. Apollo ($349, Lofelt
haptics, scheduled sessions that run offline once started), Sensate
($279–299, chest sessions), Muse ($199–249, EEG+HR), Core ($159,
HR biofeedback handheld). Two lessons: scheduled offline patterns
are exactly our timestamped-local-execution protocol, and Apollo
sells calm while Sensate sells sessions — we sell both in one
object, which nobody does. Price umbrella sits $159–349 for a pair
offer around £120–150.
SKY DISPLAY: white space, honestly. Projection planetariums (Sega
$100–150) and the Cosmic Watch app prove the appetite; nobody sells
an ambient LED orb doing slow astronomical state. Unproven demand
cuts both ways — ownable if real, ornamental if not. Keep it the
cheapest mode to build (ephemeris + dimming curves, no hardware).
ELECTRONICS: standard parts, JLCPCB-assemblable, bench $27–90
holds. No red flags.
HARD PARTS, ranked: silicone skin feel (can't be prototyped into
existence — budget a proper industrial-design experiment); battery
vs LEDs (300–500mAh buys days at our duty cycles, but measure);
radio cert + battery safety before any sale (~five figures, plan
it early); NFC-on-metal needs ferrite or window (solved problem,
not a free one); EEG claims discipline (measure scalp signals,
claim nothing about thoughts or states).
MOAT CHECK: nothing here is patentably novel per-device. The moat
is the pairing ritual, the no-receipts emotional protocol, and the
single core across Stone/amulet/desk/wearable — system, not sensor.
