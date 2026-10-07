# Meme engine — the timeline trains the algo

One strip, every feed, and the results flow back into what we make next.

## The loop

```
premise (with source_lore) → render plates → post everywhere → ledger
    → weekly reweight → catalog ?rank=top + next render batch → site engine
```

**Every platform is a tester.** Posting to X, TikTok, Instagram and YouTube
costs nothing extra (one strip, N wrappers), so all four report back — not
just X. Formats per platform:

| Platform | Format | How |
|---|---|---|
| X | `single_panel` | native image + joke in post text |
| TikTok | `slideshow` | native swipeable panels, free |
| Instagram | `short_video` | 1080×1920 MP4 (`backend/meme_video.py`) |
| YouTube | `short_video` | same MP4 as Shorts |

X runs first (cheapest signal, hours). Slideshows reuse the same assets
for free. Video renders only for winners — never animate a strip the
timeline ignored.

## Video assembly

`backend/meme_video.slideshow(panels, captions, voice)` → slow push-in per
panel, deadpan voiceover (same edge-tts path as `video.tts`), captions
burned deterministically. Joke text never lives in the plates — same rule
as the card pipeline. Splat rooms (`backend/marble.py`) can replace the
plain backdrop once `MARBLE_API_KEY` lands; assembly doesn't care.

## source_lore (required on every premise)

Each premise carries the real cultural artifact, not a paraphrase:

```json
"source_lore": {
  "event": "Anthropic's Opus 4.6 card: Claude assigned itself a 15-20% probability of being conscious",
  "phrase": "15-20% probability of being conscious",
  "date": "2026",
  "community": "Anthropic users, AI welfare discourse",
  "recognition": "The single most quoted passage of the 4.6 system card."
}
```

Packs: `templates/premises/halloween_families.json` (lore-anchored),
`templates/premises/original_families.json` (Christmas). Dropped:
`pumpkin_hallucination` — motif repetition with no mechanism underneath.

## Ledger + reweight

- `backend/creative/performance.py` — `record_post()` on publish,
  `record_metrics()` when numbers come back. Append-only JSONL under
  gitignored `data/` (`meme_performance.jsonl`). Engagement = likes +
  5×shares + 3×profile-taps + views×completion (shares and taps dominate
  because they mean the joke traveled or converted).
- `scripts/meme_reweight.py` — weekly: prints the family table, snapshots
  `data/meme_weights.json`.
- `GET /api/creative/catalog?rank=top` — featured ordering follows whatever
  is hot. No signal yet → identical order (safe default). Catalog templates
  opt into families via a `family` key (3 tagged so far).

## Why this is the business

Somebody sees a strip and thinks "holy shit, they know the lore", follows
the account, then discovers the same comedic machinery pointed at *their*
dad, friend, company or niche. The comics establish taste; the personalised
cards monetize it. The site engine runs on premise weights the public
already voted for.
