# Funny models — the moat is making funny models

> Status: pipeline live, first 5-star set generated 2026-10-07. Code truth:
> `backend/funny/` (`recipes.py`, `slop.py`, `writer.py`, `judge.py`, `persona.py`,
> `pipeline.py`), pinned by `tests/test_funny.py`. Spend: writer calls only,
> `approved=True` + `data/funny_ledger.jsonl`. Key: `OPENROUTER_API_KEY`, env-only.

## The architecture (profile in, structure ours, judgment ours)

The LLM supplies profile details (who Dad is, what happened). WE own
everything else: beat structure from Kill Tony shapes, the no-slop filter,
the rewrite loop, and the Ella verdict. The model writes WORDS into our
beats — never structure, never the final call.

```text
profile → beats → draft → noslop diagnose → guided rewrite (≤2) → Ella score → best
```

## The filter (prx0r/noslop, reference import)

`backend/resources/repos/noslop` (shallow, gitignored, never vendored — no
license on file). v6 pattern engine: NARR/NEG/CLICHE/FLAT fail sets;
**rule-of-three lists never fail** (3LIST is joke structure, not slop).
Short-form zero-tolerance regime for sets, captions, cards.

## The writers (uncensored, OpenRouter, pennies)

| Model | Price | Role |
|---|---|---|
| `cognitivecomputations/dolphin-mistral-24b-venice-edition` | $0.20/M in | default — best instruction-following; holds prose form, motif and rules |
| `thedrummer/unslopnemo-12b` | $0.40/M in | budget — anti-slop tuned but weaker form control (rhymes under persona pressure) |
| `anthracite-org/magnum-v4-72b` | $2.50/M in | premium — creative writing flagship |
| `gryphe/mythomax-l2-13b` | $0.08/M in | budget — uncensored classic |
| `x-ai/grok-4.7` | $2.00/M in | wit lane — dry mythologizing voice, no API unhinged mode (that's app-only); tested live, 4 stars |

No refusal on roast edge. A set costs ~$0.0001; the loop caps at 3 drafts.

## The judge (Ella rubric, deterministic)

Kill Tony shapes from 225 scored sets (freaktown heritage): 80–180 words,
specific opener, punchy closer, numbers, audience address, escalation room,
pivots, persona voice. 7+ points = 5 stars. $0, instant, no LLM.

## Training data on hand (the actual moat)

| Asset | Where | Size |
|---|---|---|
| Ella persona protocols (incl. Master Prompt for Generating Ella M) | `killella/data/ella_m/` | 3.7M |
| Kill Tony transcripts | `killella/data/transcripts/` | 580K |
| Comedy scripts | `killella/data/scripts/` | 3.0M |
| Clean transcript | `killella/data/transcript_clean.txt` | 100K |
| Freaktown Ella sets (20, edge-tts shaped) | `freaktown/ella_sets.md` | 124 lines |
| Ella scoring rubric + bible | `freaktown/` | — |
| Kill Tony upstream (bun stub) | `killtony-upstream/` | ref only |

Fine-tuning path (not started): this corpus is the moat-in-waiting. When
volume justifies it, train the house roast voice on it; until then the
pipeline above rents funny for a tenth of a cent per set.

## Missing upstream (404, not ours)

`prx0r/ellam` and `prx0r/funnylab` do not exist on GitHub (both 404).
`prx0r/noslop` exists and is integrated. `killella` (local, "Freak Town",
Ella M judges) is the closest Ella-M home on this box.

## External validation (Oct 2026 search)

- **Grok "Unhinged" is app-only**, not an API mode — and carries active
  litigation baggage. We rent grok-4.7's base wit through OpenRouter, never
  the brand or the risk.
- **hikariming/github-roast** (AGPL — pattern only, never code): deterministic
  score the LLM cannot change + LLM writes only the roast line. Independent
  invention of our pipeline shape.
- **HumorGen paper**: persona-based distillation into 7B beats larger baselines —
  backs persona.py; data curation beats scale for comedy.
- **BAHAHA/SemEval**: 40–50 candidates across comedian style templates, then
  rank. Our 3-attempt loop is the cheap version; volume up when it pays.
- **HumorRank**: GTVH-grounded pairwise judging tracks human agreement —
  future judge upgrade path beyond the rubric.
