"""Jev client — typed decisions via OpenRouter (TypeSafe System One).

Jev does NOT chat: you send application state + typed questions (noul /
choice / score) and get calibrated answers back. Model pinned to
typesafe/jev-1.13 (never the rolling alias — thresholds must stay put).
$0.042/1M input, output free. Key server-side only, ask-first + ledger
like every other spend. Docs: https://openrouter.ai/docs/guides/community/jev
"""
from __future__ import annotations

import json
import os
import urllib.request

MODEL = "typesafe/jev-1.13"
DECISIONS_URL = "https://openrouter.ai/api/alpha/decisions"


class JevError(Exception):
    pass


def _key() -> str:
    k = (os.environ.get("OPENROUTER_API_KEY") or "").strip()
    if not k:
        raise JevError("OPENROUTER_API_KEY not set")
    return k


def decide(state: dict | str | list, questions: dict,
           *, model: str = MODEL, timeout: int = 60) -> dict:
    """One decision call. Returns the raw answers map + usage/cost."""
    body = json.dumps({"model": model, "state": state, "questions": questions}).encode()
    req = urllib.request.Request(DECISIONS_URL, data=body, method="POST")
    req.add_header("Authorization", f"Bearer {_key()}")
    req.add_header("Content-Type", "application/json")
    req.add_header("User-Agent", "OddHobb/1.0 (server-side decisions)")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode() or "{}")
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")[:300]
        raise JevError(f"Jev {e.code}: {detail}") from None
    except urllib.error.URLError as e:
        raise JevError(f"Jev unreachable: {e.reason}") from None


def ask(state: dict | str | list, questions: dict) -> dict:
    """Thin wrapper returning just answers (or raising JevError)."""
    d = decide(state, questions)
    if "answers" not in d:
        raise JevError(f"no answers in response: {json.dumps(d)[:300]}")
    return d["answers"]
