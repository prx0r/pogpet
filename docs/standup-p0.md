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

## Later (P1+)

- GPU lipsync (Wav2Lip/SadTalker) on dog front stills
- Morph targets on future Meshy builds (freaktown sniff path)
- Live browser stage (model-viewer + Web Audio jaw) like freaktown
- Multi-cam cuts, walkout sting, Ella-style judge cards
