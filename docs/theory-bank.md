# Theory bank — structures, combinations, autonomy, feedback

## The 12 theories (operators)

`incongruity · resolution · benign_violation · bisociation ·
identity_contradiction · status_reversal · self_awareness · rigidity ·
audience_alliance · repetition_variation · mask_collision · specificity`

Each is a search operator over a JokeBlock (`backend/creative/operators.py`).
Full hypotheses + support scores: `templates/theories.json`.

## Known-good combinations (signatures)

Discovered from what actually landed. Store new ones here as the ledger
confirms them.

| Signature | Why it works | Example |
|---|---|---|
| identity_contradiction + status_reversal + specificity | contradiction names the laugh, reversal aims it, specificity makes it real | lab assistants (PI: Claude, timesheet) |
| bisociation + literalise + escalation | two worlds collide, then the collision is followed to step 10 | day-4 log (SENSORY CALIBRATION) |
| mask_collision + self_awareness + resolution | the mask slips, the wearer knows, the audience re-reads everything | digestible mask off |
| benign_violation + distance + specificity | dread made safe by detail and displacement | welfare haunted house |
| repetition_variation + escalation + callback | rule established, mutated, then the first beat returns | Christmas lists before/after |

## Classical structures (delivery-side, combine freely with above)

Rule of three · callback · misdirection · reversal · analogy ·
exaggeration · understatement. These are *arrangements* of a premise, not
premises themselves: any theory-combo can be delivered through any of them.

## Autonomy loop

```text
watcher (lore) → human mints block → operators propose premises →
rank by theory support × culture heat × staleness → execute top 5 →
post everywhere (one strip, N wrappers) → ledger scores blocks,
premises, theories, formats → winners get video + callbacks →
regulars emerge (callbacks beating novel material)
```

Humans gate twice: which lore becomes a block, which probes go public.
Everything between is machinery. Theories gain support from evidence;
stale references decay; blocks retire instead of embarrassing us.

## Feedback levels (what engagement teaches)

1. Premise level: did this interpretation land?
2. Block level: does this reality keep generating?
3. Theory level: does this mechanism work *for this audience*?
4. Format level: does this mechanism need panels, dialogue, or news?
5. Delivery level (parked): what pause/gaze/tempo does each mechanism want?

## Product v1: one block in, five comics out

`backend/creative/comics.py` implements it: candidates (operators, offline)
-> select_five (greedy theory-coverage) -> rank (jev calibrated scores when
`OPENROUTER_API_KEY` exists, transparent heuristic otherwise — never raises)
-> validate_script (title, premise, 4 panels, caption, known theories) ->
to_video_inputs (plates + dialogue -> `meme_video.slideshow`) and to_card
(panel 4 + caption -> single artwork spec). Canonical proof:
`templates/comics/claude_wetlab_5.json` — 5 premises, 5 distinct combos,
one block.

## ComedyJudge (`backend/creative/judge.py`, `tests/test_judge.py`)

Pairwise, never absolute: vetoes first (hard gates, offline), order-swapped
jev choice when a key exists (disagreement = tie), rubric dimensions +
ledger taste multiplier otherwise. Tinder pairs come from adjacent ranks
(active learning on the boundary); every click lands in append-only
`data/comedy_prefs.jsonl`. North-star metric: Precision@5.

## World operators (`backend/creative/world_ops.py`)

Tags became functions: `status_invert(A, B)` produces a new state, not a
label. 12 ops (status_invert, double_interpret, rigidify, split_knowledge,
mistake_identity, repeat_variation, identity_contradict, unmask, literalize,
bisociate, expose_self_blindness, character_violation) over
relations/beliefs/status/identities/rules. GTVH fields ride on premises as
the IR between block and premise. jestry S/R/E lands in the judge as
`resolution_efficiency`. Corpora to mine later (not fetch now):
shakedracor, romdracor, moliere TEI, StandUp4AI outcomes, Kill Tony
weak-supervision — annotate state, not text.
