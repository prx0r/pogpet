# Review: combined endgame doc (verified 2026-10-10 against box + GitHub)

> Source: `vision/combined-endgame.md` (R2 `combinedendgame`, 31KB).
> Checked: freaktown trial/avatar-flow @7548a95 (doc cites 4722b9f —
> we are past it), finalbuilds2, influence main @6999304, qprivately.
> Method: file-exists + content-spot-check per claim, read-only.

## Confirmed accurate

- **Freaktown 9/10**: CHARACTER_PACK (211L, Nolan included), interview.py
  state machine (facts/threads/contradictions/callbacks/targets),
  delivery sequencer (8 beat types + 8 delivery controls),
  versioned PerformanceEngine + 6 presets, comedy_generator loop,
  keyword performance_compiler, show_runtime laugh metrics, Ella/ChatGPT/
  Stream judge panel, reply lineage (contract + fixture + test, no
  backend runtime yet).
- **FinalBuilds2 core**: deterministic assignment, process-attribution
  with the observational-vs-causal disclaimer baked in, hypothesis
  promotion gates (out-of-sample + calibration + posterior ≥0.90),
  idea scoring, worktree builders, append-only event graph + hash-chained
  ledger.
- **Influence**: HLoop present/decide (banked prediction required),
  products/primitives, experiments dir.
- **qprivately**: grants.py verify_grant present.
- **Separation doctrine** (six organs + Jev-as-evaluator) matches what the
  repos actually enforce — no repo currently owns another's layer.

## Corrected / scoped

- **CharacterGraph does not exist** (doc is honest: "biggest missing
  layer"). Only docs proposals + a different triple in
  COMEDIAN-LEARNING.md. This is the correct next Freaktown build, not a
  description of current state.
- **No EpisodePack/ReviewBundle/human-canvas code exists anywhere**
  (finalbuilds2 or influence). Doc frames them as proposals — keep them
  that way until built; do not reference them as live.
- **Creative production/distribution adapters**: finalbuilds2 has
  integrations/ + packaging scripts, not creative adapters. Gap is real.
- **Doc's freaktown pin (4722b9f) is stale**; verified at 7548a95 instead.
  No contradictions found with the newer tree.

## Pogpet-side build items (ours — everything else belongs to other repos)

1. **Pack read API** (already Round 14 14-7): the exact surface Influence
   needs — product truth without Freaktown internals. Unblocks the
   EpisodePack→Product Pack symmetry.
2. **Commercial-affinity events**: on order fulfilment, emit a
   FinalBuilds2-compatible event (character/subject, pack, conversion
   context — never fictional state). This is the OddHobb→theory feedback
   edge; keep it to receipts, no opinions.
3. **No experiment code in pogpet**: hypotheses, arms, grants, receipts
   live in FinalBuilds2/qprivately. Pogpet exposes facts + artifacts and
   consumes promotion decisions. Enforce by refusing any
   experiments/ directory here.
4. **JokeBlocks in marketing**: Influence-side concern; our only duty is
   the pack `marketing` block (positioning/angles/claims/forbidden) so
   their agents have facts to work with. Already schemad.

## Suggested build order (cross-repo, our visibility only)

1. CharacterGraph v1 (Freaktown) + JokeBlock v1 ×10 — unblocks everything.
2. EpisodePack manifest (Freaktown) + ReviewBundle (Influence).
3. Pack read API + affinity events (pogpet — items 1–2 above).
4. One Nolan loop end to end, then stop designing.
