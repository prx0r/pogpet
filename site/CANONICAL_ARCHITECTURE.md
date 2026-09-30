# MythicBee Avatar — Canonical Architecture

**Date:** 5 September 2026

---

## The Core

Bartholomew is not a chatbot bolted onto the site. **He is the interface to the studio.**

---

## Canonical Stack

```
MYTHICBEE.COM
    │
    ├── BARTHOLOMEW UI (layered character)
    │   ├── Motion.js (position, flight, hover, land, point, bounce)
    │   ├── Inworld Realtime (WebRTC voice loop)
    │   │   ├── STT → LLM → TTS
    │   │   └── Function calls
    │   └── GiftBrief (structured user object)
    │
    └── NORMAL WEBSITE UI
        └── products / upload / checkout / previews
```

---

## The Character

**Bartholomew III, Keeper of MythicBee.**

Not generic 3D. The distinctive 2D/anime rendering is the brand.

Character sheet from exact current artwork:
- neutral flying, idle hovering, listening, thinking, talking
- excited, pointing left/right, carrying something, celebrating
- sleeping/resting, tiny favicon pose

Separate moving components:
body, eyes, mouth, antennae, front wing, rear wing, cape-upper, cape-lower, front arm

Export as transparent WebP/PNG layers. Use **Motion** (MIT, free) for animation.

---

## Voice: Inworld Realtime

- WebRTC browser connection
- STT → semantic turn detection → LLM → TTS
- Function calls (the bee can call page actions)
- First audio under 1 second
- On-demand pricing: STT $0.15/hr, TTS-2 Flash $15/1M chars
- Effectively free for prototype

---

## The GiftBrief (Structured User Object)

```json
{
  "occasion": "Fathers Day",
  "recipient": {"relationship": "dad", "name": null, "age": 60},
  "interests": ["football", "Liverpool FC"],
  "personality": ["teasing", "humorous"],
  "memories": [],
  "tone": null,
  "desired_product": null,
  "budget": null,
  "deadline": null,
  "assets": {"photos": [], "videos": [], "voice_notes": []},
  "confidence": {"occasion": 1.0, "recipient": 0.9, "creative_direction": 0.25}
}
```

Conversation = natural-language slot filling around this object.

---

## Bartholomew's Tools

```
update_gift_brief(fields)    get_gift_brief()
show_products(product_ids)   show_example(example_id)
focus_element(element_id)    fly_to(element_id)
point_at(element_id)         set_expression(expression)
celebrate()                  request_photo_upload()
create_concept()             create_preview()
add_to_cart(product_id)
```

Animation tools = safe client-side effects.
Purchasing/generation = server actions with explicit UI confirmation.

---

## Character State Machine (Event-Driven)

```
NO CONVERSATION → idle_hover
USER SPEAKING → listening (wings slow, eyes toward user)
USER STOPS → thinking (small hover loop)
FIRST AUDIO → talking (mouth/audio-reactive)
TOOL CALL → appropriate physical action
INTERRUPTED → stop talking, listening
CONCEPT COMPLETE → celebrate
```

Talking: run Inworld output audio through Web Audio analyser → map volume to mouth/head/body motion.

---

## The Persona

**Bartholomew III, Keeper of MythicBee.**

> MythicBee is an ancient studio whose job is to preserve ordinary mortals as legends. Bartholomew takes that absurdly seriously.

He is charming, slightly theatrical and faintly ancient, but never verbose. Speaks like an excellent luxury concierge who happens to be a small mythic bee.

**Conversation should continually collapse into action.**

---

## Free Escape Hatch

Later, if API costs matter:

```
VoiceProvider → INWORLD | SELF-HOSTED
                        → Pipecat → Whisper + LLM + Kokoro
```

Pipecat: open source, orchestrates realtime voice agents, interchangeable providers. SmallWebRTCTransport is open source, peer-to-peer, no vendor key.

**Don't build self-hosted now. Build the prototype.**

---

## Canonical MVP

| Layer | Choice |
|-------|--------|
| Character source | Our canonical layered Bartholomew artwork |
| Character animation | Motion |
| Character state | TypeScript state machine |
| Page movement | Motion DOM transforms |
| Voice transport | WebRTC |
| STT + TTS + LLM | Inworld Realtime |
| Agent actions | Inworld function calling |
| Long-lived object | GiftBrief JSON |
| Backend | Existing app API |
| 3D/AR later | three.ws / 8th Wall (optional) |

One animated bee + one Inworld WebRTC session + one GiftBrief + six callable tools. That's the MVP.
