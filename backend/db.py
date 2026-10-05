"""SQLite registry — the mesh is the single source of truth.

Upload once, own the character: a Mesh row is referenced by every product
binding rather than copied per product, so re-theming a season re-renders
from the same GLB.
"""
from __future__ import annotations

import hmac
import json
import sqlite3
import time
import uuid
from typing import Any, Iterable

from . import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS photos (
  id          TEXT PRIMARY KEY,
  owner       TEXT NOT NULL DEFAULT '',
  sha256      TEXT NOT NULL,
  r2_key      TEXT NOT NULL,
  mime        TEXT NOT NULL,
  width       INTEGER NOT NULL DEFAULT 0,
  height      INTEGER NOT NULL DEFAULT 0,
  bytes       INTEGER NOT NULL DEFAULT 0,
  orig_name   TEXT NOT NULL DEFAULT '',
  created_at  REAL NOT NULL,
  UNIQUE(sha256, owner)
);

CREATE TABLE IF NOT EXISTS meshes (
  id            TEXT PRIMARY KEY,
  photo_id      TEXT NOT NULL REFERENCES photos(id),
  provider      TEXT NOT NULL DEFAULT 'meshy',
  provider_task TEXT NOT NULL DEFAULT '',
  status        TEXT NOT NULL DEFAULT 'queued',
    -- queued | running | succeeded | failed
  error         TEXT NOT NULL DEFAULT '',
  glb_key       TEXT NOT NULL DEFAULT '',
  thumb_keys    TEXT NOT NULL DEFAULT '[]',
  texture_keys  TEXT NOT NULL DEFAULT '[]',
  bbox          TEXT NOT NULL DEFAULT '{}',
  print_ready   INTEGER NOT NULL DEFAULT 0,
  stub          INTEGER NOT NULL DEFAULT 0,
  created_at    REAL NOT NULL,
  updated_at    REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_meshes_photo ON meshes(photo_id);
CREATE INDEX IF NOT EXISTS idx_meshes_status ON meshes(status);

-- A mesh becoming "active" in a product. This is the fan-out: one row per
-- (mesh, product), all pointing back at the same glb_key.
CREATE TABLE IF NOT EXISTS product_bindings (
  mesh_id     TEXT NOT NULL REFERENCES meshes(id),
  product     TEXT NOT NULL,
  status      TEXT NOT NULL DEFAULT 'active',
    -- active | rendering | ready | failed
  asset_key   TEXT NOT NULL DEFAULT '',
  price_cents INTEGER NOT NULL DEFAULT 0,
  created_at  REAL NOT NULL,
  updated_at  REAL NOT NULL,
  PRIMARY KEY (mesh_id, product)
);

CREATE TABLE IF NOT EXISTS jobs (
  id          TEXT PRIMARY KEY,
  kind        TEXT NOT NULL,
    -- mesh.generate | mesh.poll | product.render
  subject_id  TEXT NOT NULL,
  status      TEXT NOT NULL DEFAULT 'pending',
    -- pending | running | done | failed
  payload     TEXT NOT NULL DEFAULT '{}',
  error       TEXT NOT NULL DEFAULT '',
  attempts    INTEGER NOT NULL DEFAULT 0,
  created_at  REAL NOT NULL,
  updated_at  REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status, kind);

-- Free-tier renders. Every row cost $0 to produce (edge-tts + ffmpeg + our LLM);
-- the watermark flag is what separates free from paid.
CREATE TABLE IF NOT EXISTS videos (
  id          TEXT PRIMARY KEY,
  owner       TEXT NOT NULL,
  mesh_id     TEXT REFERENCES meshes(id),
  scene       TEXT NOT NULL,
  talent      TEXT NOT NULL DEFAULT 'comedy',
  voice       TEXT NOT NULL,
  pet_name    TEXT NOT NULL DEFAULT '',
  topic       TEXT NOT NULL DEFAULT '',
  script      TEXT NOT NULL DEFAULT '',
  lines       TEXT NOT NULL DEFAULT '[]',
  watermarked INTEGER NOT NULL DEFAULT 1,
  duration    REAL NOT NULL DEFAULT 0,
  bytes       INTEGER NOT NULL DEFAULT 0,
  path        TEXT NOT NULL DEFAULT '',
  created_at  REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_videos_owner ON videos(owner, created_at);

-- One row per account: which pog is "active". Every product render, card and
-- video keys off this, so switching it re-themes everything at once.
-- Real accounts. `handle` IS the owner string used everywhere else, so a
-- profile's meshes/photos/videos/videos stay exactly where they are — logging
-- in just stops the identity being a random blob in localStorage.
CREATE TABLE IF NOT EXISTS users (
  id           TEXT PRIMARY KEY,
  handle       TEXT NOT NULL UNIQUE,
  email        TEXT NOT NULL DEFAULT '',
  display_name TEXT NOT NULL DEFAULT '',
  password_hash TEXT NOT NULL DEFAULT '',   -- pbkdf2, salt:hash
  api_key      TEXT NOT NULL UNIQUE,        -- for MCP / agents, shown once
  created_at   REAL NOT NULL,
  last_login   REAL NOT NULL DEFAULT 0
);

-- Delegated agent credential: minted BY a human account, has its own handle
-- and profile, but no wallet. The parent grants a subset of permissions and
-- can revoke it. This is what gets pasted into ChatGPT / Grok / Meta Muse.
CREATE TABLE IF NOT EXISTS agents (
  id             TEXT PRIMARY KEY,
  parent_handle  TEXT NOT NULL,
  agent_handle   TEXT NOT NULL UNIQUE,
  name           TEXT NOT NULL DEFAULT '',
  api_key        TEXT NOT NULL UNIQUE,
  permissions    TEXT NOT NULL DEFAULT '[]',   -- JSON array
  status         TEXT NOT NULL DEFAULT 'active',   -- active | revoked
  created_at     REAL NOT NULL,
  last_used      REAL NOT NULL DEFAULT 0,
  FOREIGN KEY (parent_handle) REFERENCES users(handle)
);
CREATE INDEX IF NOT EXISTS idx_agents_parent ON agents(parent_handle);

CREATE TABLE IF NOT EXISTS profiles (
  owner          TEXT PRIMARY KEY,
  active_mesh_id TEXT DEFAULT '',
  display_name   TEXT DEFAULT '',
  updated_at     REAL NOT NULL
);

-- Friends: profile per subject mesh (name, interests, birthday).
-- Owner-scoped like everything else; a subject without a row is just unnamed.
CREATE TABLE IF NOT EXISTS subject_profiles (
  owner      TEXT NOT NULL,
  mesh_id    TEXT NOT NULL,
  name       TEXT NOT NULL DEFAULT '',
  interests  TEXT NOT NULL DEFAULT '[]',
  birthday   TEXT NOT NULL DEFAULT '',
  updated_at REAL NOT NULL,
  PRIMARY KEY (owner, mesh_id)
);

-- Guided personal-shopper sessions: person first, no search bar. State is
-- a JSON blob (occasion, budget, recipient, photos, mesh, packs, events).
CREATE TABLE IF NOT EXISTS guide_sessions (
  id         TEXT PRIMARY KEY,
  owner      TEXT NOT NULL DEFAULT '',
  stage      TEXT NOT NULL DEFAULT 'ramble',
  state      TEXT NOT NULL DEFAULT '{}',
  created_at REAL NOT NULL,
  updated_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS upload_ledger (
  owner     TEXT NOT NULL,
  day       TEXT NOT NULL,
  count     INTEGER NOT NULL DEFAULT 0,
  PRIMARY KEY (owner, day)
);

-- Free-tier allowance. Separate from upload_ledger because meshes burn real
-- Meshy credits while videos cost us nothing — different budgets, different
-- ceilings. Spend is atomic so two concurrent requests can't both win.
CREATE TABLE IF NOT EXISTS credits (
  owner   TEXT NOT NULL,
  day     TEXT NOT NULL,
  kind    TEXT NOT NULL,          -- mesh | video
  used    INTEGER NOT NULL DEFAULT 0,
  PRIMARY KEY (owner, day, kind)
);

-- Studio one-click orders. Checkout (Stripe/Shopify) lands later; this
-- table is the intent + quote so nothing is lost between click and pay.
CREATE TABLE IF NOT EXISTS orders (
  id          TEXT PRIMARY KEY,
  owner       TEXT NOT NULL DEFAULT '',
  line        TEXT NOT NULL,
  mesh_id     TEXT NOT NULL DEFAULT '',
  coat        TEXT NOT NULL DEFAULT 'none',
  hat         TEXT NOT NULL DEFAULT 'none',
  qty         INTEGER NOT NULL DEFAULT 1,
  price_cents INTEGER NOT NULL DEFAULT 0,
  status      TEXT NOT NULL DEFAULT 'pending_checkout',
  note        TEXT NOT NULL DEFAULT '',
  created_at  REAL NOT NULL
);
"""


def connect() -> sqlite3.Connection:
    config.ensure_dirs()
    c = sqlite3.connect(config.DB_PATH, timeout=30)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA journal_mode=WAL")
    c.execute("PRAGMA foreign_keys=ON")
    return c


def _migrate_photos_unique(c: sqlite3.Connection) -> None:
    """UNIQUE(sha256) -> UNIQUE(sha256, owner).

    Two owners re-uploading the same image must each get their own row (a
    global hash lookup would leak whether someone else's photo is on file),
    while still sharing one R2 object. CREATE TABLE IF NOT EXISTS won't
    touch an existing table, so the old shape has to be rebuilt explicitly.
    """
    row = c.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='photos'"
    ).fetchone()
    if row is None or "UNIQUE(sha256, owner)" in (row["sql"] or ""):
        return

    c.execute("PRAGMA foreign_keys=OFF")
    try:
        c.executescript("""
        CREATE TABLE photos_new (
          id          TEXT PRIMARY KEY,
          owner       TEXT NOT NULL DEFAULT '',
          sha256      TEXT NOT NULL,
          r2_key      TEXT NOT NULL,
          mime        TEXT NOT NULL,
          width       INTEGER NOT NULL DEFAULT 0,
          height      INTEGER NOT NULL DEFAULT 0,
          bytes       INTEGER NOT NULL DEFAULT 0,
          orig_name   TEXT NOT NULL DEFAULT '',
          created_at  REAL NOT NULL,
          UNIQUE(sha256, owner)
        );
        INSERT INTO photos_new (id,owner,sha256,r2_key,mime,width,height,bytes,orig_name,created_at)
          SELECT id,owner,sha256,r2_key,mime,width,height,bytes,orig_name,created_at FROM photos;
        DROP TABLE photos;
        ALTER TABLE photos_new RENAME TO photos;
        """)
    finally:
        c.execute("PRAGMA foreign_keys=ON")


def _migrate_videos_talent(c: sqlite3.Connection) -> None:
    """videos.talent — added when the Perform tab landed. Guarded because
    ADD COLUMN errors if the column already exists."""
    try:
        cols = [r[1] for r in c.execute("PRAGMA table_info(videos)").fetchall()]
    except sqlite3.Error:
        return
    if cols and "talent" not in cols:
        c.execute("ALTER TABLE videos ADD COLUMN talent TEXT NOT NULL DEFAULT 'comedy'")


def init() -> None:
    with connect() as c:
        c.executescript(SCHEMA)
        _migrate_photos_unique(c)
        _migrate_photos_source(c)
        _migrate_videos_talent(c)
        _migrate_photos_person(c)
        _migrate_users_email_unique(c)


def _migrate_users_email_unique(c: sqlite3.Connection) -> None:
    """One account per email — Google sign-in keys on email; dupes fork identities."""
    c.execute(
        """CREATE UNIQUE INDEX IF NOT EXISTS idx_users_email_unique
           ON users(lower(email)) WHERE email <> ''"""
    )


def _migrate_photos_source(c: sqlite3.Connection) -> None:
    """photos.source — photo|screenshot|upload. Screenshots (Dot/Muse grabs)
    route to the companion multi-view path; plain photos keep the pet path."""
    cols = [r[1] for r in c.execute("PRAGMA table_info(photos)")]
    if "source" not in cols:
        c.execute("ALTER TABLE photos ADD COLUMN source TEXT NOT NULL DEFAULT 'photo'")


def _migrate_photos_person(c: sqlite3.Connection) -> None:
    """photos.person — which person/pet this upload belongs to (autosort label).

    NULL = not grouped yet. Renaming a label renames the whole group
    (POST /api/people/rename), which is the "who's this?" -> save flow.
    """
    cols = [r[1] for r in c.execute("PRAGMA table_info(photos)")]
    if "person" not in cols:
        c.execute("ALTER TABLE photos ADD COLUMN person TEXT")


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:20]}"


def create_order(c: sqlite3.Connection, *, owner: str, line: str, mesh_id: str,
                 coat: str, hat: str, qty: int, price_cents: int,
                 note: str = "") -> dict:
    oid = new_id("ord")
    c.execute(
        """INSERT INTO orders (id,owner,line,mesh_id,coat,hat,qty,price_cents,status,note,created_at)
           VALUES (?,?,?,?,?,?,?,?, 'pending_checkout', ?, ?)""",
        (oid, owner, line, mesh_id, coat, hat, max(1, int(qty)), int(price_cents),
         note[:200], now()),
    )
    c.commit()
    row = c.execute("SELECT * FROM orders WHERE id=?", (oid,)).fetchone()
    return dict(row) if row else {}


def get_order(c: sqlite3.Connection, oid: str) -> dict | None:
    row = c.execute("SELECT * FROM orders WHERE id=?", (oid,)).fetchone()
    return dict(row) if row else None


def orders_for(c: sqlite3.Connection, owner: str, limit: int = 20) -> list[dict]:
    rows = c.execute(
        "SELECT * FROM orders WHERE owner=? ORDER BY created_at DESC LIMIT ?",
        (owner, max(1, min(limit, 100))),
    ).fetchall()
    return [dict(r) for r in rows]


def now() -> float:
    return time.time()


def hash_password(pw: str, salt: str | None = None) -> str:
    """pbkdf2-sha256, 200k rounds, stored as salt$hash. Stdlib only."""
    import hashlib
    import secrets
    s = salt or secrets.token_hex(16)
    h = hashlib.pbkdf2_hmac("sha256", pw.encode(), s.encode(), 200_000).hex()
    return f"{s}${h}"


def verify_password(pw: str, stored: str) -> bool:
    if not stored or "$" not in stored:
        return False
    s, _ = stored.split("$", 1)
    return hmac.compare_digest(hash_password(pw, s), stored)


def create_user(c: sqlite3.Connection, handle: str, password: str = "",
                email: str = "", display_name: str = "") -> dict:
    """handle becomes the owner string for every asset they ever make."""
    import secrets
    import string
    h = _clean_handle(handle)
    if len(h) < 3:
        raise ValueError("handle needs at least 3 characters")
    if get_user_by_handle(c, h):
        raise ValueError(f"handle @{h} is taken")
    alphabet = string.ascii_letters + string.digits
    key = "figg_" + "".join(secrets.choice(alphabet) for _ in range(40))
    uid = new_id("usr")
    email_clean = email.strip()[:120]
    if email_clean:
        clash = c.execute(
            "SELECT handle FROM users WHERE lower(email)=lower(?) AND email<>''",
            (email_clean,)).fetchone()
        if clash:
            raise ValueError(f"email already registered to @{clash['handle']}")
    try:
        c.execute(
            "INSERT INTO users (id,handle,email,display_name,password_hash,api_key,created_at)"
            " VALUES (?,?,?,?,?,?,?)",
            (uid, h, email_clean, display_name.strip()[:80],
             hash_password(password) if password else "", key, now()),
        )
    except sqlite3.IntegrityError as e:
        if "email" in str(e).lower():
            raise ValueError("email already registered") from None
        raise
    # adopt an existing anonymous profile if they had one
    if not get_profile(c, h).get("active_mesh_id"):
        set_active(c, h, "")
    return get_user_by_handle(c, h)


def _clean_handle(handle: str) -> str:
    import re
    s = re.sub(r"[^A-Za-z0-9._-]", "", (handle or "").strip()).strip("._-")
    return s[:32]


def get_user_by_handle(c: sqlite3.Connection, handle: str) -> dict | None:
    row = c.execute("SELECT * FROM users WHERE handle=?",
                    (_clean_handle(handle),)).fetchone()
    return dict(row) if row else None


def get_user_by_api_key(c: sqlite3.Connection, key: str) -> dict | None:
    if not key:
        return None
    row = c.execute("SELECT * FROM users WHERE api_key=?", (key,)).fetchone()
    return dict(row) if row else None


def claim_assets(c: sqlite3.Connection, from_owner: str, to_handle: str) -> dict:
    """Move an anonymous owner's assets onto a real account.

    Photos and videos are row-rewritten (storage keys are derived from the
    owner, so the R2 objects get re-pointed too — see storage.claim_owner).
    """
    out = {}
    cur = c.execute("UPDATE photos SET owner=? WHERE owner=? AND owner<>?",
                    (to_handle, from_owner, to_handle))
    out["photos"] = cur.rowcount
    cur = c.execute("UPDATE videos SET owner=? WHERE owner=? AND owner<>?",
                    (to_handle, from_owner, to_handle))
    out["videos"] = cur.rowcount
    # Keep immutable artifact keys/namespace and revision specifications intact.
    tables={r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    for table in ("card_designs","card_jobs","card_cutouts","card_orders"):
        if table in tables:
            cur=c.execute(f"UPDATE {table} SET owner=? WHERE owner=? AND owner<>?",(to_handle,from_owner,to_handle))
            out[table]=cur.rowcount
    # Guided sessions and friend profiles move with the shopper — otherwise
    # claiming an account 404s the session they were just using.
    for table in ("guide_sessions","subject_profiles"):
        if table in tables:
            cur=c.execute(f"UPDATE {table} SET owner=? WHERE owner=? AND owner<>?",(to_handle,from_owner,to_handle))
            out[table]=cur.rowcount
    return out


def create_agent(c: sqlite3.Connection, parent: str, name: str,
                 permissions: Iterable[str]) -> dict:
    import secrets
    import string
    alphabet = string.ascii_letters + string.digits
    key = "fagg_" + "".join(secrets.choice(alphabet) for _ in range(40))  # agent key prefix
    base = _clean_handle(name) or "agent"
    handle, n = base, 1
    while get_user_by_handle(c, handle) or c.execute(
            "SELECT 1 FROM agents WHERE agent_handle=?", (handle,)).fetchone():
        n += 1
        handle = f"{base}{n}"[:32]
    allowed = [p for p in permissions if p in config.AGENT_PERMISSIONS]
    aid = new_id("agt")
    c.execute(
        "INSERT INTO agents (id,parent_handle,agent_handle,name,api_key,permissions,created_at)"
        " VALUES (?,?,?,?,?,?,?)",
        (aid, _clean_handle(parent), handle, name.strip()[:60] or handle,
         key, json.dumps(allowed), now()),
    )
    return get_agent(c, aid)


def get_agent(c: sqlite3.Connection, aid: str) -> dict | None:
    row = c.execute("SELECT * FROM agents WHERE id=?", (aid,)).fetchone()
    return dict(row) if row else None


def get_agent_by_key(c: sqlite3.Connection, key: str) -> dict | None:
    if not key:
        return None
    row = c.execute("SELECT * FROM agents WHERE api_key=?", (key,)).fetchone()
    return dict(row) if row else None


def list_agents(c: sqlite3.Connection, parent: str) -> list[dict]:
    rows = c.execute("SELECT * FROM agents WHERE parent_handle=? ORDER BY created_at DESC",
                     (_clean_handle(parent),)).fetchall()
    return [dict(r) for r in rows]


def agent_perms(agent: dict) -> list[str]:
    try:
        return list(json.loads(agent.get("permissions") or "[]"))
    except Exception:
        return []


def set_agent_permissions(c: sqlite3.Connection, aid: str,
                          permissions: Iterable[str]) -> None:
    allowed = [p for p in permissions if p in config.AGENT_PERMISSIONS]
    c.execute("UPDATE agents SET permissions=? WHERE id=?",
              (json.dumps(allowed), aid))


def set_agent_status(c: sqlite3.Connection, aid: str, status: str) -> None:
    c.execute("UPDATE agents SET status=? WHERE id=?", (status, aid))


def touch_agent(c: sqlite3.Connection, aid: str) -> None:
    c.execute("UPDATE agents SET last_used=? WHERE id=?", (now(), aid))


def get_profile(c: sqlite3.Connection, owner: str) -> dict:
    row = c.execute("SELECT * FROM profiles WHERE owner=?", (owner,)).fetchone()
    if row:
        return dict(row)
    return {"owner": owner, "active_mesh_id": "", "display_name": "", "updated_at": 0.0}


def set_active(c: sqlite3.Connection, owner: str, mesh_id: str) -> None:
    c.execute(
        "INSERT INTO profiles (owner,active_mesh_id,updated_at) VALUES (?,?,?)"
        " ON CONFLICT(owner) DO UPDATE SET active_mesh_id=excluded.active_mesh_id,"
        " updated_at=excluded.updated_at",
        (owner, mesh_id, now()),
    )


def get_subject_profile(c: sqlite3.Connection, owner: str, mesh_id: str) -> dict:
    """Friend profile for one subject mesh — {} when unnamed."""
    row = c.execute(
        "SELECT * FROM subject_profiles WHERE owner=? AND mesh_id=?",
        (owner, mesh_id)).fetchone()
    if not row:
        return {}
    d = dict(row)
    try:
        d["interests"] = json.loads(d.get("interests") or "[]")
    except (ValueError, TypeError):
        d["interests"] = []
    return d


def set_subject_profile(c: sqlite3.Connection, owner: str, mesh_id: str,
                        name: str = "", interests: list | None = None,
                        birthday: str = "") -> dict:
    """Upsert a friend profile. Interests are free tags; known ones map to
    motifs via config.INTEREST_MOTIFS, unknown ones ride along untouched."""
    cur = get_subject_profile(c, owner, mesh_id)
    keep = cur.get("interests", []) if interests is None else [str(i)[:40] for i in interests][:12]
    row = {
        "owner": owner, "mesh_id": mesh_id,
        "name": (name or cur.get("name", ""))[:60],
        "interests": json.dumps(keep),
        "birthday": (birthday if birthday != "" else cur.get("birthday", ""))[:10],
        "updated_at": now(),
    }
    c.execute(
        "INSERT INTO subject_profiles (owner,mesh_id,name,interests,birthday,updated_at)"
        " VALUES (?,?,?,?,?,?) ON CONFLICT(owner,mesh_id) DO UPDATE SET"
        " name=excluded.name, interests=excluded.interests,"
        " birthday=excluded.birthday, updated_at=excluded.updated_at",
        (row["owner"], row["mesh_id"], row["name"], row["interests"],
         row["birthday"], row["updated_at"]),
    )
    return get_subject_profile(c, owner, mesh_id)


def pogs_for(c: sqlite3.Connection, owner: str) -> list[dict]:
    """Every mesh this owner owns — the spotlight roster."""
    rows = c.execute(
        "SELECT m.*, p.r2_key AS photo_key FROM meshes m"
        " JOIN photos p ON p.id=m.photo_id WHERE p.owner=?"
        " ORDER BY CASE m.status WHEN 'succeeded' THEN 0 ELSE 1 END,"
        " m.created_at DESC",
        (owner,),
    ).fetchall()
    return [dict(r) for r in rows]


PHOTO_SOURCES = ("photo", "screenshot", "upload")


def insert_photo(c: sqlite3.Connection, **kw: Any) -> str:
    pid = new_id("pho")
    src = str(kw.get("source") or "photo")
    if src not in PHOTO_SOURCES:
        src = "photo"
    try:
        c.execute(
            "INSERT INTO photos (id,owner,sha256,r2_key,mime,width,height,bytes,orig_name,created_at,source)"
            " VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (pid, kw["owner"], kw["sha256"], kw["r2_key"], kw["mime"],
             kw["width"], kw["height"], kw["bytes"], kw["orig_name"], now(), src),
        )
    except sqlite3.Error:
        # pre-migration table without the source column
        c.execute(
            "INSERT INTO photos (id,owner,sha256,r2_key,mime,width,height,bytes,orig_name,created_at)"
            " VALUES (?,?,?,?,?,?,?,?,?,?)",
            (pid, kw["owner"], kw["sha256"], kw["r2_key"], kw["mime"],
             kw["width"], kw["height"], kw["bytes"], kw["orig_name"], now()),
        )
    return pid


def find_photo_by_hash(c: sqlite3.Connection, sha256: str, owner: str) -> sqlite3.Row | None:
    """Scoped to owner: a global lookup would let anyone probe whether a
    known image is already on file. Storage stays shared because the R2 key
    is derived from the hash alone."""
    return c.execute(
        "SELECT * FROM photos WHERE sha256=? AND owner=?", (sha256, owner)
    ).fetchone()


def get_photo(c: sqlite3.Connection, pid: str) -> sqlite3.Row | None:
    return c.execute("SELECT * FROM photos WHERE id=?", (pid,)).fetchone()


def create_mesh(c: sqlite3.Connection, photo_id: str, provider: str = "meshy") -> str:
    mid = new_id("msh")
    ts = now()
    c.execute(
        "INSERT INTO meshes (id,photo_id,provider,status,created_at,updated_at)"
        " VALUES (?,?,?,'queued',?,?)",
        (mid, photo_id, provider, ts, ts),
    )
    return mid


def get_mesh(c: sqlite3.Connection, mid: str) -> sqlite3.Row | None:
    return c.execute("SELECT * FROM meshes WHERE id=?", (mid,)).fetchone()


def update_mesh(c: sqlite3.Connection, mid: str, **kw: Any) -> None:
    if not kw:
        return
    kw["updated_at"] = now()
    cols = ", ".join(f"{k}=?" for k in kw)
    c.execute(f"UPDATE meshes SET {cols} WHERE id=?", (*kw.values(), mid))


def bind_products(c: sqlite3.Connection, mid: str, products: Iterable[str]) -> list[str]:
    """Activate a mesh across products. Idempotent — re-binding keeps the row."""
    ts = now()
    created = []
    for name in products:
        spec = config.PRODUCTS.get(name)
        if spec is None:
            continue
        try:
            c.execute(
                "INSERT INTO product_bindings (mesh_id,product,status,price_cents,created_at,updated_at)"
                " VALUES (?,?, 'active', ?,?,?)",
                (mid, name, spec["price_cents"], ts, ts),
            )
            created.append(name)
        except sqlite3.IntegrityError:
            pass
    return created


def products_for(c: sqlite3.Connection, mid: str) -> list[dict]:
    rows = c.execute(
        "SELECT b.*, m.glb_key, m.status AS mesh_status FROM product_bindings b"
        " JOIN meshes m ON m.id=b.mesh_id WHERE b.mesh_id=? ORDER BY b.product",
        (mid,),
    ).fetchall()
    return [dict(r) for r in rows]


def count_uploads_today(c: sqlite3.Connection, owner: str, day: str) -> int:
    row = c.execute(
        "SELECT count FROM upload_ledger WHERE owner=? AND day=?", (owner, day)
    ).fetchone()
    return int(row["count"]) if row else 0


def bump_uploads(c: sqlite3.Connection, owner: str, day: str) -> None:
    c.execute(
        "INSERT INTO upload_ledger (owner,day,count) VALUES (?,?,1)"
        " ON CONFLICT(owner,day) DO UPDATE SET count=count+1",
        (owner, day),
    )


def credit_used(c: sqlite3.Connection, owner: str, day: str, kind: str) -> int:
    row = c.execute(
        "SELECT used FROM credits WHERE owner=? AND day=? AND kind=?",
        (owner, day, kind),
    ).fetchone()
    return int(row["used"]) if row else 0


def refund_credit(c: sqlite3.Connection, owner: str, day: str, kind: str) -> None:
    """Give one back when a render fails for our reasons, not theirs."""
    c.execute(
        "UPDATE credits SET used = CASE WHEN used > 0 THEN used - 1 ELSE 0 END"
        " WHERE owner=? AND day=? AND kind=?",
        (owner, day, kind),
    )


def spend_credit(c: sqlite3.Connection, owner: str, day: str, kind: str,
                 limit: int) -> tuple[bool, int]:
    """Atomically take one unit. Returns (ok, used_after).

    The WHERE clause on `used < limit` is what makes it safe: if two requests
    race for the last credit, exactly one increments.
    """
    day_used = credit_used(c, owner, day, kind)
    if day_used >= limit:
        return False, day_used
    c.execute(
        "INSERT INTO credits (owner,day,kind,used) VALUES (?,?,?,1)"
        " ON CONFLICT(owner,day,kind) DO UPDATE SET used=used+1"
        " WHERE used < ?",
        (owner, day, kind, limit),
    )
    after = credit_used(c, owner, day, kind)
    return (after <= limit and after > day_used), after


def credit_status(c: sqlite3.Connection, owner: str, day: str) -> dict:
    return {
        k: {"used": credit_used(c, owner, day, k), "limit": limit,
            "remaining": max(0, limit - credit_used(c, owner, day, k))}
        for k, limit in config.FREE_DAILY.items()
    }


def enqueue(c: sqlite3.Connection, kind: str, subject_id: str, payload: dict | None = None) -> str:
    jid = new_id("job")
    ts = now()
    c.execute(
        "INSERT INTO jobs (id,kind,subject_id,status,payload,created_at,updated_at)"
        " VALUES (?,?,?,'pending',?,?,?)",
        (jid, kind, subject_id, json.dumps(payload or {}), ts, ts),
    )
    return jid


def claim_job(c: sqlite3.Connection, kind: str) -> sqlite3.Row | None:
    """Atomically take the oldest pending job of a kind."""
    row = c.execute(
        "SELECT * FROM jobs WHERE kind=? AND status='pending' ORDER BY created_at LIMIT 1",
        (kind,),
    ).fetchone()
    if not row:
        return None
    cur = c.execute(
        "UPDATE jobs SET status='running', attempts=attempts+1, updated_at=?"
        " WHERE id=? AND status='pending'",
        (now(), row["id"]),
    )
    if cur.rowcount != 1:
        return None
    return row


def finish_job(c: sqlite3.Connection, jid: str, status: str, error: str = "") -> None:
    c.execute(
        "UPDATE jobs SET status=?, error=?, updated_at=? WHERE id=?",
        (status, error, now(), jid),
    )


def dump(row: sqlite3.Row | None) -> dict | None:
    if row is None:
        return None
    d = dict(row)
    for k in ("thumb_keys", "texture_keys", "payload"):
        if k in d and isinstance(d[k], str):
            try:
                d[k] = json.loads(d[k])
            except Exception:
                pass
    return d
