# UniMate — spec for the live site (planned, not built)

> **Status: SPEC ONLY.** Nothing here is wired up. Clone lives read-only at
> `/home/ubuntu/refs/UniMate` (MIT, shallow). Sourced 2026-09-30.

## What it is

**UniMate** — *One Unified Model to Animate Diverse Skeletons* (SIGGRAPH Asia 2026,
Princeton/Berkeley/MIT/NTU). Official code: `github.com/Friedrich-M/UniMate` (★603, MIT),
paper `arXiv:2609.05415`, preview checkpoints on HuggingFace `Linzhan/UniMate`, dataset
`UniML3D` (13,006 text-paired motions: biped, quadruped, avian, marine, insectoid,
serpentine, articulated objects).

Feed it a **rigged** asset + a text prompt → it produces an articulated motion for that
skeleton. No per-character fine-tuning, no test-time optimization. Also does zero-shot
**in-betweening, expansion and text-guided editing**. Model: topology-aware diffusion
transformer (flow matching), so it is a GPU workload.

## Why we want it (the stage layer)

Today `comedy_show` / `comedy_set` / `video` / `ar_show` play **pre-baked clips**
(freaktown acts, edge-tts + ffmpeg). With UniMate a customer's pet gets its own motion:

> *"wags tail, barks at the camera"* · *"happy birthday wiggle"* · *"chases its tail"*

- **Personalized motion per order** — unlimited acts, no clip licensing.
- **Cross-topology** — dog/cat/bird rigs all work from one model; exactly our product set.
- **Economics that work:** motion is generated *for a skeleton*, not a mesh — one generated
  quadruped motion can be **reused across every dog** in the catalogue (retarget + cache),
  so inference cost amortizes over customers, not per customer.
- Editing/expansion stretches a 2 s motion to fill a 20 s clip or loops it cleanly.

## Requirements (the blockers)

1. **A rig.** Our Meshy output is an unrigged mesh. Paths: Meshy Animation API /
   auto-rig (**costs credits — ask first**), or a Blender rigging path (manual, not
   per-order scalable).
2. **GPU.** Repo pins CUDA 12.4 / torch 2.5.1 (`requirements.txt`); the box is 6 vCPU,
   no GPU. Inference needs a hosted endpoint (HF Inference / fal / GPU rental —
   **costs money, ask first**) or a local GPU we don't have.
3. **Env quirk:** their stack pins Python 3.10 + `bpy==4.0.0` for export/render — but
   their own requirements note export/animate can run via `blender -b -P` instead,
   which fits our Blender 4.2.9 CLI.
4. **Checkpoints:** preview weights on HF `Linzhan/UniMate` (more coming).

## Integration plan (phased, gated on spend)

| Phase | What | Cost |
|---|---|---|
| **0. Eval** | Play with their [interactive demo](https://linzhanmou.com/unimate/interactive.html); check checkpoint size/licence on HF; decide hosted vs skip | free |
| **1. Proof** | One quadruped mesh → rig → `scripts/run_sample_motion_text.sh` equivalent with prompt `"wags tail happily"` → render with our stack → compare against current acts | GPU time + rig credits (ask) |
| **2. Service** | Hosted endpoint behind our own client; **motion cache** keyed by `(topology, prompt)`; retarget cached motions onto each customer's skeleton | hosted GPU $/call (ask) |
| **3. Live** | New route alongside `POST /api/videos`: prompt library per product, cache in `data/motions/`, watermark rules reused, credit/limits like `FREE_DAILY["video"]` | marginal per render only |

## What it does NOT solve

- **Rigging stays ours** (Meshy or Blender) — UniMate takes a rig as input, it doesn't make one.
- **Stylized proportions:** a chibi body (huge head, stub legs) won't move like the
  quadruped training data — expect a retarget/scale pass and eyeballing per product type.
- **Licences:** code is MIT ✓. **Model checkpoint licence must be read on the HF card before
  commercial use.** The `UniML3D` raw data includes Truebones assets that **may not be
  redistributed** — we never ship the dataset, only generated motions.
- Not a substitute for the free tier's current pipeline until Phase 1 proves quality.

## Near-term alternative

Meshy's own **Animation API / auto-rig + preset motions** gives rigged pets and stock
animations cheaply and on the credits we already have — UniMate is the *custom-prompt*
upgrade over that, not the first step to it.
