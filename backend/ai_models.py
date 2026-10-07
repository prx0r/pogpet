"""AI model registry — normalized aggregators for OddHobb's machine needs.

Same shape as suppliers.py but for intelligence instead of plastic: every
model declares provider, endpoint, capability tags, pricing grade, key
location, and docs. Estimates are NEVER faked — quote-grade until a live
call returns a number. No keys live here; integrations read env-only and
every paid call is ask-first with a ledger, same money rules as Meshy.

The three aggregators cover everything with two keys if we're lean:
  openrouter — the brain (text, vision, TTS/STT, image + video gen endpoints)
  fal.ai     — the media specialist (lipsync, avatars, Tripo 3D, 1000+ models)
  alibaba    — the value lane (cheapest bulk image, voice clone, Wan video)
fal hosts Alibaba's Wan models too, so fal + openrouter is the minimal pair;
Alibaba direct earns its key on volume (bulk card art, voice clones).
"""
from __future__ import annotations

PROVIDERS: dict[str, dict] = {
    "openrouter": {
        "label": "OpenRouter (unified LLM gateway, 300+ models, 60+ providers)",
        "home": "global", "key_env": "OPENROUTER_API_KEY",
        "auth": "Bearer key, OpenAI-compatible base https://openrouter.ai/api/v1",
        "billing": "credits, provider pricing passed through, no inference markup",
        "docs": "https://openrouter.ai/docs (llms.txt at /docs/llms.txt)",
        "notes": "The brain lane: one key, model fallbacks, vision/TTS/STT/image/video endpoints. Media is thinner here (no 3D, no faceswap) — pair with fal.",
    },
    "fal": {
        "label": "fal.ai (generative media platform, 1000+ model APIs)",
        "home": "global", "key_env": "FAL_KEY",
        "auth": "Key $FAL_KEY, per-model endpoints + programmatic pricing API",
        "billing": "per-output (image/video/second) or per GPU-second; billed on success only",
        "docs": "https://fal.ai/docs (llms.txt at /docs/llms.txt)",
        "notes": "The media specialist: lipsync, avatars, Tripo 3D, Flux/Nano Banana image. Also hosts Wan video models, so it covers Alibaba's video lane without a second key.",
    },
    "alibaba": {
        "label": "Alibaba Cloud Model Studio (Qwen + Wan, Singapore region)",
        "home": "global", "key_env": "DASHSCOPE_API_KEY",
        "auth": "Bearer sk-*, workspace domains per region (Singapore: ap-southeast-1)",
        "billing": "per image (~$0.02) / per video-second; region keys not interchangeable",
        "docs": "https://docs.modelstudio.console.alibabacloud.com (llms.txt at /llms.txt)",
        "notes": "The value lane: cheapest bulk card art, portrait repaint, voice cloning, Wan digital human. Direct key earns out on volume; otherwise use fal's hosted Wan.",
    },
}

# Our machine needs → ranked model options. `est` mirrors suppliers.py grades:
# "live" = verified price below, "quote" = call the pricing API first.
MODELS: dict[str, dict] = {
    # ── brain: jokes, guide turns, Oddy ──────────────────────────────
    "jokescheap": {
        "need": "joke sets, premises, riffs, guide turns (cheap, fast)",
        "options": [
            {"provider": "openrouter", "endpoint": "meta-llama/llama-3.3-70b-instruct:free",
             "notes": "free tier, no card — ramble + drafts", "est": "quote"},
            {"provider": "openrouter", "endpoint": "google/gemini-3.6-flash",
             "notes": "cheap + fast, vision-capable", "est": "quote"},
        ],
    },
    "brainbest": {
        "need": "hard reasoning, Oddy shopper brain, taste profiles",
        "options": [
            {"provider": "openrouter", "endpoint": "anthropic/claude-opus-4.6",
             "notes": "frontier quality, failover across providers", "est": "quote"},
            {"provider": "openrouter", "endpoint": "openai/gpt-5.6-luna",
             "notes": "$1.00/1M in — latency-sensitive automation", "est": "live"},
        ],
    },
    "photorubric": {
        "need": "makeability rubric — can we make this photo? (vision)",
        "options": [
            {"provider": "openrouter", "endpoint": "google/gemini-3.1-pro-preview",
             "notes": "1M context, spatial perception; image_url inputs", "est": "quote"},
            {"provider": "openrouter", "endpoint": "openai/gpt-5.6-luna",
             "notes": "vision + reasoning, cheap", "est": "live"},
        ],
    },
    # ── card art ─────────────────────────────────────────────────────
    "cardart": {
        "need": "greeting-card art, scenes, motifs (bulk, cheap)",
        "options": [
            {"provider": "alibaba", "endpoint": "wanx-v1",
             "notes": "~CNY 0.16/image (~$0.02), 500-image free quota — bulk lane",
             "est": "live"},
            {"provider": "fal", "endpoint": "fal-ai/flux/dev",
             "notes": "$0.025/image programmatic pricing — quality lane", "est": "live"},
            {"provider": "openrouter", "endpoint": "bytedance-seed/seedream-4.5",
             "notes": "1K/2K/4K via /api/v1/images", "est": "quote"},
        ],
    },
    "cardtext": {
        "need": "card art WITH legible headlines (text rendering)",
        "options": [
            {"provider": "alibaba", "endpoint": "qwen-image-3.0",
             "notes": "every-word-renders line; long-text layouts", "est": "quote"},
            {"provider": "fal", "endpoint": "fal-ai/flux-2-pro",
             "notes": "BFL typography strengths", "est": "quote"},
            {"provider": "openrouter", "endpoint": "openai/gpt-image-1",
             "notes": "reference-image editing via input_references", "est": "quote"},
        ],
    },
    "portraitrepaint": {
        "need": "photo → watercolor/oil keepsake (cards, frames)",
        "options": [
            {"provider": "alibaba", "endpoint": "wanx-style-repaint-v1",
             "notes": "preserves facial features; stylization global/local", "est": "quote"},
            {"provider": "alibaba", "endpoint": "wan2.5-image-edit",
             "notes": "text-instruction edits + multi-image fusion, subject-consistent",
             "est": "quote"},
        ],
    },
    # ── perform: lipsync, avatars, motion ────────────────────────────
    "lipsync": {
        "need": "still + audio → talking character (perform clips)",
        "options": [
            {"provider": "fal", "endpoint": "fal-ai/sync-lipsync/v3/image-to-video",
             "notes": "$0.1333/output-second, any illustration + voice track",
             "est": "live"},
            {"provider": "fal", "endpoint": "fal-ai/ai-avatar/single-text",
             "notes": "MultiTalk: text→speech→lipsync in one call", "est": "quote"},
            {"provider": "alibaba", "endpoint": "wan-digital-human",
             "notes": "image + audio → lipsync + expressions + head/body motion",
             "est": "quote"},
        ],
    },
    "motiontransfer": {
        "need": "record-yourself → character moves (image-to-action)",
        "options": [
            {"provider": "alibaba", "endpoint": "wan2.2-animate-move",
             "notes": "std/pro modes; reference-video motion onto photo, static bg",
             "est": "quote"},
            {"provider": "openrouter", "endpoint": "alibaba/wan-2.7",
             "notes": "frame_images first/last-frame via /api/v1/videos", "est": "quote"},
        ],
    },
    "characterswap": {
        "need": "faceswap — person from photo into video, bg kept",
        "options": [
            {"provider": "alibaba", "endpoint": "wan2.2-animate-mix",
             "notes": "async create-task → poll; public image URL in", "est": "quote"},
        ],
    },
    # ── voice ────────────────────────────────────────────────────────
    "voicetts": {
        "need": "greeting/set voiceover (cheap, many voices)",
        "options": [
            {"provider": "openrouter", "endpoint": "openai/gpt-4o-mini-tts",
             "notes": "/api/v1/audio/speech, mp3/pcm; instructions tone control",
             "est": "quote"},
            {"provider": "openrouter", "endpoint": "google/gemini-flash-tts",
             "notes": "cheap lane, same endpoint", "est": "quote"},
        ],
    },
    "voiceclone": {
        "need": "Dad's voice speaks the greeting (consented clone)",
        "options": [
            {"provider": "alibaba", "endpoint": "cosyvoice-v3.5-plus",
             "notes": "voice cloning line; ref.wav + ref.txt bank pattern", "est": "quote"},
            {"provider": "openrouter", "endpoint": "tts-voice-clone",
             "notes": "stateless: reference audio inline per request, no voice upload",
             "est": "quote"},
        ],
    },
    "voicetranscribe": {
        "need": "voice-room STT, set transcription",
        "options": [
            {"provider": "openrouter", "endpoint": "openai/whisper-large-v3",
             "notes": "/api/v1/audio/transcriptions, base64 in", "est": "quote"},
            {"provider": "alibaba", "endpoint": "fun-asr-realtime",
             "notes": "realtime lane for the voice room", "est": "quote"},
        ],
    },
    # ── mesh ─────────────────────────────────────────────────────────
    "meshgen": {
        "need": "photo → 3D mesh (second opinion next to Meshy)",
        "options": [
            {"provider": "fal", "endpoint": "tripo3d/h3.1/image-to-3d",
             "notes": "$0.10–0.30 +$0.20 detail +$0.05 quad; GLB/PBR/FBX out",
             "est": "live"},
            {"provider": "fal", "endpoint": "tripo3d/h3.1/text-to-3d",
             "notes": "text descriptions → mesh (props, toppers)", "est": "live"},
        ],
    },
}


def options_for(need: str) -> list[dict]:
    """Ranked model options for one of our machine needs. Unknown need → []."""
    entry = MODELS.get(need)
    if not entry:
        return []
    out = []
    for o in entry["options"]:
        p = PROVIDERS.get(o["provider"], {})
        out.append({"need": entry["need"], **o,
                    "key_env": p.get("key_env", ""),
                    "provider_label": p.get("label", o["provider"])})
    return out


def needs() -> list[str]:
    """Every machine need we have a model answer for."""
    return sorted(MODELS.keys())
