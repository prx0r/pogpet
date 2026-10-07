# AI models — the normalized machine registry (fal.ai · Alibaba · OpenRouter)

> Status: registry live, no keys stored, no spend yet (2026-10-06). Code truth:
> `backend/ai_models.py` (`PROVIDERS`, `MODELS`, `options_for`), pinned by
> `tests/test_ai_models.py`. Money rules mirror Meshy: ask-first, env-only keys,
> per-call ledger. Docs hubs: `https://fal.ai/docs/llms.txt`,
> `https://docs.modelstudio.console.alibabacloud.com/llms.txt`,
> `https://openrouter.ai/docs/llms.txt`.

## Why three aggregators, and why these three

One key per aggregator instead of one key per model lab. Each covers what the
others price badly:

| Aggregator | Is | Best for us | Weak at |
|---|---|---|---|
| **OpenRouter** | unified LLM gateway, 300+ models, 60+ providers, one OpenAI-compatible key, pass-through pricing, failover | the **brain**: jokes, guide turns, Oddy, photo rubric (vision), TTS/STT endpoints, image + video-gen endpoints | media depth — no 3D, no faceswap; free tiers carry their own caps |
| **fal.ai** | generative media platform, 1000+ production model APIs, per-output billing, programmatic pricing API | the **media specialist**: lipsync avatars, Tripo 3D second opinion, Flux image quality | LLM brain work (not its product); GPU-second fallback billing on rarer models |
| **Alibaba Model Studio** | Qwen + Wan first-party + third-party plaza (109 models), Singapore region | the **value lane**: ~$0.02 bulk card art, portrait repaint, voice cloning, Wan digital human | second key + workspace domains; Beijing/Singapore keys don't interchange |

Two keys are enough: **OpenRouter + fal**. fal hosts Wan video models itself, so
Alibaba's video lane is reachable without the Alibaba key; Alibaba direct earns
its key on volume (bulk card art, voice clones).

## The comparison that matters

- **Pricing honesty.** fal wins: every model page shows unit + unit price and a
  `GET /v1/models/pricing` API returns it programmatically — estimates can be
  computed, not guessed. OpenRouter passes provider pricing through with no
  inference markup (watch the ~5% credit-purchase fee and a few models priced
  above direct). Alibaba publishes per-image/per-second tables (~$0.02 image,
  video per second) with a 500-image free quota on the base model.
- **API shape.** OpenRouter is one OpenAI-compatible base plus dedicated
  `/api/v1/images`, `/api/v1/videos` (async job → poll), `/api/v1/audio/speech`,
  `/api/v1/audio/transcriptions`. fal is per-model endpoints with sync + queued
  + streaming + realtime variants and copy-paste SDK calls per model page.
  Alibaba is workspace-domain REST + DashScope SDK, async create-task → poll for
  anything slow (character swap, video).
- **Regions.** OpenRouter and fal are global single endpoints. Alibaba splits
  Beijing vs Singapore keys and domains — we standardize on Singapore.
- **Playgrounds.** All three have try-before-code surfaces (fal gallery
  playground per model, Model Studio playground, OpenRouter chat room), so every
  spike below starts with eyes, not spend.

## What maps to our loops

`ai_models.options_for(need)` answers twelve needs today:

- **Cards:** `cardart` (bulk: wanx-v1 ~$0.02 → quality: flux/dev $0.025),
  `cardtext` (Qwen-Image legible headlines), `portraitrepaint` (photo → keepsake).
- **Perform:** `lipsync` (sync-3 $0.1333/s vs digital human),
  `motiontransfer` (record-yourself → character), `characterswap` (faceswap).
- **Voice:** `voicetts` (cheap multi-voice), `voiceclone` (Dad, consented),
  `voicetranscribe` (voice room STT).
- **Brain:** `jokescheap` (free-tier ramble), `brainbest` (Oddy frontier),
  `photorubric` (makeability vision).
- **Mesh:** `meshgen` (Tripo H3.1 image-to-3D $0.10–0.30 second opinion).

Spike order by closeness to revenue: portrait repaint + card art first (cheapest,
card lane), one lipsync run against existing edge-TTS audio second (compare with
the jaw-morph path before committing the perform lane), voice clone third
(needs the consent wording first), Tripo mesh comparison last (needs a sample
print to judge anyway).

## Key hygiene (non-negotiable)

`OPENROUTER_API_KEY`, `FAL_KEY`, `DASHSCOPE_API_KEY` — env-only, never committed,
never printed, never pasted into chats that log. First call on any new model is
a playground run or a free-tier call; the ledger pattern follows Meshy
(`data/<provider>_credits.jsonl`, gitignored). Beijing key must never be used
against Singapore domains.
