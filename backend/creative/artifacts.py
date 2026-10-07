"""Artifacts + print contracts + QC gate (cardgen.md §13–15).

First-class output records (never infer from files), supplier-independent
print contracts, machine QC per renderer. Orders reference passed artifacts.

Cache identity is the CONTENT, owner-scoped: canonical scene JSON +
template id/version + subject/asset hashes + renderer version + output
contract + provider params. Two different people never share a key.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
import time
import uuid

PRINT_CONTRACTS = {
    "card_5x7_folded_v1": {
        "id": "card_5x7_folded_v1", "trim_mm": [127, 177.8], "bleed_mm": 3,
        "safe_mm": 5, "dpi": 300, "pages": ["outside", "inside"], "supplier": None,
    },
    "card_a6_flat_v1": {
        "id": "card_a6_flat_v1", "trim_mm": [105, 148], "bleed_mm": 3,
        "safe_mm": 5, "dpi": 300, "pages": ["front", "back"], "supplier": None,
    },
}


def content_key(*, scene: dict, renderer: str, renderer_version: int,
                output_contract: str, provider_params: dict | None = None) -> str:
    """Canonical content hash. Includes template id/version, the full scene
    (copy + subjects + asset ids), renderer version, output contract and
    provider params — NOT revision numbers or project ids."""
    payload = json.dumps({
        "scene": scene,
        "renderer": renderer, "rv": renderer_version,
        "out": output_contract, "prov": provider_params or {},
    }, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode()).hexdigest()[:32]


def ensure_tables(c: sqlite3.Connection) -> None:
    c.executescript("""
    CREATE TABLE IF NOT EXISTS render_artifacts (
      id           TEXT PRIMARY KEY,
      owner        TEXT NOT NULL,
      project_id   TEXT NOT NULL DEFAULT '',
      revision     INTEGER NOT NULL DEFAULT 0,
      renderer     TEXT NOT NULL DEFAULT '',
      output_kind  TEXT NOT NULL DEFAULT '',
      cache_key    TEXT NOT NULL DEFAULT '',
      storage_key  TEXT NOT NULL DEFAULT '',
      mime         TEXT NOT NULL DEFAULT '',
      width        INTEGER NOT NULL DEFAULT 0,
      height       INTEGER NOT NULL DEFAULT 0,
      dpi          INTEGER NOT NULL DEFAULT 0,
      duration     REAL NOT NULL DEFAULT 0,
      status       TEXT NOT NULL DEFAULT 'ready',
      qc_status    TEXT NOT NULL DEFAULT 'pending',
      cost_cents   INTEGER NOT NULL DEFAULT 0,
      provider     TEXT NOT NULL DEFAULT '',
      provider_job TEXT NOT NULL DEFAULT '',
      created_at   REAL NOT NULL
    );
    CREATE INDEX IF NOT EXISTS idx_artifacts_project ON render_artifacts(project_id, revision);
    CREATE INDEX IF NOT EXISTS idx_artifacts_cache ON render_artifacts(cache_key);
    """)
    try:
        c.execute("""DELETE FROM render_artifacts WHERE cache_key <> '' AND id NOT IN (
          SELECT id FROM (SELECT id, ROW_NUMBER() OVER (
            PARTITION BY owner, cache_key ORDER BY created_at DESC) rn
            FROM render_artifacts WHERE cache_key <> '')))""")
    except sqlite3.Error:
        pass
    try:
        c.execute("""CREATE UNIQUE INDEX IF NOT EXISTS idx_artifacts_owner_cache
          ON render_artifacts(owner, cache_key)""")
    except sqlite3.Error:
        pass
    c.commit()


def record(c: sqlite3.Connection, owner: str, project_id: str, revision: int,
           renderer: str, output_kind: str, cache_key: str, storage_key: str,
           *, mime: str = "", width: int = 0, height: int = 0, dpi: int = 0,
           duration: float = 0.0, cost_cents: int = 0, provider: str = "",
           provider_job: str = "") -> dict:
    aid = f"art_{uuid.uuid4().hex[:12]}"
    try:
        c.execute("INSERT INTO render_artifacts (id,owner,project_id,revision,renderer,output_kind,cache_key,storage_key,mime,width,height,dpi,duration,status,qc_status,cost_cents,provider,provider_job,created_at)"
                  " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                  (aid, owner, project_id, revision, renderer, output_kind, cache_key,
                   storage_key, mime, width, height, dpi, duration, "ready", "pending",
                   cost_cents, provider, provider_job, time.time()))
        c.commit()
    except sqlite3.IntegrityError:
        # concurrent render won the race — return the winner's row
        c.rollback()
        hit = by_cache(c, cache_key, owner)
        if hit:
            return hit
        raise
    return {"id": aid, "cache_key": cache_key, "qc_status": "pending"}


def by_cache(c: sqlite3.Connection, cache_key: str, owner: str = "") -> dict:
    """Owner-scoped lookup. No owner = no row: cross-user dedupe is opt-in
    only, never the default."""
    if not cache_key or not owner:
        return {}
    row = c.execute("SELECT * FROM render_artifacts WHERE cache_key=? AND owner=?"
                    " ORDER BY created_at DESC LIMIT 1", (cache_key, owner)).fetchone()
    return dict(row) if row else {}


def qc_card_copy(filled: dict, template: dict) -> list[str]:
    """Machine checks for card copy: overflow, missing fields. Face/DPI/bleed
    checks run against real assets at compose time."""
    gaps = []
    for sid, slot in (template.get("slots") or {}).items():
        if slot.get("type") != "text":
            continue
        v = str(filled.get(sid, slot.get("default", "")))
        mx = int(slot.get("max_chars") or 0)
        if mx and len(v) > mx:
            gaps.append(f"text overflow: {sid} {len(v)} > {mx}")
        if slot.get("required") and not v:
            gaps.append(f"missing required field: {sid}")
    return gaps


def qc_video(duration: float, has_audio: bool, width: int, height: int) -> list[str]:
    gaps = []
    if duration <= 0:
        gaps.append("zero duration")
    if not has_audio:
        gaps.append("no audio")
    if width < 240 or height < 240:
        gaps.append("dimensions too small")
    return gaps


def mark_qc(c: sqlite3.Connection, artifact_id: str, passed: bool) -> None:
    c.execute("UPDATE render_artifacts SET qc_status=? WHERE id=?",
              ("passed" if passed else "failed", artifact_id))
    c.commit()
