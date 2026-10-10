# Pogtown fluid-actor stack (founder research, verbatim 2026-10-10)

> FinalBuilds2 = scientific brain (what to ask next, what discriminates,
> what deserves probes, how belief changes). Freaktown = execution engine.
> Influence = real world. qprivately = consequences. Jev = annotator.
> YouTube/Pogtown = observations. Keep Three.js + VRM runtime; add motion,
> face, world providers around it. No Unsloth; keep Jev.

## FinalBuilds2 as brain (not comedy generator)

Useful primitives: append-only events, graph lineage, IdeaGenerator→Idea,
process attribution, deterministic assignment, observations,
HypothesisV2, immutable forecasts, evidence hashes, resolutions, branching,
convergence detector, watchdog gate, idea planner, process lineage.
Hypothesis machine path: observations → convergence-detector →
ClusterCandidate → LLM induction → draft (≥3 evidence, falsifiable metric
+ window) → watchdog gate → probation. Caveat: built for software/product
ideas — abstractions transfer, scoring rubrics do not.

## Bayesian correction

Older calibration doc proposed Beta-Bernoulli + Thompson sampling; newer
evolution policy forbids it — use expected utility + λ information gain +
diversity − cost − risk instead. Pogtown outcomes are multivariate
(CTR, retention AUC, completion, comment rates, shares, return requests),
explanatory vars include character×JokeBlock×topic×performance interactions.
Hierarchical model later; never block MVP on PyMC machinery.

## Registry for characters (not product rubric)

Keep generator/lineage concept; drop delta/pain/cost_collapse scoring for
characters. Domain pogtown, kinds (character, joke_block, topic, format,
performance, visual, camera, packaging, world), per-kind admission
policies (e.g. premise clarity, contradiction, recognizability,
generativity, relationship potential, mechanism compatibility,
distinctness). JokeBlocks same treatment (clarity, falsifiability,
portability, escalation, observable prediction).

## Programs: HUMOUR / CHARACTER / VIRALITY / PERFORMANCE / DIRECTION /
## PACKAGING / TOPICALITY / WORLD — probes belong to programs so wins don't
## get confused across them.

## Performance granularity (computational filmmaking)

Same Nolan line, vary only: pre/post-punchline pauses, eye contact, head
angle, stillness, gesture, energy, pace, camera distance/cut timing,
audience delay. Freaktown primitives already fit (DeliveryScore,
PerformanceEngine, StageTimeline, camera cues, expressions, gesture,
pause_after_ms). Later: sketch grammar (blocking, multi-character), film
grammar (editing, sound, motifs). Same experimental machinery throughout.

## Process attribution over generators

Compare writer_v1 (whole-set) vs writer_v2 (planner) vs writer_v3 (graph)
vs writer_v4 (news-conditioned); director_static vs punchline-close vs
reaction-cut. Learn which processes work — the durable asset.

## Jev as annotator

Episode → mechanism scores (consistency, belief visibility, contradiction
clarity, escalation, specificity, callback, self-awareness) → correlate
with human outcomes. Never publish on Jev's taste (closes loop on model
taste, not human taste).

## Comments → hypothesis machine

Positive specifics become evidence claims (mechanism, performance,
attribution); convergence detector clusters (12 comments + 4 videos + 3
characters + retention spikes) → LLM proposes falsifiable H → diagnostic
probes. Gold run → competing explanations (H-A character … H-F packaging)
→ cheapest discriminating probes.

## Probe scoring: entertainment + 1.5×information gain + novelty/coverage
## + replication − cost − redundancy. 70/20/10 explore/explain/exploit.

## Avatar stack: Three.js + @pixiv/three-vrm (VRM 1.0, animation layer).
## Rigging: Meshy humanoids, UniRig fallback. Motion: recorded
## performances → MotionMind-style video→SMPL→VRM retarget (Tom acts it).
## Lip sync now: three-vrm-lip-sync (AudioWorklet, 5 visemes, no pipeline).
## Later: Audio2Face (ARKit52), ARDY (constrained motion), StreamTalk
## (co-speech gesture). World: one frozen Marble club (pogtown-club@1).
## Post: fframes/FFmpeg from StageTimeline. TERRA: research bucket only.

## Sprint (15 steps): club → avatar contract → motion library → lip-sync
## → StageTimeline authority → cameras → fframes post → 5 JokeBlocks +
## Nolan graph → ProbeManifest/EpisodePack → review canvas → qprivately →
## post → metrics+comments → forecast → resolve → evidence-driven probe #3.
## Then performance experiments (holds, camera, stillness), then sketches.
