Yes. This is the Pogtown MVP I would build.

The important shift is: **do not make “an autonomous comedy channel.” Make a scientific instrument whose output happens to be entertaining videos.**

Every published video is a probe. Every probe has a declared hypothesis, controlled variables, an immutable creative lineage, a verified release, and outcome measurements. When something wins, the system does not merely make more similar videos; it generates **diagnostic follow-up experiments intended to explain what caused the win**.

That is the difference between an AI content farm and something genuinely interesting.

Your previous architecture already pointed in exactly this direction: learn which creative mechanisms work rather than simply which outputs were popular, and treat Pogtown as an experimental environment for characters and JokeBlocks. Pasted text

# Pogtown Experimental Comedy System — technical specification

## 1. Scientific objective

The research question is not:

> What gets views?

It is:

> **What combinations of character, comedic mechanism, subject matter, performance, visual embodiment, direction and packaging reliably cause people to click, keep watching, laugh, comment positively, share, return for the character and develop attachment?**

That decomposes “funny and viral” into several different phenomena:

| Stage | Question | Example signal |
|---|---|---|
| Discovery | Did someone choose this content? | CTR / Shorts exposure-to-engagement |
| Hook | Did the first seconds work? | early retention |
| Sustained attention | Was it worth continuing? | retention curve / completion |
| Comic response | Did something actually land? | laugh/Pog events on Pogtown, retention spikes |
| Social resonance | Did they care enough to act? | shares/comments |
| Explanation | What specifically did they like/dislike? | comment semantics |
| Character affinity | Do they want this freak again? | return requests, repeat-character performance |
| Cultural memory | Did anything stick? | quotes, catchphrases, character-name mentions |
| Commercial depth | Would attachment transfer to objects? | later OddHobb product interest/purchases |

**Views cannot be the objective function.**

A clicky thumbnail can produce views and terrible retention. A great character can produce modest initial views but unusually strong requests for another appearance. A genuinely funny bit might produce quotes and shares but weak subscriber conversion.

Those are different causal layers.

---

# 2. The experiment is the unit of science; the video is one observation

This distinction matters.

One YouTube upload cannot usually prove:

> JokeBlock X causes 17% better comedy.

It contributes one observation to an experiment.

Use:

```text
Hypothesis
    ↓
Experiment
    ├── Arm A
    │    ├── Probe/video A1
    │    ├── Probe/video A2
    │    └── Probe/video A3
    │
    └── Arm B
         ├── Probe/video B1
         ├── Probe/video B2
         └── Probe/video B3
```

Each video is still deliberately falsifiable, but conclusions accumulate across replications.

Example:

> **H-017:** For sincere incompetent characters, `MISINTERPRETED_SUCCESS` produces more character-specific positive responses than `SELF_AWARE_FAILURE`.

Arm A:

```text
Nolan
MISINTERPRETED_SUCCESS
```

Arm B:

```text
Nolan
SELF_AWARE_FAILURE
```

Keep approximately constant:

```text
duration
topic family
visual environment
Nolan version
voice
performance engine
camera grammar
release window
thumbnail treatment
title treatment
```

Primary metric:

```text
specific positive character comments / 1,000 engaged views
```

Secondary:

```text
retention AUC
completion
shares
"bring Nolan back" rate
```

That's a real experiment.

---

# 3. YouTube is the ecological lab, not the controlled lab

This needs to be explicit in the science layer.

YouTube decides who receives a video. Therefore two uploads are **not viewer-randomized A/B tests**.

Recommendation effects, channel state, traffic source, time, competition and audience selection all confound results.

Use YouTube for:

> **Does this work in the actual attention economy?**

Use Pogtown itself later for:

> **Under randomized exposure, which variant actually wins?**

That distinction was already implicit in the earlier architecture: YouTube gives real-world discovery, while Pogtown can eventually perform genuine randomized comparisons. Pasted text

There is one useful exception: current YouTube Studio supports testing up to three title/thumbnail variants for eligible long-form content, choosing based on watch time, but that feature does **not currently support Shorts**. [Google Help](https://support.google.com/youtube/answer/16391400?hl=en-GB\&utm_source=chatgpt.com)

So:

```text
LONG FORM
native YouTube packaging experiment where available

SHORTS
matched probe releases + later Pogtown randomized testing
```

---

# 4. The creative variable hierarchy

Every episode should be described as a vector of experimental variables.

Do not throw them all into one prompt.

## Character variables

```text
premise
species/form
core contradiction
false belief
status desire
blind spot
defence mechanism
earnestness
self-awareness
confidence
relationship state
history/callbacks
```

Example:

```text
No-Nose Nolan

premise:
police sniffer dog with no smell

status desire:
elite investigator

false belief:
his unconventional methods demonstrate genius

defence:
reinterpret failure as advanced methodology

self-awareness:
very low

earnestness:
very high
```

## Joke mechanism variables

Your JokeBlocks:

```text
misinterpreted_success
false_expertise
status_reversal
literalization
callback_reversal
rule_of_three
contradiction_exposure
confident_wrongness
escalating_commitment
specificity_spiral
social_misread
delayed_realization
```

Keep v1 tiny: perhaps **10–15 well-defined blocks**.

## Topic variables

```text
evergreen
news/current
culture
technology
work
dating
family
sports
AI
politics-light
etc.
```

And richer features:

```text
recognizability
recency
controversy
audience overlap
absurdity potential
status conflict
hypocrisy
jargon density
character relevance
```

## Script variables

```text
hook type
beat count
words
setup length
punchline density
specificity
escalation slope
callback count
closer type
```

## Performance variables

Freaktown already has most of these:

```text
voice
pace
energy
pause duration
expression
gesture
stillness
eye contact
signature move
```

## Direction variables

```text
wide/medium/close
reaction shot timing
camera movement
cut rate
punchline hold
audience cutaway
sound cue
```

## Visual variables

```text
character mesh
silhouette
colour
face readability
animation quality
stage lighting
environment
visual novelty
```

## Packaging variables

```text
title
thumbnail
first frame
caption hook
description
```

## Distribution variables

```text
publish time
traffic source
format
duration
channel age/state
```

The statistical system must know all of them, even when they are *not* being manipulated.

---

# 5. Every probe has one primary question

This prevents chaos.

A valid experiment might ask:

> Does Nolan outperform Corporate Robot when both perform `FALSE_EXPERTISE`?

Then do not simultaneously change:

- JokeBlock;
- lighting;
- camera system;
- duration;
- title format;
- voice model.

Likewise:

> Does Nolan's current mesh outperform a grotesquely exaggerated Nolan mesh?

Keep:

```text
script
voice
JokeBlocks
delivery
camera
title style
topic
```

as constant as practical.

A useful invariant:

> **Every probe declares one primary manipulated factor and at most one secondary interaction factor. Everything else is a control or recorded covariate.**

---

# 6. The immutable `ProbeManifest`

Before rendering, freeze this:

```json
{
  "probe_id": "probe_nolan_0041",

  "experiment_id": "exp_017",

  "hypothesis_id": "H-017",

  "arm": "treatment",

  "primary_factor": {
    "name": "jokeblock",
    "value": "misinterpreted_success@3"
  },

  "controls": {
    "character": "nolan@14",
    "topic": "airport-security@2",
    "performance_engine": "deadpan-dog@7",
    "club_world": "pogtown-club@1",
    "camera_grammar": "standup-short@3"
  },

  "creative": {
    "joke_blocks": [
      "false_expertise@2",
      "misinterpreted_success@3",
      "double_down@2"
    ],
    "script_hash": "sha256:..."
  },

  "preregistered": {
    "primary_metric": "specific_positive_comment_rate",
    "secondary_metrics": [
      "retention_auc",
      "completion_rate",
      "share_rate"
    ],
    "expected_direction": "treatment > control",
    "minimum_evidence": "..."
  }
}
```

This object is immutable.

No changing the hypothesis after seeing the result.

---

# 7. CharacterGraph specification

Freaktown's current Character Pack is already a strong seed. Preserve it.

Add three layers.

## Canon graph

Very stable:

```text
identity
premise
traits
values
false beliefs
desires
blind spots
defence mechanisms
relationships
```

## Narrative state

Event sourced:

```text
what happened
what character observed
what character believes happened
relationship updates
grudges
confidence
goals
callbacks
```

Example:

```json
{
  "event": "audience_laughed_at_failed_investigation",

  "objective": "audience recognised Nolan's incompetence",

  "nolan_interpretation": "audience admired novel methodology",

  "state_updates": {
    "confidence": 0.71,
    "belief_advanced_methodology": 0.88
  }
}
```

## Empirical strategy graph

Kept hidden from the character:

```text
Nolan × misinterpreted_success = strong
Nolan × self_deprecation = weak
Nolan × deadpan delivery = strong
Nolan × rapid delivery = unclear
```

This is scientific knowledge used by writers.

Do **not** let it automatically change canon.

---

# 8. JokeBlock specification

A JokeBlock should resemble an executable theory.

Example:

```json
{
  "id": "misinterpreted_success",
  "version": 3,

  "family": "dramatic_irony",

  "requires": {
    "false_belief": true,
    "visible_contradiction": true
  },

  "roles": [
    "establish_claim",
    "present_failure",
    "audience_recognises_failure",
    "character_reinterprets_failure",
    "double_down"
  ],

  "audience_model": {
    "knows": "character has failed"
  },

  "character_model": {
    "believes": "failure proves competence"
  },

  "compatible_next": [
    "status_claim",
    "escalating_commitment",
    "callback_reversal"
  ],

  "known_failure_modes": [
    "character is explicitly self-aware",
    "contradiction isn't obvious"
  ]
}
```

This is vastly more useful than storing jokes.

---

# 9. JokePlan → Script → Performance

The generation pipeline should be:

```text
CharacterGraph snapshot
        +
TopicBrief
        +
JokeBlock composition
        ↓
JokePlan
        ↓
multiple script realizations
        ↓
Jev structural annotations
        ↓
candidate selection
        ↓
DeliveryScore
        ↓
PerformanceEngine
        ↓
StageTimeline
```

A JokePlan could be:

```json
{
  "character": "nolan@14",

  "topic": "airport_security",

  "beats": [
    {
      "role": "claim",
      "block": "false_expertise"
    },
    {
      "role": "failure",
      "block": "contradiction_exposure"
    },
    {
      "role": "turn",
      "block": "misinterpreted_success"
    },
    {
      "role": "escalation",
      "block": "double_down"
    },
    {
      "role": "closer",
      "block": "callback_reversal"
    }
  ]
}
```

The language model writes *within* that structure.

---

# 10. Jev's role

Do not train Jev to predict “funny.”

Use it to annotate mechanisms.

Example output:

```json
{
  "character_consistency": 0.94,
  "false_belief_visibility": 0.88,
  "contradiction_clarity": 0.91,
  "escalation_strength": 0.74,
  "specificity": 0.81,
  "callback_strength": 0.69,
  "self_awareness": 0.12
}
```

Then correlate those descriptors with human outcomes.

That gives you interpretable learning.

---

# 11. Topic mining becomes its own experiment source

Build a `TopicMiner`.

Inputs:

```text
recent news
search trends
Reddit/community language
YouTube trends
Pogtown chat
historical channel topics
```

Output:

```json
{
  "topic_id": "ai_agents_workplace_2026_10",

  "facts": [...],

  "freshness": 0.97,

  "recognizability": 0.82,

  "audience_overlap": 0.71,

  "comedic_affordances": [
    "status anxiety",
    "false expertise",
    "corporate euphemism"
  ],

  "recommended_characters": [
    "corporate-robot"
  ]
}
```

Then explicitly test:

> Was the video strong because the topic was hot?

rather than confusing topic performance with character quality.

---

# 12. Marble should generate the club once

Do not regenerate a comedy club for each video.

World Labs' public World API now allows programmable generation of navigable 3D environments from text, images and video, with downstream rendering/export integration. [World Labs](https://www.worldlabs.ai/blog/announcing-the-world-api?utm_source=chatgpt.com)

Use it as an **environment authoring tool**.

```text
Marble World API
        ↓
generate Pogtown Comedy Club
        ↓
human/agent approves world
        ↓
freeze/export
        ↓
StageWorldPack
```

Something like:

```json
{
  "id": "pogtown-club@1",

  "world_provider": "worldlabs.marble",

  "world_asset_hash": "sha256:...",

  "stage": {
    "origin": [0, 0, 0],
    "performer_anchor": [0, 0, 0]
  },

  "cameras": {
    "wide": {},
    "medium": {},
    "close": {},
    "side": {},
    "audience": {}
  },

  "lighting": {
    "preset": "club_warm"
  }
}
```

Atlas should sit behind the same interface later rather than becoming a dependency.

```text
WorldProvider.generate()
WorldProvider.export()
```

Today: Marble.

Future: Atlas/other world models.

---

# 13. Rigging pipeline

Same principle.

Any character mesh enters:

```text
raw mesh
    ↓
rig provider
    ↓
capability detection
    ↓
Freaktown avatar contract
```

Never let the stage care which rigging engine did it.

Your existing Freaktown contract already gets this right:

```text
humanoid?
blink?
visemes?
look_at?
expressions?
```

So:

```text
RigProvider
    ↓
avatar.glb / avatar.vrm
    +
avatar.json
```

If the body can't do something:

> degrade.

A Roomba does not need humanoid hand gestures to be funny.

---

# 14. Camera system

Freeze five initial camera anchors:

```text
WIDE
MEDIUM
CLOSE
SIDE
AUDIENCE
```

Then a versioned `CameraGrammar` decides when to use them.

Example:

```text
setup:
MEDIUM

escalation:
MEDIUM → CLOSE

punchline:
CLOSE

post-punchline hold:
stay CLOSE 800ms

big audience response:
AUDIENCE 600ms

actout:
WIDE
```

Do not ask an LLM to continuously fly a camera around.

It can choose semantic instructions.

Renderer executes deterministic camera language.

---

# 15. StageTimeline is the render truth

Everything should compile down to:

```text
00:00.000  camera.medium
00:00.000  character.enter
00:00.600  audio.voice.start
00:02.420  gesture.small
00:04.810  camera.close
00:05.200  punchline
00:05.300  character.dead_stare
00:05.300  hold 1100ms
00:06.400  next_beat
```

Then:

```text
StageTimeline
→ StageRuntime
→ MP4
```

One event timeline should drive:

```text
audio
animation
camera
captions
SFX
```

That gives you deterministic lineage and makes visual factors experimentally controllable.

---

# 16. `EpisodePack`

Once rendered, freeze:

```json
{
  "episode_id": "ep_nolan_041",

  "probe_manifest": "probe_nolan_0041",

  "character": {
    "id": "nolan",
    "version": 14
  },

  "character_state_hash": "...",

  "joke_blocks": [
    "false_expertise@2",
    "misinterpreted_success@3"
  ],

  "performance": {
    "engine": "deadpan@7",
    "timeline_hash": "..."
  },

  "visual": {
    "mesh_hash": "...",
    "world": "pogtown-club@1",
    "camera_grammar": "shorts@3"
  },

  "artifacts": {
    "video": "asset:...",
    "thumbnail": "asset:...",
    "captions": "asset:..."
  },

  "qc": {
    "audio": "PASS",
    "render": "PASS",
    "character": "PASS"
  }
}
```

This is Freaktown's final output.

---

# 17. Influence handles the release

Influence receives the EpisodePack.

It can generate:

```text
title candidates
thumbnail candidates
description
hashtags
schedule
```

But it cannot rewrite the episode.

It creates a:

```text
ChannelRelease
```

Then the middle Review Canvas shows:

```text
VIDEO
THUMBNAIL
TITLE
DESCRIPTION

Experiment:
H-017

Treatment:
MISINTERPRETED_SUCCESS

Controlled:
Nolan@14
deadpan@7
club@1
29 sec

Cost:
$0.18

[ Reject ] [ Change ] [ Approve exact release ]
```

qprivately binds approval to exact hashes.

---

# 18. YouTube publishing must be verified

Flow:

```text
approved ChannelRelease
        ↓
qprivately grant
        ↓
Influence upload
        ↓
external YouTube video ID
        ↓
independent readback
        ↓
TransitionReceipt
```

Only then:

```text
published = TRUE
```

Only verified releases enter experiment analysis.

---

# 19. Analytics ingestion schedule

I would capture snapshots at comparable ages:

```text
30 minutes
2 hours
6 hours
24 hours
72 hours
7 days
28 days
```

Not:

> video A has 8,000 views and video B has 4,000

when A is nine days old.

Each snapshot gets:

```text
video_age_seconds
traffic sources
exposure
views
watch metrics
interaction metrics
```

YouTube's Analytics API currently exposes audience-retention reports including `elapsedVideoTimeRatio`, `audienceWatchRatio`, `relativeRetentionPerformance`, plus started/stopped-watching measures; traffic-source reports are also available. [Google for Developers](https://developers.google.com/youtube/analytics/channel_reports?utm_source=chatgpt.com)

---

# 20. Build a retention feature extractor

Convert the raw retention curve into interpretable features.

For every video:

```text
R_05 = retention around first 5% of runtime
R_10
R_25
R_50
R_75
R_95

retention_auc
largest_drop
largest_rewatch_peak
closer_retention
post_punchline_delta
```

Because you know the StageTimeline, you can align these against beats.

Then you can learn:

```text
misinterpreted_success block
started at 9.2s

retention change:
+3.8pp relative to matched baseline
```

That's much better than total watch time.

---

# 21. Comments should be one of the richest signals — but not the sole goal

Your instinct is correct.

**Specific positive comments are arguably the richest explanatory signal** because viewers volunteer *why* something worked.

YouTube's API allows retrieval of comment threads and replies, so this can be ingested systematically. [Google for Developers](https://developers.google.com/youtube/v3/docs/commentThreads?utm_source=chatgpt.com)

But don't optimize simply for:

> positive comment count.

Comments are:
- selection biased;
- sparse;
- sometimes sarcastic;
- influenced by controversy;
- easy to engagement-bait.

Instead build a **Comment Evidence Engine**.

---

# 22. Comment taxonomy

Use a model to annotate each comment without reducing it immediately to one scalar.

```text
GENERIC_POSITIVE
"lol"

CHARACTER_POSITIVE
"Nolan is killing me"

RETURN_REQUEST
"bring this dog back"

QUOTE
"I'm stealing 'advanced scent-neutral methodology'"

JOKE_MECHANISM
"him thinking they were applauding him finished me"

PERFORMANCE
"the pause after that line was perfect"

VISUAL
"the stupid tiny police hat makes this"

VOICE
"his voice makes it 10x funnier"

TOPIC
"this airport security one is too real"

NEGATIVE_CHARACTER
"I hate this character"

NEGATIVE_WRITING
"same joke three times"

CONFUSION
"I don't get what happened"

AI_ARTIFACT
"why did his arm melt"

PACKAGING_MISMATCH
"thumbnail had nothing to do with it"
```

And perhaps:

```text
specificity
sentiment
character_reference
quote_reference
request_more
mechanism_reference
```

---

# 23. The gold comment metrics

Don't use:

```text
positive_comments
```

Use rates such as:

```text
specific_positive_comments / 1,000 engaged views

character_positive_comments / 1,000 engaged views

explicit_return_requests / 1,000 engaged views

quote_adoption / 1,000 engaged views

specific_negative_comments / 1,000 engaged views
```

Those have explanatory value.

A comment saying:

> “the fact he thought the audience was impressed absolutely killed me”

is almost a free human annotation saying:

```text
MISINTERPRETED_SUCCESS worked.
```

That should become linked evidence on the experiment.

---

# 24. Character quality should have its own metrics

Do not judge a character by their first video.

Define **Character Market Fit** from repeated appearances.

Signals:

```text
character-name mention rate
positive character comment rate
"bring them back" rate
quote/catchphrase rate
performance across unrelated topics
repeat appearance retention
subscriber conversion around appearances
Pogtown return vote
eventual merch demand
```

A great character should survive:

> changing the joke.

A great joke should survive:

> changing the character.

That's exactly why follow-up probes matter.

---

# 25. Character probation

For new characters:

```text
3-probe probation
```

Probe 1:
best-known general mechanism.

Probe 2:
different topic/mechanism.

Probe 3:
character-forward episode.

Then:

```text
RETIRE
HOLD
REGULAR
GOLD
```

Don't spend 50 episodes trying to rescue a weak premise.

But keep the full record.

A character that fails today could become useful under a future mechanism.

---

# 26. Gold Runs

A Gold Run should be an immutable scientific object, not:

> video with lots of views.

Example:

```json
{
  "gold_run_id": "gold_004",

  "episode_id": "ep_nolan_041",

  "reason": {
    "retention_percentile": 98,
    "specific_positive_comment_percentile": 99,
    "share_percentile": 96
  },

  "frozen_lineage": {
    "...": "..."
  },

  "status": "diagnostic_required"
}
```

A Gold Run's first consequence should **not** be:

> make ten clones.

It should be:

> **explain the win.**

---

# 27. The Gold Run diagnostic tree

Suppose Nolan's airport-security video explodes.

Spawn controlled follow-ups.

## Test character

```text
Same JokeBlocks
Same topic family
New character
```

If performance collapses:

> Nolan mattered.

## Test comedy mechanism

```text
Same Nolan
Same visual system
Different JokeBlock
```

If it collapses:

> mechanism mattered.

## Test topic

```text
Same Nolan
Same JokeBlocks
Different topic
```

If it survives:

> not just the news cycle.

## Test visual design

```text
Same script/audio
alternate Nolan mesh treatment
```

Tests recognizability/silhouette.

## Test performance

```text
Same script
deadpan vs nervous engine
```

Tests delivery.

## Test direction

```text
same audiovisual ingredients
camera grammar A/B
```

## Test packaging

For eligible long-form videos, use YouTube's native title/thumbnail tests rather than republishing content. [Google Help](https://support.google.com/youtube/answer/16391400?hl=en-GB\&utm_source=chatgpt.com)

## Replicate

```text
same mechanism
new script
same character
```

If the effect repeats, confidence rises substantially.

---

# 28. Never confuse novelty with mechanism

This is going to be a huge issue.

A weird new mesh might win because:

> it is new.

Not because:

> ugly meshes are inherently funnier.

Track:

```text
character appearance number
mesh first-seen age
topic novelty
format novelty
```

and model novelty decay.

Otherwise you'll optimize the entire system toward endlessly introducing random characters.

---

# 29. Exploration/exploitation strategy

You said mostly explore. Correct.

Initially:

```text
70% EXPLORE
20% EXPLAIN / REPLICATE
10% EXPLOIT
```

I would actually value **explanation** separately from exploitation.

### Explore

Test genuinely new:
- JokeBlocks;
- characters;
- topics;
- performance styles;
- visual forms.

### Explain

Probe surprising outcomes.

This is the most scientifically valuable pool.

### Exploit

Use combinations already supported by evidence.

Once the theory graph matures, perhaps:

```text
55% explore
25% explain
20% exploit
```

Don't ever let it become:

> 90% clones of last week's viral thing.

That kills the research engine.

---

# 30. Experiment allocator

FinalBuilds2 should decide what deserves the next probe.

Candidate score could conceptually use:

```text
expected_information_gain
+
expected_entertainment_value
+
strategic_value
-
generation_cost
-
redundancy
```

Not just:

```text
predicted views
```

Use bandit ideas such as posterior sampling/UCB for allocation, but weight **uncertainty reduction** highly.

The goal is:

> learn the shape of comedy space.

---

# 31. Statistical model

I would eventually use a hierarchical model.

Outcome:

```text
retention_auc
specific_positive_comment_rate
share_rate
character_return_rate
```

Explanatory terms:

```text
character
JokeBlock
topic
performance engine
mesh family
title family
thumbnail family
day/time
duration
traffic source
appearance number
```

plus interactions:

```text
character × JokeBlock
character × topic
JokeBlock × topic
character × performance
```

This is where the interesting knowledge lives.

You might learn:

> `MISINTERPRETED_SUCCESS` is mediocre globally but excellent on sincere, low-self-awareness characters.

That's actual theory.

---

# 32. Avoid p-hacking

The system is going to test hundreds of things.

Therefore:

1. preregister a **primary metric**;
2. record all hypotheses before outcome;
3. distinguish exploratory from confirmatory results;
4. preserve failed probes;
5. correct across related hypothesis families;
6. replicate major findings.

FinalBuilds2 already has the right philosophical infrastructure for hypothesis evolution and process attribution. Your previous system specifically distinguished observational attribution from causality. Pasted text

Keep that discipline.

---

# 33. The outcome vector

I would not collapse everything into one score for science.

Store:

```text
reach
click/acquisition
hook
retention
rewatch
share
generic positive
specific positive
character positive
return request
quote adoption
negative specific
subscriber effect
returning audience
```

You can have a temporary ranking utility for allocation, but the raw vector stays canonical.

---

# 34. Metric-to-factor mapping

This prevents silly conclusions.

| Factor being tested | Most informative primary metric |
|---|---|
| Thumbnail/title | watch time from impressions / CTR |
| First-frame hook | early retention |
| JokeBlock | local retention + comments + completion |
| Character premise | repeated-appearance affinity |
| Mesh design | early hold + visual-specific comments |
| Performance style | retention around punchlines |
| Camera direction | beat-level retention |
| Topic | reach + retention normalized by exposure |
| Closer | final retention / comments / shares |
| Character recurrence | return-request and repeat-viewer measures |

Don't use CTR to decide whether the joke was funny.

---

# 35. Pogtown randomized experiments

Eventually your own viewer lets you do the experiments YouTube cannot.

When somebody opens:

```text
pog.town/watch
```

assign:

```text
experiment_id
arm
viewer/session hash
```

deterministically.

Then two viewers may receive:

```text
same Nolan
same setup
different punchline mechanism
```

Now you can measure:

```text
Pog button
completion
replay
skip
return vote
```

under actual random assignment.

That can confirm hypotheses discovered observationally on YouTube.

---

# 36. The first-frame problem for Shorts

For Shorts, the video itself is the thumbnail.

Therefore model the first 1–2 seconds as a separate experimental artifact:

```text
visual hook
first line
caption
character silhouette
camera
motion onset
```

You can explicitly test:

```text
start on character face
vs
start wide
```

while leaving the rest of the episode identical.

That's a much cleaner Shorts test than trying to infer thumbnail effects.

---

# 37. Positive comments become theory evidence

The comment engine should not simply say:

> 78% sentiment.

It should emit links:

```text
comment c128
supports:
  mechanism=misinterpreted_success
  confidence=.82

comment c141
supports:
  visual=police_hat
  confidence=.93

comment c201
supports:
  character=nolan
  request_more=true
```

Now your human audience is helping annotate the creative graph.

That's unusually powerful.

---

# 38. Comment evidence should be inspectable

Don't let the LLM invent conclusions from summaries.

For every finding:

```text
"Viewers specifically praised Nolan's misinterpretation"
```

store:

```text
supporting comment IDs
comment texts
classifier version
confidence
```

Then your Review Canvas can open:

> Why do we think this?

and show the evidence.

That fits qprivately/verified-evidence philosophy beautifully.

---

# 39. Full database model

I would roughly maintain:

```text
characters
character_versions
character_events
character_relationships

joke_blocks
joke_block_versions

topics
topic_snapshots

hypotheses
experiments
experiment_arms

probe_manifests
joke_plans
scripts
performance_plans

episode_packs
channel_releases

metric_snapshots
retention_points

comments
comment_annotations

findings
gold_runs

qp_receipts
```

Assets live in R2/object storage.

Rows refer to immutable hashes.

---

# 40. The `Finding` object

This becomes the core scientific output.

Example:

```json
{
  "finding_id": "finding_0098",

  "claim": {
    "subject": "misinterpreted_success@3",
    "predicate": "works_better_with",
    "object": "sincere_low_self_awareness"
  },

  "scope": {
    "platform": "youtube",
    "format": "short",
    "characters": 5
  },

  "evidence": {
    "experiments": [
      "exp_017",
      "exp_021",
      "exp_032"
    ],
    "n_probes": 24
  },

  "status": "provisional",

  "posterior": {
    "direction_probability": 0.94
  }
}
```

Then:

```text
provisional
→ replicated
→ robust
→ contradicted
→ retired
```

That's the actual comedy knowledge base.

---

# 41. The first Pogtown MVP does not need all of this implementation

Architect for it.

Build a vertical slice.

I would implement:

```text
3 characters
5 JokeBlocks
1 club
1 camera grammar
1 renderer
1 YouTube channel
1 analytics pipeline
1 comment classifier
1 experiment table
```

No giant world engine yet.

---

# 42. MVP visual production

I would do:

### Environment

Generate **one genuinely beautiful club** using Marble.

Freeze it.

### Performer

Use the existing mesh/auto-rig route to create characters.

### Animation

Keep deliberately constrained:

```text
idle
sway
talk
look
small gesture
big gesture
dead stare
reaction
walk on
walk off
```

You do not need Pixar motion.

Comedy survives limited motion if timing is strong.

### Voice

Existing Freaktown provider router.

### Camera

Five fixed anchors.

### Output

Primary:

```text
1080×1920 Shorts
```

Optional landscape later.

---

# 43. The biggest production advantage is determinism

If a video unexpectedly works, you must be capable of rendering:

```text
same script
same voice
same character
same motion
same world
same everything
```

with only:

```text
camera changed
```

Otherwise your experiments are useless.

So every stochastic generator needs:

```text
version
seed
artifact hash
```

where possible.

If not reproducible, freeze its output as an asset.

---

# 44. Human review for MVP

Do not autonomously publish the first hundred videos blind.

Influence Review Canvas:

```text
[ VIDEO PLAYER ]

H-017
Testing:
MISINTERPRETED_SUCCESS vs SELF_AWARE_FAILURE

Character:
Nolan@14

Duration:
27.4 sec

QC:
audio ✓
mesh ✓
captions ✓

YouTube:
title
description

[ REJECT ]
[ CHANGE ]
[ APPROVE ]
```

Approve exact hashes.

qprivately publishes.

---

# 45. Later autonomous publication

Once the pipeline is proven:

human grants:

```text
channel:
Pogtown YouTube

capability:
publish_video

experiment series:
EXP-021

max publications:
6

expiry:
48h

max paid spend:
$0

constraints:
all EpisodePacks QC-passed
```

Then Influence can autonomously publish the preregistered experiment.

Still auditable.

---

# 46. First experimental programme

I would not immediately test 50 variables.

Run four studies.

## Study A — Character premise

Question:

> Do some character premises intrinsically create stronger affinity?

Use:
- same stage;
- same performance grammar;
- same JokeBlock family;
- matched topics.

Test perhaps six characters.

Outcome:

```text
character positive comments
return requests
retention
```

## Study B — Joke mechanism

Use top three characters.

Each gets several JokeBlocks.

This estimates:

```text
global mechanism effects
character × mechanism interactions
```

## Study C — Performance

Take strongest character/mechanism combinations.

Test:

```text
deadpan
nervous
chaotic
```

Same wording.

## Study D — Visual embodiment

Same episode/audio.

Change:

```text
mesh style
silhouette
expression treatment
```

Now you can actually answer:

> Does the character look matter?

---

# 47. Topics become Study E

Only after some baseline exists.

Take proven character/mechanism pairs.

Run them over:

```text
evergreen
current news
AI news
work
dating
sports
```

Then normalize for topic exposure.

This tells you whether:

> topicality adds reach at the expense of character attachment,

for example.

That's genuinely useful.

---

# 48. Gold Run protocol

When a probe reaches Gold:

**do not change seven things at once.**

Automatically create an `ExplanationPlan`:

```text
E1 replication
E2 character swap
E3 JokeBlock swap
E4 topic swap
E5 performance swap
E6 visual swap
E7 packaging test
```

Prioritize these by:

```text
expected information gain / cost
```

The system should treat virality as:

> a mysterious observation requiring investigation.

That's a much more interesting philosophy than:

> feed the winner back into the prompt.

---

# 49. What counts as "good character"?

I would operationalize it as:

> **A character is strong if attachment survives changes in material.**

A strong character should generate positive affinity across:

```text
different JokeBlocks
different topics
multiple appearances
```

Therefore Character Quality isn't one viral episode.

It is an estimated **character random effect across probes**.

That's a very clean statistical definition.

---

# 50. What counts as “funny mechanism”?

Similarly:

> A JokeBlock is strong if its effect survives multiple characters and topics.

Then:

```text
Character effect
Mechanism effect
Interaction effect
```

are three separate things.

Exactly what you want.

---

# 51. What counts as viral?

Again: distinct.

Virality is more:

```text
distribution acceleration
sharing
replay
reach expansion
```

Something can be:

```text
very funny
not viral
```

or:

```text
very viral
not character-building
```

Store both.

---

# 52. The unique thing you can eventually discover

After hundreds of probes, you can ask questions no conventional comedy model can answer:

> Which character traits interact with dramatic irony?

> Does a grotesque mesh improve first-second retention but hurt long-term attachment?

> Are callbacks more effective for returning viewers?

> Does news satire acquire viewers but evergreen character comedy create stronger return intent?

> Does a 900ms post-punchline stare outperform 300ms specifically for confident-wrong characters?

> Do positive comments about visual appearance predict merchandising demand?

That's real research.

---

# 53. OddHobb then becomes the downstream physicalization engine

When Pogtown learns:

```text
Nolan:
strong audience affinity
recognizable silhouette
high return requests
frequently quoted
```

that's an eligibility signal.

Then:

```text
CharacterGraph
    ↓
canonical Nolan visual
    ↓
Pogpet transforms/recipes
    ↓
figure
ornament
card
sticker
wrapping paper
    ↓
Product Pack
    ↓
physical sample
    ↓
PROVEN
    ↓
Influence
```

Content creates the demand.

OddHobb captures the demand physically.

The broader architecture explicitly anticipated this path from successful Pogtown characters to authorised merchandise and personalized goods. Pasted text

---

# 54. System boundaries

I would freeze this:

```text
FINALBUILDS2
scientific question / hypothesis / experiment / inference

FREAKTOWN
character / JokeBlock realization / performance / EpisodePack

WORLD + RIG PROVIDERS
raw creative infrastructure

INFLUENCE
review / release / platform ops / analytics ingestion

QPRIVATELY
authority / effects / verification / receipts

POGTOWN
viewer surface + future randomized experimental environment

POGPET
physical manifestation / Product Packs / fulfilment
```

No subsystem recreates another one.

---

# 55. Immediate engineering plan

If I were giving the coding agent the next sprint, it would be:

### P0 — render loop

1. Generate and freeze `pogtown-club@1` with Marble.
2. Define `StageWorldPack`.
3. Get any arbitrary approved mesh through the rigging adapter into the existing Freaktown avatar capability contract.
4. Render it on stage.
5. Freeze five camera anchors.
6. Compile one `StageTimeline`.
7. Produce one deterministic 9:16 MP4.

### P1 — structured comedy

8. Define JokeBlock v1 with **five** blocks only.
9. Create CharacterGraph v1 for Nolan.
10. Build JokePlan schema.
11. Compile JokePlan → current delivery score.
12. Produce three Nolan probes differing only in one JokeBlock.

### P2 — scientific release

13. Add `ProbeManifest`.
14. Add `Experiment`.
15. Add `EpisodePack`.
16. Display experiment metadata beside the video in Influence Review Canvas.
17. qprivately exact-hash approval.
18. Influence posts to YouTube.
19. Verify upload.

### P3 — feedback

20. Ingest age-normalized YouTube metrics.
21. Store retention curves.
22. Ingest comments/replies.
23. Classify comments into the semantic taxonomy.
24. Link comments to character/JokeBlock/video features.
25. Create first `Finding`.

### P4 — Gold loop

26. Detect first Gold candidate.
27. Generate its ExplanationPlan.
28. Run at least three diagnostic probes.
29. Update the finding.
30. Let the next creative generation consume the updated evidence.

Then stop and inspect whether it actually learned something.

---

# The acceptance test

Pogtown MVP is **not**:

> AI successfully uploaded a funny-looking Short.

It's this:

> **We preregistered a theory, generated two controlled creative treatments, rendered them through the same character/world/performance stack, human-approved and autonomously published them, collected verified age-normalized audience and comment evidence, produced an interpretable finding, and that finding changed the next experiment.**

If that works, you have the machine.

Everything after that—more characters, better rigs, Marble/Atlas worlds, ARDY motion, better jokes, live Pogtown, merchandise—is scaling a proven loop rather than building another platform.