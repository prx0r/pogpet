# Dev plan 2026-10-07 — OddHobb as the creative execution layer

Yes. The clean endgame is **not OddHobb becoming another AI assistant**. Muse/ChatGPT/Dot/etc. remain the conversational brain. OddHobb becomes the **creative execution layer** they can call.

That changes how Qwen, fal, Alibaba Cloud, Meshy, Blender, etc. should be wired.

## The end state

Someone says to Muse:

> “Make Dad a ridiculous Christmas card. Something about him falling asleep after dinner. And make a video version in his voice.”

Muse already knows who “Dad” is and may know the joke/context. Meta's connector programme is explicitly designed for this: your existing service becomes callable tools, with OAuth account linking; Meta supports onboarding from an API or MCP. [Meta Model API](https://dev.meta.ai/products/connectors?utm_source=chatgpt.com)

The flow should be:

```text
                    HUMAN
                      │
             "make Dad a card"
                      │
                      ▼
      MUSE / CHATGPT / DOT / OTHER AGENT
      knows conversational context + memory
                      │
                      │ OddHobb connector / MCP
                      ▼
              ODDHOBB CREATIVE API
                      │
             compile CreativeBrief
                      │
                      ▼
              TEMPLATE MATCHER
       occasion × style × scene × joke
                      │
                      ▼
            CREATIVE REVISION v1
          immutable structured scene
                      │
          ┌───────────┼───────────────┐
          ▼           ▼               ▼
       IMAGE        VOICE           MESH
       router       router          router
          │           │               │
   Qwen Image       Qwen VC        Meshy/Tripo
   Flux 3           Qwen TTS       Blender
   Muse Image       CosyVoice      existing GLB
          │           │               │
          └───────┬───┴──────┬────────┘
                  ▼          ▼
              VIDEO ROUTER   PRINT
               Wan 3.0       compositor
               Kling         PDF
               etc.
                  │
                  ▼
              QC + ARTIFACTS
        PNG / PDF / MP4 / GLB / audio
                  │
                  ▼
         MUSE RECEIVES RESULTS
                  │
         "These three are ready"
```

The personal agent **never needs to know what fal.ai is**.

It says:

> make this creative into a photoreal video

and OddHobb decides whether that means Wan 3.0, Kling, Qwen, Blender, or something released six months later.

That abstraction is essential.

---

# Qwen 3.8: two completely different uses

There is an important correction to the existing repo.

Your current `backend/qwen_voice.py` is **not actually Qwen 3.8 Realtime**. It currently calls the Hugging Face endpoint for `Qwen3-TTS-12Hz-0.6B-Base`.

I would replace that as the canonical path.

Alibaba now exposes **`qwen3.8-omni-flash-realtime`** directly. It accepts streaming audio, images and video, returns text/audio, supports WebRTC/WebSocket/AOQ, tool/function calls and remote MCP, and supports cloned voices. [ModelStudio Documentation](https://docs.modelstudio.console.alibabacloud.com/en/model-studio/realtime?utm_source=chatgpt.com)

But there are two use cases.

### When the user is talking to Muse

Don't put Qwen between Muse and the user.

Muse is already doing:

```text
speech
→ understanding
→ reasoning
→ conversation
→ OddHobb tool calls
```

Qwen is unnecessary there.

OddHobb uses Qwen **only to produce the creative artifact**, such as Dad's cloned voice track.

### When the user is talking directly to Oddy

Then Qwen 3.8 Omni Realtime is extremely relevant:

```text
browser mic
      │
      ▼
qwen3.8-omni-flash-realtime
      │
      ├── speaks naturally
      ├── sees uploaded images/video
      ├── understands interruptions
      └── calls OddHobb MCP tools
```

That could replace the Gemini-specific architecture currently described by `voice_chat.py`.

So refactor:

```text
voice_chat.py

RealtimeProvider
    ├── QwenOmniRealtimeProvider
    ├── GeminiLiveProvider
    └── StubProvider
```

Then **Oddy's tools are still the same OddHobb MCP tools used by Muse**.

No duplicated personal-shopper logic.

---

# Voice cloning specifically

Alibaba's current voice cloning is much cleaner than the HF hack you have.

They support cloning from roughly **10–20 seconds of audio**, creating a persistent voice identity that can then be used by TTS or Qwen Omni. [ModelStudio Documentation](https://docs.modelstudio.console.alibabacloud.com/en/model-studio/voice-cloning-user-guide?utm_source=chatgpt.com)

For Qwen 3.8 Omni:

```text
reference audio
      │
      ▼
qwen-voice-enrollment
target_model = qwen3.8-omni-flash-realtime
      │
      ▼
provider_voice_id
      │
      ▼
qwen3.8-omni-flash-realtime
speaks in that voice
```

The `target_model` used at enrollment has to match the Omni model later used to speak. [AlibabaCloud](https://www.alibabacloud.com/help/en/model-studio/qwen-omni-voice-cloning?utm_source=chatgpt.com)

But for your **pre-rendered Dad video**, I would *not* normally use Omni.

Use:

```text
Dad's voice sample
       ↓
qwen-voice-enrollment
       ↓
qwen3-tts-vc
       ↓
dad-line.wav
```

Alibaba currently exposes both realtime and non-realtime Qwen3 voice-cloning TTS variants; real-time synthesis supports streaming and cloned voices. [AlibabaCloud](https://www.alibabacloud.com/help/en/model-studio/realtime-tts-user-guide?utm_source=chatgpt.com)

That's more deterministic because you just want:

> “After a difficult first half, I think I handled the turkey magnificently.”

not an autonomous conversation.

So:

```text
LIVE CHARACTER / ODDY
    → Qwen 3.8 Omni Realtime

PREGENERATED CARD VIDEO SPEECH
    → Qwen3-TTS VC
```

And I would require an explicit voice-enrollment consent step before storing a cloned voice identity.

---

# The provider router is the core new subsystem

I would build:

```text
backend/creative/providers/
    base.py
    router.py

    alibaba/
        qwen_image.py
        qwen_voice.py
        qwen_realtime.py
        wan_video.py

    fal/
        client.py
        flux.py
        kling.py
        wan.py

    meta/
        muse_image.py
        sam.py

    mesh/
        meshy.py
        tripo.py
        blender.py
```

OddHobb code never says:

```python
fal.subscribe("fal-ai/...")
```

outside those adapters.

It says:

```python
providers.run(
    capability="identity_image",
    input=scene,
    quality="premium",
)
```

Then `router.py` resolves:

```yaml
identity_image:
  primary: alibaba.qwen_image_3_pro
  fallback: fal.flux_3_edit

image_edit:
  primary: fal.flux_3_edit
  fallback: alibaba.qwen_image_3_pro

video_scene:
  primary: alibaba.wan_3
  fallback: fal.wan_3

lip_sync:
  primary: fal.kling_lipsync

voice_clone:
  primary: alibaba.qwen_voice_enrollment

cloned_tts:
  primary: alibaba.qwen3_tts_vc

realtime_character:
  primary: alibaba.qwen3_8_omni

mesh:
  primary: meshy
  fallback: tripo
```

Models will change constantly.

**Capabilities shouldn't.**

---

# Where fal.ai is useful

fal should be your **creative model supermarket**, not your architecture.

For example, the current FLUX 3 Image Edit endpoint can accept up to 10 references and perform local edits while retaining other aspects of a composition. That is useful for something like:

```text
reference 1 = Dad
reference 2 = sports outfit
reference 3 = OddHobb sideline template
→ Dad being interviewed pitch-side
``` :chatgpt-content-reference{index="5"}


For less expensive iterative editing you also have FLUX Kontext variants. :chatgpt-content-reference{index="6"}

The output should still be a **scene plate**, though.

Don't ask Flux to render:

> POST MATCH INTERVIEW  
> Dad reflects on turkey performance

You generate the photographic portion:

```text
reporter + Dad + stadium + microphone
```

and OddHobb deterministically lays the broadcast typography over it.

That makes captions editable and printable.

---

# And fal is useful for lip sync

Suppose we've already made:

```text
dad_press_conference.mp4
```

and Qwen produces:

```text
dad_voice.wav
```

Then:

```text
video + cloned audio
       ↓
Kling LipSync on fal
       ↓
speaking Dad
```

fal's current Kling Audio-to-Video lip-sync endpoint takes an existing video plus audio and produces synchronized mouth motion. [Fal](https://fal.ai/models/fal-ai/kling-video/lipsync/audio-to-video/api?utm_source=chatgpt.com)

That means voice and video remain decoupled.

That's desirable.

If Kling gets beaten by something else next month, swap one adapter.

---

# Alibaba's Wan stack may remove several stages

Alibaba now has **Wan 3.0**, and it is much more interesting for OddHobb than the older Wan paths.

Current Wan 3 supports:

- text, image, video and audio references
- text-to-video
- image-to-video
- reference-based video
- first/last-frame control
- up to 30 seconds
- native dialogue/BGM/SFX
- up to 20 multimodal references. [ModelStudio Documentation](https://docs.modelstudio.console.alibabacloud.com/en/model-studio/wan3-video-generation-guide?utm_source=chatgpt.com)

And their reference-to-video path is specifically designed to preserve characters and voices across scenes. [AlibabaCloud](https://www.alibabacloud.com/help/en/model-studio/video-to-video-guide?utm_source=chatgpt.com)

So eventually this:

```text
Dad photos
Dad voice
sports template reference
script
       │
       ▼
Wan 3
       │
       ▼
finished press-interview video
```

might outperform:

```text
image
→ video
→ TTS
→ lipsync
```

But I would support **both pipelines**.

The compiler chooses based on quality tests.

---

# And Qwen Image is worth routing directly too

Alibaba's current Qwen Image 3.0 supports generation and editing, and the Pro version is aimed at photorealism, complex layouts and strong text/render adherence. [AlibabaCloud](https://www.alibabacloud.com/help/en/model-studio/image-model/?utm_source=chatgpt.com)

I would benchmark:

```text
qwen-image-3.0-pro
vs
fal Flux 3 Edit
```

on exactly 50 OddHobb tasks:

```text
Dad → sports interview
Dad → news desk
Dad → Santa press conference
Mum → award ceremony
pet → investigation board
2 people → TV interview
etc.
```

Score:

```text
identity
pose
scene adherence
hands
photorealism
latency
cost
```

Then let the router choose from empirical OddHobb data.

That becomes another **Data Garden**, effectively.

---

# Alibaba Cloud should orchestrate jobs, not contain business logic

Function Compute is excellent for the thin workers. It's event-driven and ephemeral, so you pay while functions actually execute. [AlibabaCloud](https://www.alibabacloud.com/help/en/functioncompute/what-is-function-compute?utm_source=chatgpt.com)

But don't shove the whole creative state machine into one Lambda-like function.

Use:

```text
CloudFlow
  = orchestration

Function Compute
  = workers

SMQ
  = job queue / backpressure

OSS
  = temporary provider media / artifacts

OddHobb DB
  = canonical truth
```

CloudFlow is Alibaba's managed state-machine/workflow service; it handles sequential, parallel and conditional execution and can invoke Function Compute or even third-party HTTP endpoints. [AlibabaCloud](https://www.alibabacloud.com/help/en/serverless-workflow/latest/integrated-function-compute?utm_source=chatgpt.com)

So a real render could be:

```text
RenderBundle
    │
    ├── ResolveAssets
    │
    ├── parallel
    │      ├── MakePhotorealPlate
    │      ├── MakeMeshPoster
    │      └── PrepareVoice
    │
    ├── ComposeCard
    │
    ├── QCPrint
    │
    └── if video_requested
           │
           ├── GenerateVideo
           ├── LipSync if needed
           ├── AddLowerThird
           └── QCVideo
```

Long fal jobs shouldn't hold an FC instance open.

fal explicitly recommends submitting long jobs to its queue and using **webhooks** rather than blocking. [Fal](https://fal.ai/models/fal-ai/kling-video/lipsync/audio-to-video/api?utm_source=chatgpt.com)

So:

```text
FC submits fal job
      ↓
CloudFlow pauses
      ↓
fal renders for 3 minutes
      ↓
fal webhook → FC
      ↓
FC validates webhook
      ↓
CloudFlow callback resumes
```

CloudFlow has a `waitForCallback` pattern specifically for this sort of asynchronous task. [AlibabaCloud](https://www.alibabacloud.com/help/en/serverless-workflow/latest/task-steps?utm_source=chatgpt.com)

That's the correct infrastructure.

---

# Keep R2; don't rewrite storage immediately

You already have a functioning R2 asset system.

Don't migrate everything to OSS because Alibaba exists.

I'd introduce:

```text
CanonicalAssetStore
    = R2

ProviderStagingStore
    = OSS Singapore
```

When Wan/Qwen needs a URL:

```text
R2 asset
→ temporary OSS object
→ signed URL
→ Model Studio
→ output to OSS
→ ingest canonical result into R2
```

Later, if Alibaba becomes 90% of your compute, you can change which one is canonical.

The scene/data model doesn't care.

---

# The agent-facing API should shrink dramatically

Your MCP currently exposes ~57 tools.

That's useful for development.

It's bad for Muse.

Muse should see perhaps **six high-level tools**:

```text
oddhobb_people()
oddhobb_ideas(person, occasion, request)
oddhobb_create(idea, overrides)
oddhobb_render(creative, outputs)
oddhobb_status(job)
oddhobb_buy(creative, product)
```

Internally:

```text
oddhobb_create()
```

might execute fifteen operations.

Muse doesn't care.

Meta's connector system is explicitly designed around exposing a service's existing API as a small number of callable actions, with OAuth linking the user's service account. [Meta Model API](https://dev.meta.ai/products/connectors?utm_source=chatgpt.com)

And MCP-capable agent runtimes can hit the same backend; Meta's own Muse Code supports remote MCP and OAuth sign-in. [Meta Model API](https://dev.meta.ai/docs/muse-code/extending?project_id=1775916636764246\&team_id=1331104075427093\&utm_source=chatgpt.com)

So one service definition powers:

```text
ChatGPT
Meta AI / Muse Connector
Muse Code
Claude
OpenCode
Oddy
future agents
```

---

# The really cool bit: agent memory becomes creative input

Suppose Muse knows:

```text
Dad
- Liverpool supporter
- falls asleep after Christmas lunch
- thinks he is good at golf
- hates coriander
- calls the dog "the management"
```

Muse should **not upload its entire memory into OddHobb**.

It sends only relevant context:

```json
{
  "recipient": "Dad",
  "occasion": "christmas",
  "context": [
    {
      "fact": "falls asleep after Christmas lunch",
      "source": "agent_memory"
    },
    {
      "fact": "Liverpool supporter",
      "source": "agent_memory"
    }
  ]
}
```

OddHobb combines that with its own graph:

```text
Dad
 ├── 19 photos
 ├── 2 meshes
 ├── voice enrolled
 ├── prior cards liked
 └── previous joke ratings
```

Then the matcher says:

```text
#1 SPORTS PRESSER
"Post-match interview after Dad survives Christmas lunch"
score 0.94

#2 NEWS PARODY
"Local man enters sixth hour of festive nap"
score 0.91

#3 SANTA PRESS CONFERENCE
"Santa denies responsibility for Dad's annual shutdown"
score 0.86
```

That is the actual OddHobb moat.

Not the image model.

**The model can be swapped. The personal graph + template graph + response history compounds.**

---

# The same scene creates all the products

This remains the most important bit.

Muse picks:

```text
creative_8f3
Dad
Christmas
sportspresser
post_match_interview
"Christmas lunch knocked me out in the second half"
```

Then:

```text
creative_8f3
    │
    ├── greeting-card.pdf
    ├── card-front.png
    ├── whatsapp-share.jpg
    ├── Dad-photoreal.mp4
    ├── Dad-mesh.mp4
    ├── poster.png
    └── maybe physical desk figure
```

One joke.

One scene.

One recipient.

Many renderers.

---

# What I'd change in `pogpet` now

The first implementation pass should not be another frontend feature.

Refactor the backend around:

```text
backend/creative/
    brief.py
    templates.py
    matcher.py
    revisions.py
    compiler.py
    jobs.py
    artifacts.py
```

Then specifically retire the current fake "Qwen realtime" path:

```text
backend/qwen_voice.py
HF Qwen3-TTS
```

into something like:

```text
providers/alibaba.py

enroll_voice()
tts_cloned()
open_realtime_session()
generate_image()
edit_image()
generate_video()
```

Keep the HF route only as an optional local/cheap fallback.

Then make existing:

```text
cards
videos
perform
mesh
```

**consumers of the Creative Revision system**, instead of four semi-independent systems.

That gets you to the actual product:

> **Any personal AI agent can hand OddHobb a person + intent, and OddHobb autonomously turns that into personalized physical and digital media using whichever creative models are currently best.**

That is much larger than a personalised-card site.
