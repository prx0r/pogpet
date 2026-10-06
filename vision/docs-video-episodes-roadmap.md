# Video & Episodes Roadmap — from clips to promptable shows

Where the comedy-club-in-a-splat future meets the parts already on disk.
Companion to `roadmap.md` (shop stages) and `docs/variant-engine.md`
(variants/taste). Read-only survey of `freaktown` and `pogtown-mvp`; all
OddHobb build work lands here in `figgsite`.

## Scorecard vs roadmap.md

| roadmap.md stage | Status | Evidence |
|---|---|---|
| 1. Populate the store (Christmas 20) | **Done** | 23 lines live, tiers, photos, spin |
| 2. Mesh in videos | **Half** | Free video path + feed live; subject-mesh performance = this doc |
| 2b. Make your own / digital downloads | **Half** | Controlled custom live; paid unlocks unwired |
| 3. People layer (Dad vault) | **Half** | Subject profiles + motifs live; birthdays stored, vault/claim pending |
| 4. Agentic ordering | **Half** | MCP fullchain + card reserve; ACP/AP2 mandates future |
| 5. Q4 merchandising | **Live** | Sections, ad-six, price ladder |
| Production matrix | **Draft** | `factory_registry.json` + gates; samples pending |
| Post-Xmas probes | Not started | — |

## What already exists (no new research needed)

**Script.** `freaktown/show.py:147` runs a whole talent night (lineup → Ella
intro → acts → audience sim → judge → outro + transcripts). `figgsite`
`backend/video.py` writes punchy sets. `pogtown` standup rules + deterministic
`ellaScore` judge without any LLM. Writing is solved.

**Voice.** Edge-TTS everywhere, free, streaming, with word timings
(`freaktown/backend/services/edge_tts.py:58`). Ryan/Aiden preset drops already
on disk. Qwen voice bank: kernels written (`kaggle-qwen/qwen_kaggle.py`),
needs only an `HF_TOKEN` secret attached — custom Dad-voices without paying.

**Music/SFX.** `freaktown/sound_synth.py` is stdlib-only procedural walkouts
today, zero cost. Stable Audio path is authorized with prompt compilers and a
seed-cache contract (`docs/HANDOFF_STABLE_AUDIO.md`); needs CUDA (Kaggle),
`FAL_KEY`, or falls back to procedural. Intro music is a solved problem at
three price points: free, free-GPU, paid-API.

**Lipsync.** `freaktown/packages/stage-runtime` has the full client stack:
`LipSyncAdapter` (visemes + jawOpen + word-timeline), 4-bus `AudioBus`
(voice/music/sfx/crowd with ducking), cue executor, camera director with
named shots. The dog GLB already carries an injected `jawOpen` morph
(`figgsite/scripts/add_jaw_morph.py`), `pose_lipsync.py` baked a 39s shareable
MP4, and `site/stage.html` plays it live. Mouths move today.

**Stage & feed.** `figgsite` videos tab is a vertical swipe feed already
playing muted-loop MP4s. `pogtown` contributes the Blue Room flow, freak-pack
portable identity, and the doctrine that packs are authoritative while
Unreal/web/iOS are just renderers. `site/rehearse.html` (new) scrubs GLB
clips with poster export. The Unreal/LiveKit cinematic feed stays parked —
correctly; it was never needed for episodes.

## The episode compiler (what to build)

Same shape as the product compiler. One prompt compiles down four layers:

```text
prompt ("Dad bombs at the comedy club, 30s, dry")
  → SCRIPT   write_set / show.py lineup (existing)
  → VOICE    edge-TTS now, Qwen bank voice later (existing + HF_TOKEN)
  → MUSIC    procedural walkout/SFX now, Stable Audio bank later
  → BODY     validated rig + jawOpen from audio envelope (existing)
  → ROOM     photo-composite scene now, splat room later
  → FEED     vertical MP4 into the existing videos tab
```

Episode spec v1 (mirror the product canonical format):

```text
episode: {subject, room, performance, voice, music, seed, revision}
room:    photo_composite | rigged_template | splat   (only the first exists)
```

Re-roll, keep/discard, taste weights, and seed-pinned checkout all port
directly from the variant engine — a take is a variant with a timeline.

## Build order

1. **Episode job v1 (this box, $0):** prompt → script → edge voice →
   procedural intro/SFX → jawOpen bake → MP4 → feed. All parts exist; the
   work is the job + cache keys, not new tech. Reuses the card-jobs pattern
   (queued/running/ready, immutable revisions).
2. **Attach `HF_TOKEN` to both Kaggle kernels:** Qwen voice bank + Stable
   Audio walkouts. Unlocks custom voices and real intro music for free-GPU
   cost. Nothing to write; it is an ops action.
3. **Room ladder:** marquee/poster compositing (L1 card work in a tuxedo) →
   one validated celebration rig (putt/cheer, explicit ownership binding,
   never blind-rig a random Meshy mesh) → splat rooms when the cost bends.
4. **Continuity:** recurring cast, running gags from taste data, Christmas
   special with the shop ornament hanging in the scene. Series bible as a
   side effect of gift orders.
5. **Calendar loop + episode gifting:** birthday in 9 days → three rendered
   keepsakes, one checkout. Same funnels as physical gifts.

## What NOT to build

- No Unreal/LiveKit programme feed for episodes (parked, correctly).
- No neural video generation (the deterministic bake is the product).
- No second TTS vendor until the Qwen bank runs (edge covers now).
- No rig-compatible assumptions: template rigs only, validated binding.
