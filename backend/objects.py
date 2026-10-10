"""Agent-addressable object records (rooms, podiums, figures).

The bridge between digital agents and physical things: one record links
appearance (GLB), physical design (revision + recipe), behaviour
(capabilities + event state) and place (compatible worlds). AR glasses
commoditize display — identity + event protocol is the durable layer.
A QR/NFC tag on the object points at the resolve endpoint; phones today,
glasses tomorrow, same record.

Docs: docs/canonical-vision.md §5 (agent contract), the physical-world
strategy (event table), docs/vendor/marble-atlas.md (splat→mesh source).
Actuation-adjacent: state changes are owner-enforced; resolve is public
(no PII — display names only with consent... names omitted by default).
"""
from __future__ import annotations

import json
import time

SCHEMA = """
CREATE TABLE IF NOT EXISTS objects (
 object_id TEXT PRIMARY KEY,
 owner TEXT NOT NULL DEFAULT '',
 kind TEXT NOT NULL DEFAULT 'room',
 digital_asset TEXT NOT NULL DEFAULT '',
 physical_revision TEXT NOT NULL DEFAULT 'v1.0',
 recipe_id TEXT NOT NULL DEFAULT '',
 capabilities TEXT NOT NULL DEFAULT '[]',
 compatible_worlds TEXT NOT NULL DEFAULT '[]',
 manufacturing_status TEXT NOT NULL DEFAULT 'unvalidated',
 state TEXT NOT NULL DEFAULT '{}',
 created_at REAL NOT NULL, updated_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS objects_owner ON objects(owner);
"""

# Agent event → response hints (lights/display/AR overlay read these).
EVENTS = ("working", "needs_approval", "finished_artwork", "visitor",
          "offline", "new_message", "idle")

STATUSES = ("unvalidated", "validated", "in_production", "shipped",
            "installed")


def ensure_schema() -> None:
    from backend import db as _db
    with _db.connect() as c:
        c.executescript(SCHEMA)


def _new_id() -> str:
    import uuid
    return f"oddhobb-{uuid.uuid4().hex[:6]}"


def register(owner: str, kind: str = "room", digital_asset: str = "",
             recipe_id: str = "", capabilities: list | None = None,
             compatible_worlds: list | None = None) -> dict:
    from backend import db as _db
    ensure_schema()
    oid = _new_id()
    now = time.time()
    with _db.connect() as c:
        c.execute(
            "INSERT INTO objects (object_id,owner,kind,digital_asset,"
            "physical_revision,recipe_id,capabilities,compatible_worlds,"
            "manufacturing_status,state,created_at,updated_at)"
            " VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            (oid, owner, (kind or "room")[:40], (digital_asset or "")[:500],
             "v1.0", (recipe_id or "")[:80],
             json.dumps([str(x)[:40] for x in (capabilities or [])]),
             json.dumps([str(x)[:80] for x in (compatible_worlds or [])]),
             "unvalidated", "{}", now, now))
    return get(oid) or {"object_id": oid}


def get(object_id: str) -> dict | None:
    from backend import db as _db
    ensure_schema()
    with _db.connect() as c:
        r = c.execute("SELECT * FROM objects WHERE object_id=?",
                      (object_id,)).fetchone()
    if not r:
        return None
    d = dict(r)
    for k in ("capabilities", "compatible_worlds", "state"):
        try:
            d[k] = json.loads(d.get(k) or ("{}" if k == "state" else "[]"))
        except (ValueError, TypeError):
            d[k] = {} if k == "state" else []
    return d


def set_state(owner: str, object_id: str, event: str,
              detail: dict | None = None) -> dict:
    """Record an agent event on an owned object. Event must be known;
    owner must match. Returns the record or an error dict."""
    if event not in EVENTS:
        return {"ok": False, "error": f"unknown event (known: {EVENTS})"}
    from backend import db as _db
    ensure_schema()
    with _db.connect() as c:
        r = c.execute("SELECT * FROM objects WHERE object_id=? AND owner=?",
                      (object_id, owner)).fetchone()
        if not r:
            return {"ok": False, "error": "object not found"}
        state = {"event": event, "detail": detail or {},
                 "at": time.time()}
        c.execute("UPDATE objects SET state=?, updated_at=? WHERE object_id=?",
                  (json.dumps(state), time.time(), object_id))
    rec = get(object_id) or {}
    rec["ok"] = True
    return rec


def set_status(owner: str, object_id: str, status: str) -> dict:
    if status not in STATUSES:
        return {"ok": False, "error": f"unknown status (known: {STATUSES})"}
    from backend import db as _db
    ensure_schema()
    with _db.connect() as c:
        c.execute("UPDATE objects SET manufacturing_status=?,"
                  "updated_at=? WHERE object_id=? AND owner=?",
                  (status, time.time(), object_id, owner))
        hit = c.total_changes
    if not hit:
        return {"ok": False, "error": "object not found"}
    rec = get(object_id) or {}
    rec["ok"] = True
    return rec
