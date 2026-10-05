"""Voice brain: swappable conversational provider with barge-in.

Gemini Live is the premium path (native interruption, affective dialog,
tool calls mid-sentence, ephemeral browser tokens). But models turn over
fast, so nothing outside this module names one: the active provider and
model come from config (env-overridable), and every caller goes through
active_provider().

    GEMINI_VOICE_PROVIDER=gemini_live|stub   (default: key ? live : stub)
    GEMINI_VOICE_MODEL=<any live-capable id> (default below)
    GOOGLE_API_KEY=<server-side only, never leaves this box>

Without a key the stub serves local echo sessions: the whole shopper flow
stays testable offline, and swapping to the latest best model later is a
one-line env change, not a rewrite. Paid Live calls follow the same
ask-first + ledger discipline as Meshy/Marble (ledger: data/voice_ledger.jsonl).
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
    if config.GOOGLE_API_KEY:
        return PROVIDERS["gemini_live"]
    return PROVIDERS["stub"]
