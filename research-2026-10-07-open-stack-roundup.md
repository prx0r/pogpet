# Research 2026-10-07 — open-stack roundup for OddHobb

Yes. I searched the last month specifically, plus the two projects you linked. There has been a pretty major convergence toward exactly this OddHobb idea.

The strongest architecture I see now is **capture once → extract a reusable person/world model → deterministic free creation → optional generative upgrade**.

### The genuinely important recent stuff

**1. Qwen 3.8 Omni is probably the best “capture interpreter” right now.** Alibaba updated `qwen3.8-omni-flash` and `qwen3.8-omni-flash-realtime` on September 28. The non-realtime model accepts text, image, audio and video, has a 1M-token context window, and is explicitly positioned for audio/video understanding and content analysis. The realtime variant takes streaming audio plus video frames, outputs speech/text, supports function calling, and can directly call remote MCP tools. [AlibabaCloud](https://www.alibabacloud.com/help/en/model-studio/qwen3-8-omni-flash?utm_source=chatgpt.com)

That makes the split extremely clean:

```text
20–30 sec PERSON CAPTURE
        │
        ├─ qwen3.8-omni-flash
        │      deep offline analysis
        │
        └─ qwen3.8-omni-flash-realtime
               guided live capture / Oddy conversation
```

For OddHobb I'd have Qwen extract a structured **Person Manifest**, not prose:

```text
identity refs
voice regions
transcript
facial expressions + timestamps
gestures + timestamps
posture
speaking cadence
humour/delivery tendencies
best front/¾/profile frames
full-body frames
interesting motion clips
objects/clothes
capture quality scores
```

It is more compelling after seeing **OmniAgent**: its active-video-perception work was incorporated into Qwen 3.8 Omni in September. Instead of blindly ingesting every frame, it can actively inspect frames, audio or clips when useful. [GitHub](https://github.com/harryhsing/omniagent?utm_source=chatgpt.com)

So yes: **Qwen 3.8 changes this project materially.**

---

**2. Qwen's new MM Plugins repo is almost freakishly aligned with OddHobb.**

In September alone Qwen added:

- `omni-memory` — audiovisual memory over long videos, including speakers, dialogue, sounds and events
- `omni-skill-creator` — turns a demonstration video into a reusable agent skill
- `video-spatio` — 3D spatial reasoning over image/video
- video editing and native 3D/Blender tooling already existed. [GitHub](https://github.com/QwenLM/Qwen-MM-Plugins?spm=a2ty_o06.30285417.0.0.576cc921NGk97S)

The `omni-skill-creator` idea is particularly wild.

Imagine the capture isn't merely:

> what does Dad look/sound like?

It also learns:

> **how Dad does things.**

Dad demonstrates:

```text
wave
shrug
golf swing
dance
point
laugh
"his thing"
```

and those become reusable behavioural assets:

```text
person/dad/
    appearance
    voice
    memories
    motions
    skills/
        dad_shrug
        dad_wave
        dad_golf_swing
```

That's much closer to a reusable **person compiler**.

---

**3. AnyID is almost exactly the premium video problem.**

This only just surfaced publicly as a preview. It is an identity-preserving video system from researchers at Xi'an Jiaotong, Alibaba Cloud and Tsinghua that can use **faces, portraits or an entire video clip** as identity references. It accepts either up to five images or one video reference and targets stable identity across angles and expressions. [GitHub](https://github.com/JoHnneyWang/AnyID)

So:

```text
Dad capture.mp4
        +
"Dad giving a ridiculous post-match interview"
        ↓
AnyID-like generation
```

is literally the research direction.

Important catch: the released AnyID weights are **CC BY-NC-SA**, so I would not ship those weights commercially in OddHobb. [GitHub](https://github.com/JoHnneyWang/AnyID)

But architecturally this confirms the thesis:

> **raw capture video itself should remain a first-class identity reference.**

Don't throw it away after extracting stills.

---

**4. World Tracing got stronger object + dynamic checkpoints on September 23.**

World Labs' `World Tracing` predicts layered 3D geometry from images, including partially occluded surfaces, and its September update includes a **dynamic 16-frame model** alongside object and scene checkpoints. [GitHub](https://github.com/haoz19/world-tracing)

This is interesting because our capture bundle shouldn't assume:

```text
video → Meshy → GLB
```

There should really be intermediate spatial representations:

```text
frames
 ↓
depth / layered XYZ
 ↓
body / object scaffold
 ↓
mesh OR gaussian OR point representation
```

Then different outputs consume whichever representation they actually need.

---

### The project you linked — `image-blaster` — is extremely relevant

I checked `neilsonnn/image-blaster`.

Its important contribution isn't a particular model. It's the **agentic creative-pipeline pattern**:

```text
ONE IMAGE
   ↓
agent analyzes it
   ↓
clean plate
   ↓
World Labs Marble → static Gaussian-splat world
   ↓
Hunyuan → movable GLB objects
   ↓
SFX generation
   ↓
interactive 3D environment
```

It outputs `.glb`/`.obj` dynamic objects, `.spz` Gaussian-splat backgrounds and generated sound. [GitHub](https://github.com/neilsonnn/image-blaster?utm_source=chatgpt.com)

That is almost exactly how I think OddHobb should work, except our primitive is:

> **one person capture**

rather than:

> one environment image.

So I'd explicitly copy its philosophy:

```text
oddhobb-person-blaster

20 sec clip
   ↓
ANALYSE
   ↓
├─ identity references
├─ voice profile
├─ motion clips
├─ mannerism manifest
├─ face/head avatar
├─ printable mesh
├─ digital avatar
└─ creative profile
```

And like Image Blaster, **the orchestrator is replaceable**. It happens to use Claude skills; OddHobb's pipeline should work when triggered by Muse, ChatGPT, Gemini, Qwen, etc.

---

# The other link may be even more consequential: `storytold`

I checked the organization properly. These repositories are being developed **right now** — PhotoCraft had commits today, FilmCraft yesterday, EffectCraft today, DesignCraft yesterday.

They have built an extraordinarily relevant open-source creative stack:

| Project | Basically |
|---|---|
| PhotoCraft | Photoshop |
| FilmCraft | Premiere |
| EffectCraft | After Effects |
| DesignCraft | InDesign |
| VectorCraft | Illustrator-ish |
| LightCraft | Lightroom-ish |

And the architectural bit that matters for OddHobb:

> **every operation is agent-drivable.**

PhotoCraft's engine can be controlled through UI, CLI, JSON control channel or MCP, and compiles to WebAssembly. [GitHub](https://github.com/storytold/photocraft?utm_source=chatgpt.com)

FilmCraft exposes its timeline, colour, effects and export engine through commands, JSON and MCP. [GitHub](https://github.com/storytold/filmcraft?utm_source=chatgpt.com)

EffectCraft is effectively an open After Effects-like compositor with layers, keyframes, 306 effects, text, 3D cameras, motion graphics, Lottie, H.264/ProRes/HEVC/AV1 export — and an MCP server. [GitHub](https://github.com/storytold/effectcraft?utm_source=chatgpt.com)

This changes one recommendation I made earlier.

### I wouldn't rush to Polotno anymore.

I would seriously prototype the Storytold stack as the **free deterministic rendering backend**.

Imagine:

```text
                CREATIVE REVISION
                        │
        ┌───────────────┼───────────────┐
        ▼               ▼               ▼
   PhotoCraft       DesignCraft     EffectCraft
   image layers     card layout     animation
        │               │               │
        └───────────────┼───────────────┘
                        ▼
                    FilmCraft
                final video assembly
```

All four are agent-addressable.

That is remarkably close to an **open Adobe Creative Cloud designed for AI agents**. [GitHub](https://github.com/storytold?utm_source=chatgpt.com)

For OddHobb, that's more interesting long-term than embedding Canva.

---

# Free voice got substantially better too

`OmniVoice Studio` is worth stealing ideas/code patterns from.

It currently advertises:

- ~3-second zero-shot voice cloning
- 646 languages
- fully local operation
- CUDA / Apple Silicon / ROCm / CPU
- multiple interchangeable TTS engines
- video dubbing
- speaker diarization
- an **MCP server**. [GitHub](https://github.com/Galest/OmniVoice-Studio)

This fits the BYOC/free strategy perfectly.

Instead of OddHobb owning one voice model:

```text
voice_clone capability
    │
    ├─ user's local OmniVoice
    ├─ self-hosted Qwen
    ├─ Alibaba Qwen
    ├─ ElevenLabs BYOK
    └── future provider
```

Again: capabilities, not vendor names.

---

# Talking avatars are getting cheap enough that Freaktown's approach is validated

Two current projects caught my eye.

`TA2.0` takes:

```text
reference image
+
speech audio
+
optional prompt
→ expressive lip-synced video
```

and released an auditable inference runtime. [GitHub](https://github.com/neosapience/ta2-0)

But even more interesting for the **free** OddHobb path is `buildfastwithai/talking-avatar`. It deliberately avoids generating the whole face. It makes three tiny mouth states and drives them directly from the actual audio stream. [GitHub](https://github.com/buildfastwithai/talking-avatar)

That's basically the 2D version of what we already did in Freaktown:

```text
audio
→ envelope
→ mouth state / jaw morph
```

So I think the architecture was correct.

We should have:

```text
FREE 2D
mouth sprites

FREE 3D
mesh morph targets / visemes

LOCAL GPU
TA2.0

BYOC PREMIUM
Wan / Kling / Higgsfield / whatever wins
```

---

# Gemini also had a significant release this month

Google released **Gemini 3.8 Live** on September 15, plus a Live Extended Thinking variant. The latter can reason in the background during live audio interaction. [Google AI for Developers](https://ai.google.dev/gemini-api/docs/changelog)

So for the guided capture experience I'd benchmark:

```text
Qwen 3.8 Omni Realtime
vs
Gemini 3.8 Live
```

rather than hard-code either.

But Qwen currently has the architectural edge for us because its realtime model explicitly supports **video input + remote MCP** in the same session. [AlibabaCloud](https://www.alibabacloud.com/help/en/model-studio/qwen3-8-omni-flash-realtime)

That means Oddy could literally watch:

> “Turn your head a little… good. Step back… perfect. Say something naturally. Nice, I've got your voice. Give me your most Dad-like shrug.”

while simultaneously calling:

```text
oddhobb.capture_mark()
oddhobb.subject_update()
oddhobb.finish_capture()
```

That is a much better onboarding experience than an upload form.

---

# So I would update the OddHobb architecture again

The top-level object becomes **Person Capsule**, not merely Person Profile.

```text
PERSON CAPSULE
│
├── identity/
│   ├── canonical face refs
│   ├── profile refs
│   ├── body refs
│   └── raw capture video
│
├── voice/
│   ├── clean reference
│   ├── voice profile
│   └── clone providers
│
├── behaviour/
│   ├── mannerism manifest
│   ├── gestures
│   ├── expressions
│   ├── motion tracks
│   └── learned skills
│
├── spatial/
│   ├── geometry scaffold
│   ├── digital avatar
│   └── printable meshes
│
├── knowledge/
│   ├── interests
│   ├── relationships
│   ├── memories
│   └── jokes / preferences
│
└── provenance/
    ├── observed
    ├── inferred
    ├── supplied_by_agent
    └── generated
```

And then this becomes the input to **every OddHobb template**.

---

## The stack I'd prototype now

If I were building it this week, I'd use:

1. **Qwen 3.8 Omni** for capture understanding.
2. **Qwen MM `omni-memory`** patterns for extracting persistent audiovisual observations.
3. **Freaktown's performance timeline** for free character animation.
4. **OmniVoice/Qwen TTS** as the free/self-host voice layer.
5. **World Tracing / Hunyuan / Meshy** behind a `geometry` capability.
6. **PhotoCraft + EffectCraft + FilmCraft** as deterministic agent-driven postproduction.
7. **Image-Blaster's agentic pipeline design** as the model for asset compilation.
8. **AnyID-style video-reference generation** as the premium identity-video path — but not its current noncommercial weights.
9. **fal/Higgsfield/Alibaba BYOC** for anything expensive.

The surprising discovery from this search is that **the open/free deterministic half has become much stronger than I thought**. Between Freaktown + Storytold + local voice + Qwen's agent tooling, OddHobb can own the *entire orchestration and finishing pipeline* without paying a generation provider. Paid models then become optional render accelerators/upgrades, rather than dependencies.
