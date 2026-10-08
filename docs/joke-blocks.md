# JokeBlocks — the theory-aware library

> Frozen ontology: **facts → connection → comic model → theories → results.**
> A JokeBlock stores comic potential. A premise selects one interpretation.
> A derivation explores its consequences. An instantiation expresses one
> consequence in a medium. Performance tells us whether the theory was right.

## Files

| Path | What |
|---|---|
| `templates/blocks/*.json` | one block per file: facts + culture + theories + lineage |
| `templates/theories.json` | 12 hypotheses, each with a support score the ledger moves |
| `templates/fingerprints.json` | per-model verbal tells (the participation game: name the model from one word) |
| `templates/premises/*.json` | premise packs; entries carry `source_lore` + `format` |
| `backend/creative/blocks.py` | loader, validation, premise index, children/lineage |
| `backend/creative/operators.py` | 12 theory operators: block in, premise candidates out |
| `backend/creative/performance.py` | ledger with `block_id`; `family_scores` + `block_scores` |

## Block schema (v1, frozen)

`id · parent · tags · sources · facts[{claim, status}] · culture ·
comic_claim · reality_model · comic_model · theories[{id, strength}] ·
tensions · characters · premise_ids · derivations[{id, premise, format,
occasion}] · references[{url, date, note}] · minted · results`

- `facts[].status` is the epistemic guardrail: `confirmed / reported /
  observed / unconfirmed / comic_model`. The engine may play with the comic
  model but never assert an unconfirmed fact (see `plague_lab`: plague as
  cause of death stays `unconfirmed`, so every derivation treats it as the
  comic model, not a claim).
- `culture` = analogues, active_frames, meme_objects, staleness,
  audience_camps, heat. Stale references (`toilet_paper: 0.91`) lose even
  when technically valid.
- `parent` nests blocks: `sycophancy_design` → `pickup_routine`,
  `yesman_parent`, `digestible_mask`. Children inherit the crux, carry
  their own quotes.

## Operators

`INCONGRUITY · SCRIPT_OPPOSITION · IDENTITY · STATUS · RIGIDITY ·
BISOCIATION · BENIGN_VIOLATION · LITERALISE · ESCALATE · SELF_AWARENESS ·
AUDIENCE_SUPERIORITY · ROLE_REVERSAL` — each a dumb template function, so
diversity comes from the intellectual operation, not the voice. `run_all`
over a block yields the candidate list; an LLM or human executes the best.

## Loop

Watcher proposes lore → human mints block → operators propose premises →
derivations post everywhere → ledger scores blocks AND families → winners
get video → recurring cast emerges (characters whose callbacks beat their
novel material). Delivery and theatre stay parked; the library is the atom.
