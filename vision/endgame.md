# Endgame: the autonomous creative factory (founder research, verbatim 2026-10-10)

> OddHobb × Pogtown × FinalBuilds2. Keep Jev; no Unsloth fine-tuning.
> The vision is bigger than an AI agent that makes products or videos:
> an experimental system that discovers ideas, generates competing
> approaches, builds the thing, publishes authorised experiments, measures
> real behaviour, learns which creative mechanisms work, and reinvests it.
> Learn processes, not outputs.

## 1. The two repos sent

**mrsarac/ff-tracking** — procedural filmmaking experiment, highly
relevant for video production: a virtual camera films a simulated AI
terminal, tracking individual glyph positions, with physically inspired
lens effects and synchronised sound. Built with Rust, fframes, Skia/SkSL
shaders and generated audio. Its shared timeline of precise visual events
(driving animation, camera focus, effects, sound) translates directly to
Pogtown's joke beats, character reactions, cuts and sound cues. Caveat:
renderer targets macOS Apple Silicon/Metal — on our Linux VPS reuse the
architectural ideas or port the rendering, don't assume it works directly.

**amathislab/terra** — longer-term relevance: biomechanics/robotics,
recorded human movement → musculoskeletal trajectories, terrain
reconstruction, PPO control policies. Characters that move with physical
consistency instead of switching generated clips (robot comedian walking
onstage, recovering from a stumble, acting out a story). Not plug-and-play:
specialist assets, GPU training, noncommercial/restricted licences on
dependencies and motion data. Research reference, not the commercial
pipeline.

## 2. More repositories worth investigating (2026 releases, active)

| Repo | Unlocks | Priority |
|---|---|---|
| fframes | Fast Rust/SVG video rendering, agent inspection, snapshot tests, audio QC, browser timeline. Linux Vulkan supported. | P0 |
| YouTube Analytics MCP | Official owner-channel analytics, retention curves, search terms, CTR, performance comparisons. | P0 |
| ff-unmute | Procedural soundtracks where camera/effects respond to audio measurements. Joke/physical-comedy timing. | P1 |
| FirstFrame | Progressive rendering, early approval/rejection, streamed previews, asset lineage. Middle-canvas review vision. | P1 |
| lipsync-engine | Lightweight streaming visemes, SVG/Canvas. Animated characters, Oddy. | P1 |
| NVIDIA Kimodo | Controllable human motion from text/keyframes/spatial constraints (Mar 2026). | P1 research |
| NVIDIA ARDY | Real-time text-directed character motion (Jul 2026). Live Pogtown characters. | P1 research |
| ardy2bvh | ARDY motion → BVH/FBX for Blender/Unity/Unreal. | P1 research |
| MotionMind | Video → 3D body motion → rigged avatar, semantic motion library, Gemini Live. Promising, small, unproven. | Experimental |
| Agentic Video Editor | Hook detection, timeline, QC, approval, publishing, analytics architecture. Reference, unvalidated. | Study |
| Meta SPIDER | Physics-informed motion transfer to hands/humanoids (Sep 2026 data; noncommercial). | Research |
| yt-analytics-mcp | Smaller read-only analytics, excellent same-age episode comparisons. | P0 alternative |

Three discoveries: **fframes** (reproducible testable render pipeline, not MP4 piles), **ARDY** (request actions like walk onstage / wave awkwardly / collapse into chair; needs retargeting, cleanup, GPU), **FirstFrame** (first viewable frame 9.3s vs 65.7s full — review scene one while later scenes build; reject bad takes before spending). Combine selectively: Jev chooses, creative agents write, specialised renderers produce, verified analytics inform.

## 3. FinalBuilds2 is closer than expected

Existing capabilities (from the operations manual; represented in repo, not independently verified production-ready): idea research + scoring, autonomous worktree builders, independent verification + promotion, append-only event/lineage graph, deterministic experiment assignment, process-to-outcome attribution, hypothesis evolution policy, creative production/distribution adapters (to integrate), closed-loop audience optimisation (to validate). Key files: `src/experiments/engine.js` (control/treatment assignment), `src/analytics/process-attribution.js` (outcomes → processes, observational vs causality), `docs/HYPOTHESIS-EVOLUTION-POLICY.md` (promote on out-of-sample prediction, calibration, independent evidence). Expand the unit of work beyond software: products, campaigns, episodes, performances, creative experiments.

## 4. One OS, two factories

- **FinalBuilds2**: research · hypotheses · lineage · experiments · allocation.
- **Jev + qprivately**: decisions · verified gates · execution grants · receipts.
- **OddHobb** (commercial factory): demand research → design → mesh/print verification → pack → listing → Influence campaigns → sales.
- **Pogtown** (creative factory): trend research → JokeBlocks → characters → scripts → animation → YouTube → audience response.
- **Shared ledger**: results → comparisons → hypothesis updates → next experiments.

Strict boundaries: FinalBuilds2 owns experiment lifecycle + lineage; Influence owns brand marketing + distribution; pogpet owns product truth, print artifacts, fulfilment; Freaktown/Pogtown own characters, JokeBlocks, episodes; qprivately owns proof semantics, grants, audit; Jev decides, never the source of truth. No repo grows its own second manager/scheduler/experiment-store/verifier.

## 5. Pogtown as humour science

Every episode a formal experiment with a declared humour theory.
Example No-Nose Nolan NOLAN-007: hypothesis — characters interpreting
laughter as competence-confirmation drive stronger repeat viewing than
characters recognising incompetence. Arm A (self-awareness, control) vs
Arm B (misinterpreted success, treatment); constants: character, voice,
duration, setting, style, release, thumbnail. Measure: 30s retention,
average % watched, rewatches, shares, repeat-character engagement,
normalised by age/source. Retain/revise/reject with uncertainty. Hundreds
of such experiments teach the character graph mechanism-level lessons
(e.g. overconfidence-after-failure works when sincere, fails when already
arrogant) that feed the next script generator — worth more than "25,000
views". YouTube caveat: 2–3 day reporting lag, missing Shorts
viewed-vs-swiped and noisy small-video retention, no true viewer-level
randomisation (recommendation confounds) — treat as noisy observational
experiments; Pogtown's own Pog button can run genuine randomised
comparisons later. Two environments: YouTube for discovery, Pogtown for
control.

## 6. Ship next (narrow, whole loop)

1. Pogtown episode contract (character version, JokeBlock IDs, hypothesis, script, render version, YouTube ID).
2. fframes rendering adapter (one complete short from structured timeline, snapshots, audio QC).
3. Review canvas (preview/approve/reject/request-changes on scenes + finals).
4. YouTube analytics ingestion (comparable-age snapshots, availability flags).
5. FinalBuilds2 experiment adapter (episode → hypothesis, arm, lineage, outcome).
6. Jev decision routing (next experiment under explicit budget; log alternatives + reasons).
7. Closed-loop proof (several episodes → outcomes → evidence-informed brief).

Parallel small loop for OddHobb: verified pack → listing → approved campaign creative → impressions/clicks/orders → next creative decision. Shared infrastructure, independent generators and reward signals.

Bigger connection: Pogtown characters with demonstrated appeal → OddHobb authorised merchandise/personalised gifts. Long-term asset: evidence-backed library of mechanisms, characters, designs, experiments that generates, tests, learns, improves. First engineering move: small integration across FinalBuilds2, Freaktown, fframes, YouTube Analytics. Keep Jev, preserve verification boundaries, prove one feedback cycle before more infrastructure.
