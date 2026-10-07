"""Uncensored creative writer via OpenRouter (BYO/server key, ask-first).

Default: thedrummer/unslopnemo-12b ($0.40/M — anti-slop tuned, fittingly).
Fallbacks: dolphin-mistral-24b-venice-edition, anthracite-org/magnum-v4-72b.
Every call needs approved=True + lands in data/funny_ledger.jsonl. The model
writes WORDS into our beats; structure, filter and judging stay deterministic.
"""
from __future__ import annotations

import json
import os
import time
import urllib.request
from pathlib import Path

MODELS = ["cognitivecomputations/dolphin-mistral-24b-venice-edition",
          "thedrummer/unslopnemo-12b",
          "anthracite-org/magnum-v4-72b"]

URL = "https://openrouter.ai/api/v1/chat/completions"


class WriterError(Exception):
    pass


def _ledger(entry: dict) -> None:
    from backend import config
    p = Path(config.DATA) / "funny_ledger.jsonl" if hasattr(config, "DATA") else \
        Path("data/funny_ledger.jsonl")
    p.parent.mkdir(parents=True, exist_ok=True)
    entry["ts"] = time.time()
    with p.open("a") as f:
        f.write(json.dumps(entry) + "\n")


def write_set(prompt: str, *, model: str = "", approved: bool = False,
              max_tokens: int = 400) -> dict:
    """Draft joke lines. approved=True required (spend, however tiny)."""
    if not approved:
        raise WriterError("writer needs approved=True — spend, ask first")
    key = (os.environ.get("OPENROUTER_API_KEY") or "").strip()
    if not key:
        raise WriterError("OPENROUTER_API_KEY not set")
    mdl = model or MODELS[0]
    body = json.dumps({"model": mdl,
                       "messages": [{"role": "user", "content": prompt}],
                       "max_tokens": max_tokens}).encode()
    req = urllib.request.Request(URL, data=body, method="POST")
    req.add_header("Authorization", f"Bearer {key}")
    req.add_header("Content-Type", "application/json")
    req.add_header("User-Agent", "OddHobb/1.0 (server-side creative)")
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            d = json.loads(r.read().decode() or "{}")
    except urllib.error.HTTPError as e:
        raise WriterError(f"writer {e.code}: {e.read().decode()[:200]}") from None
    except urllib.error.URLError as e:
        raise WriterError(f"writer unreachable: {e.reason}") from None
    try:
        text = d["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError):
        raise WriterError(f"writer bad shape: {json.dumps(d)[:200]}") from None
    usage = d.get("usage") or {}
    _ledger({"model": d.get("model", mdl), "prompt_chars": len(prompt),
             "out_chars": len(text), "usage": usage, "approved": True})
    lines = [ln.strip(" -•\t") for ln in text.splitlines() if ln.strip()]
    return {"ok": True, "model": d.get("model", mdl), "lines": lines,
            "usage": usage}
