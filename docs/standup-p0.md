# P0 standup — dog, lips, face, vertical, mic

> Status: PIPELINE LIVE (2026-10-02). Spec + implementation.
> Goal: **the dog does stand-up** — voice, mouth moving, face alive, vertical
> 9:16, speaking into a microphone. Not a black card with a still.

## What we learned (freaktown + lipsync landscape)

### Freaktown (local, read-only research)

| Layer | Freaktown pick | Applies to us? |
|---|---|---|
| Script | 60s standup minute (LLM / fixed) | **Yes** — same brief |
| Voice | **edge-tts** free, keyless | **Yes** — already wired |
| Mouth | Web Audio analyser → VRM visemes / `jawOpen` | **Yes in spirit** — energy → jaw |
| Mesh truth | Sniff morphs; no mouth → body-only | **Our GLB has 0 morph targets** |
| Stage | 4 cameras, one audio timeline | Later |
| GPU lip models | SadTalker / Wav2Lip / bitHuman | **Not on this box** (no CUDA, ~10G disk) |

Freaktown doctrine (`packages/stage-runtime/src/LipSync.ts`):
1. Detect what the avatar can do (`viseme` / `jaw` / `none`).
2. Every mouth listens to **audible** voice energy.
3. Mouth channel never fights blink / emotion channels.

### Adjacent open-source (for later / GPU lane)

| Tool | Need | Verdict here |
|---|---|---|
| **Wav2Lip** | CUDA GPU | Best sync accuracy — cloud/Kaggle later |
| **SadTalker** | CUDA + ~8GB | Full head motion from 1 photo — GPU later |
| **MuseTalk / LatentSync / LivePortrait** | heavier GPU | Quality ceiling later |
| **wawa-lipsync** | browser, morph targets | Needs visemes on the mesh |
| **talk2avatar / DLP3D** | VRM + morphs | Our dog GLB is not VRM |

**P0 decision:** ship a **CPU standup** that feels like a performance:
edge-tts voice + **audio-envelope mouth** on a polished vertical frame +
stage set + mic + name plate. True neural lipsync is P1 on a GPU box.

## P0 product shape

```
standup script (dog minute)
    → edge-tts (ryan / andrew) → set.wav
    → audio envelope (RMS, smoothed)
    → frames 1080×1920:
         warm white stage (NOT black)
         dog still (canonical mesh render) with subtle bob/zoom
         mouth open/close driven by envelope
         mic prop + name plate + optional laugh line
    → ffmpeg mux → vertical mp4
    → videos feed (swipe tab)
```

## Non-negotiables

1. **No black feed cards** — stage is warm white / paper.
2. **Mouth must move with the words** — envelope, not a static open mouth.
3. **Mic in frame** — standup, not a portrait.
4. **Same dog mesh** as products/studio — one character.
5. **0 Meshy credits** — no new sculpts for P0.

## P0 decision: YES — lipsync without GPU (freaktown path)

Freaktown already solved this. Two layers:

1. **Mesh must declare a mouth.** `basic_body.py` emits a GLB with a
   **`jawOpen` morph target** (`extras.targetNames: ["jawOpen"]`). Caps:
   `lipsync: true`. Our Meshy chibi had **0 morphs** — that's why it felt dead.
2. **Browser drives the morph from Web Audio.** `packages/stage-runtime/src/LipSync.ts`
   + `AudioBus` analyser: energy → `jawOpen` (or visemes aa/ih/ou if present).
   CPU/Web Audio only. Stage CSS mouth is the 2D fallback (`stage/app.js`).

### What we built on oddhobb

| Piece | Path |
|---|---|
| Inject `jawOpen` into the dog GLB | `scripts/add_jaw_morph.py` → `data/uploads/chibi-figure-hook-jaw.glb` |
| Live stage page (play clip, mouth moves) | `https://oddhobb.com/stage.html` |
| Offline bake (mesh jaw + audio in mp4) | `scripts/p0_standup_morph.py` (Blender shape key ← envelope) |

**Not needed for P0:** Wav2Lip / SadTalker / any GPU. Those are P1 quality upgrades
(photoreal mouth) on a CUDA box — not required for a moving jaw on our mesh.

### Later (P1+)

- GPU lipsync (Wav2Lip/SadTalker) for photoreal mouth on dog stills
- Full viseme set (aa/ih/ou/ee/oh) on future Meshy builds — freaktown sniff path
- Live browser stage wired into the Videos tab as the default player
- Multi-cam cuts, walkout sting, Ella-style judge cards
