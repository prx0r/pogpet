# Dev plan 2026-10-07 — Free Core + BYOC

Yes. **That is the better business model.** OddHobb should have a genuinely usable **$0 creative path**, then let the user attach their own creative compute for the expensive magic.

And yes: `prx0r/freaktown` already solved an important part of the lip-sync problem. I checked the current repo. It did **not** solve photoreal neural lipsync; it solved the thing we actually need for mesh characters far more cheaply:

> `Procedural sway + analyser jaw morphs; VRM expressions where rig has them`

with **one master Web Audio timeline** driving the performance.

That architecture should be lifted almost wholesale into OddHobb.

## The stack should be Free Core + BYOC

Think of OddHobb like this:

```text
                     ODDHOBB
              creative compiler + data

                      │
        ┌─────────────┴─────────────┐
        │                           │
   FREE / LOCAL                  BYOC
   $0 API spend               Bring Your Own Compute
        │                           │
        │                    ┌──────┼─────────┐
        ▼                    ▼      ▼         ▼
  deterministic          Higgsfield fal    Alibaba
  compositor             API       API      Cloud
  Freaktown stage
  Blender
  WebAudio
  open models
        │                    │
        └────────────┬───────┘
                     ▼
               same artifact
                  contract
```

I prefer **BYOC** to BYOK conceptually, because later the provider doesn't even have to be an API key. It might be:

- fal API key
- Higgsfield API credentials
- Alibaba Model Studio
- user's own ComfyUI
- their own GPU endpoint
- RunPod
- local machine
- another MCP tool
- something that doesn't exist yet

OddHobb just asks for a **capability**.

---

# Freaktown already gives us the free performance engine

There are three particularly useful ideas already sitting there.

First, the avatar contract is provider-neutral:

```text
character.json
avatar.glb / avatar.vrm
avatar.json
voice_reference.wav
delivery.json
set.wav
```

Second, Freaktown already established:

```text
TTS provider
     ↓
one canonical audio timeline
     ↓
body motion
camera
gestures
jaw movement
sound effects
```

And third, its `delivery.v1` format already describes:

```json
{
  "text": "...",
  "pace": 1.0,
  "energy": 0.65,
  "expression": "deadpan",
  "gesture": "shrug",
  "camera": "close",
  "pause_after_ms": 600
}
```

That's *fantastic* for OddHobb.

We should not rebuild that.

---

# Free lip sync = Freaktown lip sync

For an OddHobb mesh, we don't need Kling lipsync at all.

We already have audio. Feed it to Web Audio:

```text
audio
  ↓
AnalyserNode
  ↓
RMS / frequency energy
  ↓
jawOpen / mouth morph
```

with smoothing:

```text
targetJaw = speechEnergy(audioFrame)
jaw += (targetJaw - jaw) * smoothing
```

Then layer:

```text
speech envelope
+
blink
+
head movement
+
gesture cues
+
expression
```

It isn't phoneme-perfect.

But for:

- Oddy
- brick Dad
- cartoon Dad
- pet mesh
- Dot/Muse avatars
- comedy stage performers

it is **more than good enough**, costs essentially nothing, runs live in the browser, and remains perfectly synchronized because the same audio clock drives everything.

That's exactly why Freaktown's architecture says:

> “honest motion, never faked mouths.”

For stylized characters that's the right decision.

---

# We can make it better without paid AI

The next free upgrade isn't neural lipsync. It's **viseme timing**.

So:

```text
FREE LEVEL 0
audio amplitude → jaw

FREE LEVEL 1
TTS word timings → speech envelope

FREE LEVEL 2
text/phonemes → viseme sequence
AA / OH / EE / FV / MBP etc.
       ↓
GLB morph targets

PAID / BYOC
neural video lipsync
```

For a rigged character we can author maybe 6–10 mouth shapes and get dramatically better speech without any video model.

So the free performance stack becomes:

```text
Qwen/Edge audio
      │
      ├── word timings
      ├── phonemes/visemes
      └── audio signal
             │
             ▼
      FREAKTOWN TIMELINE
             │
    ┌────────┼─────────┐
    ▼        ▼         ▼
 jaw/face gestures   cameras
```

This can produce surprisingly polished stuff entirely deterministically.

---

# The catch with “free voice cloning”

Freaktown already has a `Qwen3TTS` provider abstraction and explicitly designed it for:

> open-source voice cloning from reference audio.

But its current implementation is still a **placeholder**: it identifies the right Qwen3-TTS model, checks CUDA, exposes `reference_audio`, but doesn't actually produce the cloned audio yet.

So that is one thing we should finish properly.

The upstream Qwen3-TTS code is open source and supports voice cloning; the official package exposes the voice-cloning primitives. [GitHub](https://github.com/QwenLM/Qwen3-TTS/blob/main/qwen_tts/__init__.py?utm_source=chatgpt.com)

The economics are:

```text
Edge TTS                         $0 API / CPU
Qwen3-TTS self-hosted            $0 API / needs GPU compute
user's Qwen worker               $0 to OddHobb
Alibaba hosted Qwen              user's API spend
ElevenLabs etc.                  user's API spend
```

So I wouldn't falsely advertise:

> infinite cloud voice cloning costs nobody anything.

But we absolutely can say:

> **OddHobb itself does not require a paid generation provider.**

That's an excellent property.

---

# Then BYOC turns on the insane versions

Imagine the user opens a card:

### Dad — Sports Presser

OddHobb could show:

```text
FREE
✓ personalised copy
✓ Dad photo
✓ broadcast graphics
✓ printable card
✓ animated mesh version
✓ spoken video
✓ basic lipsync

MAKE IT REAL
○ Higgsfield
○ fal.ai
○ Alibaba
○ My GPU
```

That is much better than us paying for every experiment.

---

# Higgsfield is especially neat for this

Higgsfield now has a proper developer API, and one API credential opens its API model catalogue; importantly, its API balance is distinct from its normal website subscription. [Higgsfield](https://higgsfield.ai/creator-hub/help-center/integrations/what-is-the-higgsfield-api?utm_source=chatgpt.com)

And right now it exposes **Wan 3.0** directly.

For example, its Wan 3.0 reference-to-video route is literally:

```text
alibaba/wan-3.0/reference-to-video
```

and accepts reference images. [Higgsfield API](https://open.higgsfield.ai/models/alibaba/wan-3.0/reference-to-video/api-reference?utm_source=chatgpt.com)

So a user's connected Higgsfield could be:

```text
OddHobb scene
+
Dad references
+
sports presser visual reference
+
script
       ↓
user's Higgsfield account
       ↓
Wan 3.0
       ↓
premium MP4
```

OddHobb pays **zero**.

Higgsfield also exposes one REST interface around multiple image/video families, so the user connection isn't hard-coded to Wan. [Higgsfield API](https://open.higgsfield.ai/quick-start?utm_source=chatgpt.com)

---

# Same with fal

fal explicitly supports configuring the SDK using a supplied credential, and says those credentials should be protected server-side rather than shipped into browser JS. [Fal](https://fal.ai/models/fal-ai/speech-to-text/api?utm_source=chatgpt.com)

So:

```text
Settings
  Creative providers

  ✓ Free OddHobb
  + Connect fal.ai
  + Connect Higgsfield
  + Connect Alibaba
```

Then we store a credential reference:

```json
{
  "provider": "fal",
  "credential_id": "cred_2981",
  "owner": "tom",
  "status": "connected"
}
```

**Never** put their actual secret into a Creative Revision.

And never expose it to Muse/ChatGPT.

Muse sees:

```json
{
  "providers": {
    "free": true,
    "fal": true,
    "higgsfield": false
  }
}
```

not:

```text
FAL_KEY=...
```

---

# Provider credentials should sit behind a vault

Something like:

```text
provider_connections

id
owner
provider
encrypted_secret
metadata_json
created_at
last_used_at
status
```

Server-held encryption key.

Then agents get capabilities:

```json
{
  "video": [
    {
      "provider": "free",
      "capabilities": ["mesh_performance"],
      "cost_to_oddhobb": 0
    },
    {
      "provider": "fal",
      "capabilities": [
        "image_to_video",
        "lip_sync",
        "identity_video"
      ],
      "billing": "user"
    }
  ]
}
```

The agent can request:

> `quality = premium`

but it **cannot retrieve credentials**.

---

# This means the provider selector belongs to the compiler

Our Creative Revision should say:

```json
{
  "output": "video",
  "intent": {
    "identity_strength": "high",
    "photorealism": "high",
    "duration": 8
  }
}
```

Not:

```json
{
  "fal_model": "fal-ai/kling-whatever"
}
```

Then the router sees:

```text
requirements:
    video
    photoreal
    identity reference
    audio

available:
    free
    fal
    higgsfield

preference:
    user's providers first
```

and chooses:

```text
Higgsfield / Wan3 reference-to-video
```

tomorrow it might choose something else.

---

# I'd actually have four compute policies

The user/agent chooses an intent rather than a provider every time:

| Mode | What happens |
|---|---|
| **Free** | only OddHobb/open/deterministic stack |
| **Use mine** | connected providers allowed |
| **Best** | choose best connected model for task |
| **Specific** | advanced user says `Higgsfield → Wan 3` |

So Meta Muse could say:

> “I can make the regular animated version for free, or Tom has Higgsfield connected so I can make the photoreal version too.”

That's a very good UX.

---

# The free card/video pipeline is stronger than I initially framed it

For your sports card, the fully free path can actually be:

```text
Dad profile
     ↓
LLM joke/copy
     ↓
template
     ↓
Dad cutout / face crop
     ↓
sports scene background
     ↓
Konva/PIL/Canvas composition
     ↓
             CARD PNG/PDF
                  +
            FREAKTOWN stage
                  ↓
          Dad mesh / cutout puppet
                  ↓
             free TTS
                  ↓
        analyser jaw + gestures
                  ↓
          cameras + lower thirds
                  ↓
              WEBM/MP4
```

No generation API necessary.

Then:

```text
MAKE THIS PHOTOREAL
```

runs:

```text
same creative revision
        ↓
Higgsfield / fal / Alibaba
        ↓
new artifact
```

**Nothing upstream changes.**

That's exactly the architecture we want.

---

# And the mesh is arguably more fun than fake-real Dad anyway

This gives you two different products from the same joke:

### Real Dad

Photoreal sports interview.

### OddHobb Dad

His ridiculous little 3D character giving a serious post-match press conference.

The latter can be:

- deterministic
- extremely cheap
- reusable indefinitely
- much easier to animate consistently
- more recognizably OddHobb

So the free version isn't a crippled demo.

It's a **different aesthetic**.

---

# Freaktown should become a reusable package

Rather than copy-pasting its code into `pogpet`, extract the useful kernel:

```text
oddhobb-performance/
    audio/
        timeline
        compositor

    delivery/
        beats
        pauses
        prosody

    expression/
        jaw
        visemes
        gestures

    stage/
        cameras
        cues

    tts/
        registry
        edge
        qwen
```

Then:

```text
Freaktown
    uses performance kernel

OddHobb
    uses performance kernel

Pogtown
    uses performance kernel
```

Freaktown has already thought through the right abstractions — especially **TTS provider independence + exact audio timeline + motion compiler**.

We should take those rather than invent another performance stack.

---

# So the full OddHobb creative ladder becomes

```text
                        CREATIVE REVISION
                               │
            ┌──────────────────┼──────────────────┐
            │                  │                  │
            ▼                  ▼                  ▼

        FREE CARD          FREE VIDEO        FREE 3D
      deterministic        Freaktown           mesh
       composition         performer          renders
            │                  │                  │
            │                  │                  │
            └──────────────────┼──────────────────┘
                               │
                         premium button
                               │
              ┌────────────────┼──────────────┐
              ▼                ▼              ▼
          HIGGSFIELD          FAL          ALIBABA
          user's $$$       user's $$$      user's $$$
              │                │              │
              └────────────────┼──────────────┘
                               ▼
                      PREMIUM ARTIFACT
```

I think **this is substantially better than OddHobb buying generations itself**.

It means a Meta Muse user with no creative accounts can still make everything.

A power user with `$100` sitting in Higgsfield gets insane cards/videos.

A developer with their own GPU uses that.

And Muse sees exactly the same six OddHobb tools in every case.

The next code change I'd make is therefore **not Wan integration**. I'd first extract Freaktown's free performance kernel and build the `provider_connections + capability_router` abstraction around it. Once that boundary exists, Higgsfield/fal/Wan become tiny adapters rather than architectural decisions.
