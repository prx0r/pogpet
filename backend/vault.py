"""Provider vault: user BYOC credentials behind server-held encryption.

Agents see capabilities ({free: true, fal: true}), never secrets. Secrets
are Fernet-encrypted with a server-held key (.vault_key, 0600, gitignored,
never leaves the box) and only decrypted in-process at run time.
"""
from __future__ import annotations

import os
import sqlite3
import stat
import time
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
KEYFILE = ROOT / ".vault_key"

PROVIDERS = ("fal", "higgsfield", "alibaba", "openrouter", "replicate",
             "comfyui", "runpod", "custom")


def _key() -> bytes:
    raw = (os.environ.get("ODDHOBB_VAULT_KEY") or "").strip()
    if raw:
        return raw.encode()
    return _file_key()


def _file_key() -> bytes:
    from cryptography.fernet import Fernet
    if KEYFILE.exists():
        return KEYFILE.read_bytes().strip()
    k = Fernet.generate_key()
    KEYFILE.write_bytes(k + b"\n")
    os.chmod(KEYFILE, stat.S_IRUSR | stat.S_IWUSR)
    return k


def _fernet():
    from cryptography.fernet import Fernet
    return Fernet(_key())


def ensure_tables(c: sqlite3.Connection) -> None:
    c.executescript("""
    CREATE TABLE IF NOT EXISTS provider_connections (
      id          TEXT PRIMARY KEY,
      owner       TEXT NOT NULL,
      provider    TEXT NOT NULL,
      encrypted_secret TEXT NOT NULL DEFAULT '',
      metadata_json TEXT NOT NULL DEFAULT '{}',
      created_at  REAL NOT NULL,
      last_used_at REAL NOT NULL DEFAULT 0,
      status      TEXT NOT NULL DEFAULT 'connected'
    );
    CREATE INDEX IF NOT EXISTS idx_vault_owner ON provider_connections(owner);
    """)
    c.commit()


def connect(c: sqlite3.Connection, owner: str, provider: str,
            secret: str, metadata: dict | None = None) -> dict:
    import json
    if provider not in PROVIDERS:
        raise ValueError(f"unknown provider — {', '.join(PROVIDERS)}")
    if not secret.strip():
        raise ValueError("secret is required")
    cid = f"cred_{uuid.uuid4().hex[:8]}"
    token = _fernet().encrypt(secret.strip().encode()).decode()
    c.execute("INSERT INTO provider_connections (id,owner,provider,encrypted_secret,metadata_json,created_at,status)"
              " VALUES (?,?,?,?,?,?,?)",
              (cid, owner, provider, token, json.dumps(metadata or {}),
               time.time(), "connected"))
    c.commit()
    return {"credential_id": cid, "owner": owner, "provider": provider,
            "status": "connected"}


def use(c: sqlite3.Connection, owner: str, provider: str) -> str:
    """Decrypt for a run. Never log, never return to agents."""
    row = c.execute("SELECT * FROM provider_connections WHERE owner=? AND provider=? AND status='connected'"
                    " ORDER BY created_at DESC LIMIT 1", (owner, provider)).fetchone()
    if row is None:
        raise KeyError(f"no connected {provider} for this owner")
    c.execute("UPDATE provider_connections SET last_used_at=? WHERE id=?",
              (time.time(), dict(row)["id"]))
    c.commit()
    return _fernet().decrypt(dict(row)["encrypted_secret"].encode()).decode()


def disconnect(c: sqlite3.Connection, owner: str, provider: str) -> bool:
    cur = c.execute("UPDATE provider_connections SET status='revoked' WHERE owner=? AND provider=?",
                    (owner, provider))
    c.commit()
    return cur.rowcount > 0


def agent_view(c: sqlite3.Connection, owner: str) -> dict:
    """What Muse sees: booleans, never secrets."""
    rows = c.execute("SELECT provider FROM provider_connections WHERE owner=? AND status='connected'",
                     (owner,)).fetchall()
    on = {dict(r)["provider"] for r in rows}
    return {"free": True, **{p: (p in on) for p in
            ("fal", "higgsfield", "alibaba", "openrouter", "replicate", "comfyui", "runpod")}}


def connected(c: sqlite3.Connection, owner: str) -> list[str]:
    rows = c.execute("SELECT provider FROM provider_connections WHERE owner=? AND status='connected'",
                     (owner,)).fetchall()
    return sorted({dict(r)["provider"] for r in rows})


def migrate_plaintext(c: sqlite3.Connection) -> int:
    """One-way migration: plaintext provider_keys → encrypted vault, then the
    old table is dropped. After this exactly one credential store exists."""
    try:
        rows = [dict(r) for r in c.execute("SELECT * FROM provider_keys")]
    except sqlite3.Error:
        return 0
    n = 0
    for r in rows:
        try:
            connect(c, r.get("owner", ""), r.get("provider", ""),
                    r.get("secret", ""), {"label": r.get("label", ""),
                                          "migrated": True})
            n += 1
        except ValueError:
            pass
    c.execute("DROP TABLE IF EXISTS provider_keys")
    c.commit()
    return n
