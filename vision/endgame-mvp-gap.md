# Endgame MVP: gap analysis (2026-10-10, verified on box)

> Companion to `vision/endgame-pogtown-mvp.md` (the spec) and
> `vision/endgame.md` (the doctrine). This file is the build map: what
> exists, what's missing, who builds it, in what order.

## Present today (verified, not assumed)

- **freaktown**: character contracts (`contracts/character.v1.schema.json`,
  `freaks/*/character.json`), comedy-theory corpus (Freud PDF,
  ragthoven jokes TSV), docs (CHARACTER_PACK, COMEDIAN-LEARNING,
  POGTOWN-* system/plan/engine/roster). NO formal JokeBlock library, NO
  Nolan, NO CharacterGraph, NO JokePlan — those four are greenfield.
- **finalbuilds2**: on box (experiment substrate per earlier review).
- **influence**: on box (campaigns/distribution surface).
- **qprivately**: on box (grants/receipts).
- **pogpet (here)**: `backend/creative/experiments.py` — ProbeManifest
  freeze/validate, retention features, comment taxonomy v0, gold rates +
  candidate rule, E1–E7 ExplanationPlan, Finding lifecycle, novelty
  decay. Pure logic, 7 tests green, zero spend. No rendering, no
  publishing, no experiment daemon — by design.

## Missing, in dependency order

1. **JokeBlock v1 ×5–10** (freaktown): executable theory objects
   (requires/roles/audience+character models/compatible_next/failure
   modes). Nothing in pogpet depends on their internals — only ids +
   versions.
2. **Nolan CharacterGraph v1** (freaktown): canon/story/strategy for one
   character. Pogpet needs nothing but the character id + version.
3. **JokePlan → structured generator** (freaktown): replaces whole-set
   mutation for the MVP cast.
4. **EpisodePack + ReviewBundle + qprivately publish grant**
   (freaktown/influence/qprivately): the release envelope.
5. **Analytics ingestion + comment harvest** (influence): snapshots at
   comparable ages + comment threads into `comment_labels`-shaped rows.
6. **Outcome → Finding loop** (FinalBuilds2 consuming our evaluators):
   wire `retention_features`, `gold_rates`, `classify_comment`,
   `explanation_plan`, `make_finding` as the scoring library rather than
   reimplementing them.
7. **OddHobb physicalization edge** (here, later): pack read API already
   queued (Round 14 14-7); add commercial-affinity events when a proven
   character converts to merch. Nothing before a gold run exists.

## MVP acceptance (unchanged from spec §acceptance)

Preregistered theory → two controlled treatments → same stack render →
human-approved autonomous publish → verified age-normalized evidence →
interpretable finding → finding changes the next experiment. Prove the
loop once with Nolan before any second character, world, or rig.
