"""Marble (World Labs) client + spend ledger.

Rooms are infrastructure: one $1.20 generation amortized over every
performance ever filmed there. Same money rules as Meshy:

1. ASK the user before every paid call (generate/export). Balance checks
   and polls are free, but even those wait for session approval.
2. Key lives ONLY in the environment (`MARBLE_API_KEY`, empty = stub).
   Never in docs, tests, logs, or history. Never printed.
3. Every credit spend appends to data/marble_credits.jsonl (gitignored)
   and the delta is reported afterwards.

Without a key every paid method raises MarbleAuthError and the rooms
system runs on local backdrops (data/rooms/*.png) for $0.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from . import config

BASE = "https://api.worldlabs.ai"
LEDGER = config.ROOT / "data" / "marble_credits.jsonl"


class MarbleError(Exception):
    pass


class MarbleAuthError(MarbleError):
    pass


def is_configured() -> bool:
    return bool(config.MARBLE_API_KEY)


def _req(method: str, path: str, body: dict | None = None, timeout: int = 60) -> dict:
    if not config.MARBLE_API_KEY:
        raise MarbleAuthError("MARBLE_API_KEY not set")
    url = f"{BASE}{path}"
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("WLT-Api-Key", config.MARBLE_API_KEY)
    if data:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode() or "{}")
    except urllib.error.HTTPError as e:
        payload = e.read().decode("utf-8", "replace")[:400]
        if e.code in (401, 403):
            raise MarbleAuthError(f"Marble rejected the key ({e.code})") from None
        raise MarbleError(f"Marble {e.code}: {payload}") from None
    except urllib.error.URLError as e:
        raise MarbleError(f"Marble unreachable: {e.reason}") from None


def balance() -> int | None:
    """Free endpoint. None on failure (never guess a balance)."""
    try:
        return int(_req("GET", "/marble/v1/credits").get("credits", 0) or 0)
    except Exception:  # noqa: BLE001
        return None


def generate_room(*, prompt: str, model: str = "marble-1.1",
                  display_name: str = "") -> str:
    """Start a room generation. Returns operation_id. Ask first (~$1.26)."""
    res = _req("POST", "/marble/v1/worlds:generate", {
        "display_name": display_name or prompt[:60],
        "model": model,
        "world_prompt": {"type": "text", "text_prompt": prompt},
    })
    op = res.get("operation_id") or ""
    if not op:
        raise MarbleError(f"no operation id: {json.dumps(res)[:300]}")
    return str(op)


def get_operation(operation_id: str) -> dict:
    return _req("GET", f"/marble/v1/operations/{operation_id}")


def export_world(world_id: str, *, asset: str = "splats") -> str:
    """Splat PLY export is free; mesh GLB costs 3,500cr. Returns operation_id."""
    kind = "ply" if asset == "splats" else "glb"
    res = _req("POST", f"/marble/v1/worlds/{world_id}:export",
               {"asset_type": asset, "format": kind})
    return str(res.get("operation_id") or "")


def log_spend(stage: str, ref: str, credits: int, source: str) -> None:
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    rec = {
        "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "stage": stage, "ref": ref, "credits": credits,
        "source": source, "asked": True, "balance_after": balance(),
    }
    with LEDGER.open("a") as f:
        f.write(json.dumps(rec) + "\n")
