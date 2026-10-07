"""Voice brain: swappable conversational provider with barge-in.

Two jobs, never mixed: when the user talks to MUSE, Qwen stays out of it
(OddHobb only produces artifacts); when the user talks to ODDY directly,
a realtime provider carries the conversation and calls the same OddHobb
MCP tools Muse uses. No duplicated personal-shopper logic.

    QWEN_MODEL=qwen3.8-omni-flash-realtime (default)
    GEMINI_VOICE_PROVIDER=gemini_live|stub   (legacy path)
    GOOGLE_API_KEY / DASHSCOPE_API_KEY = server-side only, never leave box

Without keys the stub serves local echo sessions. Paid calls follow the
same ask-first + ledger discipline as Meshy (ledger: data/voice_ledger.jsonl).
Voice cloning additionally requires explicit enrollment consent
(voice_consents table) before any voice identity is stored.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request
import uuid
from datetime import datetime, timedelta, timezone

from . import config

PROVIDERS: dict[str, "BaseVoiceProvider"] = {}

WS_URL = ("wss://generativelanguage.googleapis.com/ws/google.ai.generativelanguage"
          ".v1beta.GenerativeService.BidiGenerateContent")

# OddHobb tool names the voice may invoke mid-conversation (function calling).
# Full JSON-Schema declarations are negotiated at session setup; names first.
VOICE_TOOLS = [
    "figg_guide_open", "figg_guide_turn", "figg_guide_packs",
    "figg_product_assets", "figg_product_personalise", "figg_checkout",
    "figg_greeting", "figg_card_save", "figg_card_render",
]

SHOPPER_INSTRUCTIONS = (
    "You are the OddHobb personal shopper. Start with the person, never a "
    "catalogue search: who are they shopping for, what occasion, what budget. "
    "Recommend from the OddHobb tools only. Prices are fixed tiers (3/5/10/15/20). "
    "Never invent products, prices, or delivery dates. Confirm before checkout."
)


class VoiceError(Exception):
    pass


class BaseVoiceProvider:
    name = "base"

    def is_configured(self) -> bool:
        return True

    def list_models(self) -> list[dict]:
        raise NotImplementedError

    def create_session(self, owner: str, tools: list[str] | None = None) -> dict:
        raise NotImplementedError


# RealtimeProvider is the devplan name for this exact interface: one surface
# for live-character voice no matter which model speaks.
RealtimeProvider = BaseVoiceProvider


def register(cls):
    PROVIDERS[cls.name] = cls()
    return cls


@register
class StubVoiceProvider(BaseVoiceProvider):
    name = "stub"

    def list_models(self) -> list[dict]:
        return [{"id": "stub-echo", "label": "Offline echo (no key)"}]

    def create_session(self, owner: str, tools: list[str] | None = None) -> dict:
        return {"ok": True, "provider": "stub", "model": "stub-echo",
                "session_id": "vs_" + uuid.uuid4().hex[:12],
                "websocket_url": "", "ephemeral_token": "",
                "instructions": SHOPPER_INSTRUCTIONS,
                "tools": tools or VOICE_TOOLS,
                "note": "stub: typed turns only. Set GOOGLE_API_KEY for live voice."}


@register
class GeminiLiveProvider(BaseVoiceProvider):
    name = "gemini_live"

    def is_configured(self) -> bool:
        return bool(config.GOOGLE_API_KEY)

    def list_models(self) -> list[dict]:
        return [{"id": config.GEMINI_VOICE_MODEL, "label": "Live model (env-swappable)",
                 "active": True}]

    def _mint_token(self) -> dict:
        now = datetime.now(timezone.utc)
        body = {
            "uses": 1,
            "expireTime": (now + timedelta(minutes=30)).isoformat().replace("+00:00", "Z"),
            "newSessionExpireTime": (now + timedelta(minutes=1)).isoformat().replace("+00:00", "Z"),
        }
        req = urllib.request.Request(
            "https://generativelanguage.googleapis.com/v1beta/auth_tokens",
            data=json.dumps(body).encode(), method="POST")
        req.add_header("x-goog-api-key", config.GOOGLE_API_KEY)
        req.add_header("Content-Type", "application/json")
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.loads(r.read().decode() or "{}")
        except urllib.error.HTTPError as e:
            raise VoiceError(f"token mint failed ({e.code})") from None
        except urllib.error.URLError as e:
            raise VoiceError(f"Google unreachable: {e.reason}") from None

    def create_session(self, owner: str, tools: list[str] | None = None) -> dict:
        if not self.is_configured():
            raise VoiceError("GOOGLE_API_KEY not set")
        tok = self._mint_token()
        name = tok.get("name") or tok.get("token") or ""
        if not name:
            raise VoiceError(f"empty token response: {json.dumps(tok)[:200]}")
        return {"ok": True, "provider": "gemini_live",
                "model": config.GEMINI_VOICE_MODEL,
                "session_id": "vs_" + uuid.uuid4().hex[:12],
                "websocket_url": WS_URL, "ephemeral_token": name,
                "instructions": SHOPPER_INSTRUCTIONS,
                "tools": tools or VOICE_TOOLS,
                "expires_in": "1 use, 30 min"}


def active_provider() -> BaseVoiceProvider:
    want = (config.GEMINI_VOICE_PROVIDER or "").strip().lower()
    if want in PROVIDERS:
        return PROVIDERS[want]
    if getattr(config, "DASHSCOPE_API_KEY", ""):
        return PROVIDERS.get("qwen_omni", PROVIDERS["stub"])
    if config.GOOGLE_API_KEY:
        return PROVIDERS["gemini_live"]
    return PROVIDERS["stub"]


@register
class QwenOmniRealtimeProvider(BaseVoiceProvider):
    """Live Oddy voice: qwen3.8-omni-flash-realtime. Streaming audio/video
    in, text/audio out, interruptions, tool calls into the same OddHobb MCP
    tools Muse uses, cloned voices. Browser connects direct (WebRTC/WS/AOQ);
    the server mints nothing and proxies no media. Needs DASHSCOPE_API_KEY."""
    name = "qwen_omni"
    MODEL = "qwen3.8-omni-flash-realtime"

    def is_configured(self) -> bool:
        return bool(getattr(config, "DASHSCOPE_API_KEY", ""))

    def list_models(self) -> list[dict]:
        return [{"id": self.MODEL, "label": "Oddy live voice (Singaporestack)",
                 "active": True}]

    def create_session(self, owner: str, tools: list[str] | None = None) -> dict:
        if not self.is_configured():
            raise VoiceError("DASHSCOPE_API_KEY not set")
        return {"ok": True, "provider": "qwen_omni", "model": self.MODEL,
                "session_id": "vs_" + uuid.uuid4().hex[:12],
                "transports": ["webrtc", "websocket", "aoq"],
                "instructions": SHOPPER_INSTRUCTIONS,
                "tools": tools or VOICE_TOOLS,
                "note": "browser connects direct; server holds no audio"}


def ensure_consent_tables(c) -> None:
    c.execute("""CREATE TABLE IF NOT EXISTS voice_consents (
      id TEXT PRIMARY KEY, owner TEXT NOT NULL, subject_id TEXT NOT NULL DEFAULT '',
      audio_sha TEXT NOT NULL DEFAULT '', created_at REAL NOT NULL)""")
    c.execute("""CREATE TABLE IF NOT EXISTS provider_keys (
      owner TEXT NOT NULL, provider TEXT NOT NULL, label TEXT NOT NULL DEFAULT '',
      secret TEXT NOT NULL DEFAULT '', updated_at REAL NOT NULL,
      PRIMARY KEY (owner, provider))""")
    c.commit()
