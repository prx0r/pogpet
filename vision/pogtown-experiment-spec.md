# Pogtown experiment spec: the science of funny (v1, 2026-10-10)

> Objective: discover, with evidence, what makes something funny, viral,
> and character-worthy — character vs premise vs mesh vs title/thumbnail
> vs delivery — and reinvest it. Every video is a probe that clearly
> falsifies something. Mostly explore; exploit gold runs by variation.
> Positive comments are the gold feedback: they say *why* in specifics.

## 1. The probe (unit of work)

```json
{
  "probe_id": "probe_nolan_031",
  "hypothesis_id": "hyp_misinterp_sincere_04",
  "falsifies": "misinterpreted-success works WITHOUT visible incompetence",
  "character": {"id": "no-nose-nolan", "version": 14},
  "mechanisms": ["misinterpreted_success@3", "callback_reversal@1"],
  "holds_constant": ["mesh", "voice", "delivery_engine", "thumbnail_style",
                     "title_template", "posting_slot", "duration_band"],
  "varies": {"situation": "parking-ticket appeal"},
  "situation_source": "news:2026-10-09:local-council-fines",
  "artifacts": {"video": "asset:…", "thumbnail": "asset:…"},
  "outcomes": {}
}
```

Rule: a probe with no `falsifies` field is not scheduled. "Let's see what
happens" is not a probe.

## 2. Variable taxonomy (what we test, in which lane)

| Lane | Variables | Examples |
|---|---|---|
| GLOBAL (applies to every probe) | thumbnail style, title template, posting slot, duration band | Does close-face + 3-word title beat scene-still + question? |
| CHARACTER | premise, mesh design, voice, relationships | Same set, new face: does recognition carry it? |
| CONTENT | JokeBlock, situation, topic source | Same character, new mechanism: what moved? |
| DELIVERY | engine, pacing, camera, hold lengths | Same script, deadpan vs nervous engine? |
| SITUATION | news item, occasion, trend | Same mechanism on fresh news vs evergreen? |

Control protocol: one lane varies per probe class; the rest are pinned
and recorded. A probe sheet that varies character AND mechanism AND
thumbnail teaches nothing — reject at schedule time.

## 3. Probe classes (the standard battery)

- **Mechanism probe**: fixed character + delivery + packaging, new
  JokeBlock. Answers: does this mechanism work *here*?
- **Character probe**: fixed mechanism + delivery, new/recast character.
  Answers: is it the bit or the face? (Recast a gold run with a new
  character; if it dies, the character was the carrier.)
- **Delivery probe**: fixed script + character, new engine/pacing/camera.
  Answers: how much lives in performance?
- **Packaging probe**: fixed video, new thumbnail/title. Answers: what
  makes someone click? (Cheapest probes; run most often.)
- **Situation probe**: fixed everything, fresh news graft. Answers: does
  topicality lift, and does it decay?
- **Gold-run variation**: gold run + one deliberate change. Answers: what
  was load-bearing? (Section 5.)

## 4. Gold runs (promotion, not vibes)

Promote when ALL hold over ≥3 probes or one breakout (10× median views
with completion intact):

```text
completion ≥ channel median AND (shares/views OR comments/views) top-decile
```

Gold run record: probe refs, mechanism set, frozen character version,
frozen delivery config, thumbnail/title, audience slice. Then the system
asks *why it worked* by spawning variation probes — same character/new
mechanism (character carrier test), same mechanism/new character
(mechanism carrier test), same video/new packaging (packaging test).
First variation that kills it names the load-bearing element. Store that
as the lesson, not the view count.

## 5. Feedback hierarchy (comments are gold)

| Tier | Signal | Why ranked here |
|---|---|---|
| GOLD | positive comment specifics | Only signal that names mechanisms ("the way he doubles down", "that stare") — maps to theory edges |
| SILVER | retention curve shape, rewatches, shares | Behavior, but mute about cause |
| BRONZE | views, likes, follows | Reach + weak approval, confounded by packaging/algorithm |

Comment mining pipeline: collect → filter positive (specific praise, not
"lol") → extract mechanism mentions (Jev labels: which JokeBlock,
character trait, moment timestamp) → attach as evidence to theory edges
with quote + probe ref. A comment saying "I lost it when he trademarked
the technique" is a vote for double_down@2 in a Nolan context — file it
there. Negative comments file symmetrically (failure modes).

## 6. Attribution model (character vs premise vs mesh vs title)

Per probe, decompose outcome into lane contributions via the battery:
packaging probes isolate click (CTR deltas); retention curves isolate
content vs delivery (early drop = premise/packaging, mid decay = content,
end cliff = closer/delivery); character probes isolate face vs bit;
comment labels isolate mechanism vs performance. Record per-lane deltas
with n, window, and confounders (posting slot, traffic source, video
age). YouTube numbers are observational (recommendation confounds);
Pogtown randomized Pog votes are the control environment when live.

## 7. Thumbnails + titles (global lane, highest frequency)

Thumbnail variables: face close-up vs scene, text overlay vs clean,
expression peak vs neutral, brand frame vs raw. Title variables: question
vs statement, name-first vs mechanism-first, length bands. Rule: every
video ships with its packaging probe (A/B title or thumbnail) — clicks
are the cheapest data we collect. Retention: first-3s drop (hook),
mid-video slope (content), end cliff (payoff/delivery). Comment prompt
engineering is allowed ("which bit got you?") — replies are gold ore.

## 8. News ingestion (topical situations, with guardrails)

News → situation candidates (local absurdity, national farce, calendar
events) → taste filter (no tragedy, no victims as butts, no misinfo
adjacent) → graft onto fixed mechanism + character. Track decay: same
mechanism on 1-day-old vs 7-day-old news measures topicality half-life.
Evergreen control always runs alongside.

## 9. Explore / exploit

Default 80/20 explore (Thompson sampling over mechanism×character cells,
weighted by uncertainty + cost). Exploit = gold-run variations + proven
mechanism on new characters. Never pure exploit: audience taste drifts,
and mechanisms saturate (track per-mechanism marginal returns; retire
below baseline for 5 straight probes). Budget in probes/week, not
dollars; spend caps per probe class (packaging cheapest, delivery
mid, new-character most expensive).

## 10. Implementation mapping

- FinalBuilds2: hypothesis registry, probe scheduler (control-protocol
  enforcement), outcome ingestion, Thompson sampler, gold promotion.
- Freaktown: CharacterGraph (canon/story/strategy), JokeBlock v1 ×10,
  structured JokePlan generator (retire whole-set mutation for Nolan),
  delivery.v1 + PerformanceEngine, EpisodePack manifests, reply lineage.
- Influence: packaging probes, scheduling, review canvas, analytics
  ingestion (24h/7d snapshots + comment harvest), Pogtown vote tooling.
- qprivately: publish/spend grants, receipts on every consequential step.
- Pogpet (read-only here): commercial-affinity events on merch conversion
  (character × buyers, no fictional state) — purchase-proves-attachment
  signal back into theory.
- New tables: `probes`, `gold_runs`, `comment_labels`, `mechanism_edges`
  (character × mechanism → strength + n + refs). JSONL first, tables when
  queries hurt.

## 11. Phase plan (MVP loop first, per endgame doc §6)

1. JokeBlock v1 ×10 + Nolan CharacterGraph v1 (canon/story/strategy).
2. Structured plan → delivery → PerformanceEngine → one EpisodePack.
3. Packaging probe on it (2 titles × 2 thumbnails).
4. Publish (grant), collect 7d outcomes + comment mine.
5. Promote or kill exactly one hypothesis + one mechanism edge.
6. Spawn the next probe from the lesson. Loop until a gold run, then
   vary it. Stop designing; start falsifying.
