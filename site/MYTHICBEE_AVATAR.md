# MythicBee Avatar — The Clippy Rebuilt

**Source:** Research synthesis from Rive, Spine, three.ws, Spline, Live2D, dotLottie, 8th Wall

---

## The Vision

A branded AI character that lives on the page, idles, buzzes to different UI elements, reacts to what the visitor is doing, can be clicked, listens, speaks, and occasionally performs little animations.

Not generic 3D. The distinctive 2D/anime rendering is part of what makes it good.

---

## Three Manifestations of the Same Character

### 1. Brand mark
Simplified MythicBee silhouette. For favicon, foil stamping, packaging, social avatar.

### 2. MythicBee character (THE CLIPPY)
The exact 2D illustrated character. **Rive.** Lives on the site.

### 3. MythicBee embodied agent
3D version. three.ws / Spline / GLB. For hero sequences, AR, marketing videos, onboarding.

**The heraldic bee is the mark. The anime bee is the character. Same entity, different abstraction.**

---

## The Stack (MVP)

```
Rive character → CSS/GSAP page flight → ElevenLabs or Vapi voice → state-machine controller
```

### Rive (10/10)

- Animation state machine (not fixed GIF)
- 12-16 pieces: head, eyes, mouth, antennae, thorax, abdomen, arms, wings, cape
- States: IDLE → FLY → LAND → LISTEN → TALK → REACT → CELEBRATE
- Events from website: hover, click, upload, generation
- Open source JS/WASM runtime
- Used by Duolingo for Lily's AI video-call character

### Voice (ElevenLabs or Vapi)

- ElevenLabs: embeddable browser agent, voice + text, SDK control
- Vapi: browser SDK, real-time voice, client-side tool calls
- The bee can call: `fly_to()`, `point_at()`, `celebrate()`, `look_confused()`

### Page Movement (CSS/GSAP)

Separate from Rive. CSS moves the bee container:
- Fly from bottom right → hero
- Orbit CTA
- Follow mouse briefly
- Land beside upload field
- Fly behind/around cards
- Dock back into corner

---

## The Interaction Flow

```
PAGE LOAD
    ↓
bee flies in once
    ↓
lands bottom-right
    ↓
quiet hover animation

                     user approaches CTA
                              ↓
                     bee looks toward CTA

USER CLICKS BEE
    ↓
"Who are we making something mythic for?"
    ↓
voice/text conversation
    ↓
bee guides user through site

UPLOAD PHOTO
    ↓
bee flies over
    ↓
inspects photo
    ↓
thinking animation
    ↓
"Okay. I have an idea."
    ↓
creation begins

GENERATION
    ↓
bee becomes the loading state
    ↓
flies around / looks busy / disappears through portal
    ↓
returns carrying the result
```

---

## The 3D Incarnation (Later)

Use three.ws:
- Agent Identity Studio → rigged GLB from brand brief
- Standard rigged GLB (not locked to renderer)
- For: interactive hero, AR ("Meet your director"), marketing videos

Use 8th Wall (now open source, MIT):
- AR: "Put MythicBee in my room"
- Post-purchase: "Meet your director" — bee flies onto customer's real desk

---

## Recommended MVP

1. **Rive character** (exact current artwork, 12-16 pieces)
2. **CSS/GSAP page flight** (bee container moves independently)
3. **ElevenLabs or Vapi voice** (text/voice conversation)
4. **Small state-machine controller** (IDLE→FLY→LAND→LISTEN→TALK→REACT)

Then separately: three.ws for 3D incarnation. 8th Wall for AR later.

---

## The Bee as Loading State

Instead of a boring spinner during generation:

**The bee becomes the loading state.**

Flies around / looks busy / disappears through a little portal / returns carrying the result.

Makes MythicBee feel substantially more alive than standard AI-generation websites.
