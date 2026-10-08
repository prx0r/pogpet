# Comedy OS — what was built, and what it's for

One sentence: **a theory-aware library of JokeBlocks that mines reality
for comedy, proves premises on socials, and feeds performers — on
oddhobb.com today, on the Freaktown stage tomorrow.**

## The pipeline

```text
REALITY (events, lore, memes)
  → JOKEBLOCK (facts + culture, append-only, timestamped)
  → THEORY OPERATORS (12 world-state functions, not tags)
  → PREMISES (perception shifts, GTVH-structured)
  → DERIVATIONS (situation trees: if true, what follows?)
  → INSTANTIATIONS (comic / meme / video / card / set)
  → ARTIFACT (disposable) → PERFORMANCE → RESPONSE TRACE
  → COMEDY JUDGE (pairwise + vetoes + taste prior)
  → LEARNING GRAPH (blocks, theories, audience, performers update)
```

Backwards direction: any bit (transcript, comic, tweet) classifies into
theory tags, so stage evidence and generated drafts speak one language.

## Inventory (this tree, all tested)

| Piece | Path | Count / state |
|---|---|---|
| JokeBlocks | `templates/blocks/` | 27, 6 canonical anchors v1 |
| Theories | `templates/theories.json` | 15 with support scores |
| World operators | `backend/creative/world_ops.py` | 12 state functions |
| Question operators | `backend/creative/operators.py` | 12 + `compose()` |
| Fingerprints | `templates/fingerprints.json` | 3 models' verbal tells |
| Formats | `templates/formats.json` | 10 (incl. news_vs_discourse) |
| Evergreen tree | `templates/evergreens.json` | 6 trunks, 40 leaves, event activation |
| Premises packs | `templates/premises/` | 60+ premises + 6 canonical embodiment |
| Comics | `templates/comics/` | 9 validated 4-panel scripts |
| ComedyJudge | `backend/creative/judge.py` | pairwise + swap + vetoes + taste |
| Backwards classifier | `backend/creative/classify.py` | transcript → theory tags |
| Regulars | `backend/creative/regulars.py` | fertility/coherence/response |
| Delivery traces | `backend/creative/delivery.py` | schema frozen, harness parked |
| Performance ledger | `backend/creative/performance.py` | posts + metrics + weights |
| Duel API + page | `/api/creative/duel`, `/funnier` 😂 tab | live, tested end to end |
| Meme video | `backend/meme_video.py` | panels → 1080×1920 MP4 |
| Source events | `templates/events/` | claim-level status + sources |

Docs: `joke-blocks.md` (ontology) · `theory.md` + `theory-bank.md` (theory +
operators) · `comedy-graph.md` (full architecture, verbatim) ·
`meme-engine.md` (post → ledger → reweight) · `performance-logic.md`
(sets as proofs, delivery traces) · `genial.md` + `original-premise-bible.md`
(founder bibles) · `viral-card-library.md` (cards contract).

## Relevance to Freaktown (`~/freaktown`)

Freaktown built the **delivery compiler** (`comedy/corpus, rhythms,
director, evaluator`): timing, character fit, stage performance, reaction
learning. This tree is its **upstream material mine**. The contract:

- Our premises + derivations are what their director stages. A premise
  carries theories, oppositions and characters — everything `director.py`
  needs to cast and time it.
- Our ledger theory-support scores feed their `evaluator.py` mechanism
  stats: same question (what works), asked at different layers (material
  vs delivery). Shared vocabulary: theories, operators, callbacks.
- Our regulars (empirically discovered identities with callbacks) become
  their recurring performers with persistent graphs.
- Their stage returns the clean signal our ledger can't get from socials:
  laugh onset/decay per beat → delivery traces → mechanism × delivery
  knowledge no transcript corpus holds.
- Division of labor, frozen: **figgsite mines what's funny, Freaktown
  learns how to perform it.** Neither duplicates the other.

## Relevance to oddhobb.com

- **`/funnier` (😂 tab):** Tinder-for-jokes. Two comics, pick one —
  visitors train the judge for fun, and every vote is a labeled preference
  for the exact model that ranks their future cards. Engagement feature
  and training pipeline in one page.
- **Originals shelf:** winning premises become buyable non-personalised
  cards (`templates/original/`). Proven-public taste, zero personalization
  cost, sold while the visitor's own card renders.
- **Personalization engine:** the site's card/matcher stack runs on
  premise weights the public already voted for — a Dad card built from
  machinery the internet laughed at.
- **Funnel:** comics establish taste (X → profile → oddhobb tab) and
  monetize it (personalised cards, gift packs, Shopify drafts). The
  ledger's profile-taps metric measures exactly this step.
- **News channel (`news_vs_discourse`):** verified event + timeline
  reaction as a content format — doubles as the store's voice on current
  events and as proof of the facts-vs-culture split to visitors.

## What stays parked

Performance/delivery harness (Qwen omni key), fal plates (FAL_KEY),
automated posting (X API), Pogtown theatre runtime. The library is the
atom; everything else emerges when keys and traffic justify it.
