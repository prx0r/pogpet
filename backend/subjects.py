"""Canonical person graph (cardgen.md §1–2).

Dad is not a mesh. Identity lives in studio_subjects; assets hang off it
via photo_subjects / mesh_subjects; rich facts live in
subject_profiles_v2 keyed by (owner, subject_id). The old mesh-keyed
subject_profiles stays as a compat source and migrates forward on read.

Assets registry (§2): every raw upload and every derivation gets one row.
Existing photos/meshes keep operating; this table is the index above them.
Detection proposes, customers confirm — confirmed links only for renders.
"""
from __future__ import annotations

import json
import sqlite3
import time


def ensure_tables(c: sqlite3.Connection) -> None:
    """Only the tables WE own. studio_subjects / photo_subjects /
    mesh_subjects belong to studio_library (richer schema: face_id,
    provenance) — never create shadow versions here."""
    c.executescript("""
    CREATE TABLE IF NOT EXISTS subject_profiles_v2 (
      owner        TEXT NOT NULL,
      subject_id   TEXT NOT NULL,
      relationship TEXT NOT NULL DEFAULT '',
      birthday     TEXT NOT NULL DEFAULT '',
      profile_json TEXT NOT NULL DEFAULT '{}',
      updated_at   REAL NOT NULL,
      PRIMARY KEY (owner, subject_id)
    );
    CREATE TABLE IF NOT EXISTS assets (
      id          TEXT PRIMARY KEY,
      owner       TEXT NOT NULL,
      kind        TEXT NOT NULL,
      sha256      TEXT NOT NULL DEFAULT '',
      storage_key TEXT NOT NULL DEFAULT '',
      parent_id   TEXT NOT NULL DEFAULT '',
      metadata    TEXT NOT NULL DEFAULT '{}',
      provenance  TEXT NOT NULL DEFAULT '',
      created_at  REAL NOT NULL
    );
    CREATE INDEX IF NOT EXISTS idx_assets_owner ON assets(owner);
    CREATE INDEX IF NOT EXISTS idx_assets_parent ON assets(parent_id);
    CREATE TABLE IF NOT EXISTS families (
      id         TEXT PRIMARY KEY,
      owner      TEXT NOT NULL,
      name       TEXT NOT NULL DEFAULT '',
      created_at REAL NOT NULL
    );
    CREATE TABLE IF NOT EXISTS family_members (
      family_id  TEXT NOT NULL REFERENCES families(id),
      subject_id TEXT NOT NULL REFERENCES studio_subjects(id),
      role       TEXT NOT NULL DEFAULT '',
      PRIMARY KEY (family_id, subject_id)
    );
    """)
    c.commit()


def _now() -> float:
    return time.time()


def _new_id(c: sqlite3.Connection, prefix: str) -> str:
    import uuid
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


# ── subjects ──────────────────────────────────────────────────────────

def get_subject(c: sqlite3.Connection, owner: str, subject_id: str) -> dict:
    row = c.execute("SELECT * FROM studio_subjects WHERE owner=? AND id=?",
                    (owner, subject_id)).fetchone()
    return dict(row) if row else {}


def subjects_for(c: sqlite3.Connection, owner: str) -> list[dict]:
    return [dict(r) for r in c.execute(
        "SELECT * FROM studio_subjects WHERE owner=? ORDER BY created_at", (owner,))]


def find_subject_by_name(c: sqlite3.Connection, owner: str, name: str) -> dict:
    row = c.execute("SELECT * FROM studio_subjects WHERE owner=? AND lower(name)=lower(?)",
                    (owner, name)).fetchone()
    return dict(row) if row else {}


def create_subject(c: sqlite3.Connection, owner: str, name: str,
                   kind: str = "person") -> dict:
    sid = _new_id(c, "sub")
    c.execute("INSERT INTO studio_subjects (id,owner,name,kind,created_at)"
              " VALUES (?,?,?,?,?)", (sid, owner, name[:80], kind, _now()))
    c.commit()
    return get_subject(c, owner, sid)


def profile_for(c: sqlite3.Connection, owner: str, subject_id: str) -> dict:
    row = c.execute("SELECT * FROM subject_profiles_v2 WHERE owner=? AND subject_id=?",
                    (owner, subject_id)).fetchone()
    if not row:
        return {}
    d = dict(row)
    try:
        d["profile"] = json.loads(d.get("profile_json") or "{}")
    except (ValueError, TypeError):
        d["profile"] = {}
    return d


def set_profile(c: sqlite3.Connection, owner: str, subject_id: str, *,
                relationship: str = "", birthday: str = "",
                profile: dict | None = None) -> dict:
    cur = profile_for(c, owner, subject_id).get("profile", {})
    merged = {**cur, **(profile or {})}
    if relationship:
        merged["relationship"] = relationship
    c.execute("INSERT INTO subject_profiles_v2 (owner,subject_id,relationship,birthday,profile_json,updated_at)"
              " VALUES (?,?,?,?,?,?) ON CONFLICT(owner,subject_id) DO UPDATE SET"
              " relationship=excluded.relationship, birthday=excluded.birthday,"
              " profile_json=excluded.profile_json, updated_at=excluded.updated_at",
              (owner, subject_id,
               relationship or profile_for(c, owner, subject_id).get("relationship", ""),
               birthday or profile_for(c, owner, subject_id).get("birthday", ""),
               json.dumps(merged), _now()))
    c.commit()
    return profile_for(c, owner, subject_id)


def link_photo(c: sqlite3.Connection, photo_id: str, subject_id: str,
               confirmed: bool = False, face_id: str = "",
               provenance: str = "user") -> None:
    """studio_library schema: (photo_id, subject_id, face_id, confirmed, provenance)."""
    c.execute("INSERT OR IGNORE INTO photo_subjects (photo_id,subject_id,face_id,confirmed,provenance)"
              " VALUES (?,?,?,?,?)",
              (photo_id, subject_id, face_id, 1 if confirmed else 0, provenance))
    if confirmed:
        c.execute("UPDATE photo_subjects SET confirmed=1 WHERE photo_id=? AND subject_id=?",
                  (photo_id, subject_id))
    c.commit()


def link_mesh(c: sqlite3.Connection, mesh_id: str, subject_id: str) -> None:
    """studio_library schema: (mesh_id PK, subject_id)."""
    c.execute("INSERT OR REPLACE INTO mesh_subjects (mesh_id,subject_id) VALUES (?,?)",
              (mesh_id, subject_id))
    c.commit()


def confirmed_subjects_for_photo(c: sqlite3.Connection, photo_id: str) -> list[dict]:
    return [dict(r) for r in c.execute(
        "SELECT s.* FROM studio_subjects s JOIN photo_subjects ps ON ps.subject_id=s.id"
        " WHERE ps.photo_id=? AND ps.confirmed=1", (photo_id,))]


def profile_for_photo(c: sqlite3.Connection, owner: str, photo_id: str) -> dict:
    """photo → confirmed photo_subjects → studio_subject → subject_profile (§1)."""
    subs = [s for s in confirmed_subjects_for_photo(c, photo_id) if s["owner"] == owner]
    if not subs:
        return {}
    return {"subject": subs[0], "profile": profile_for(c, owner, subs[0]["id"])}


# ── families ──────────────────────────────────────────────────────────
# A family is a named set of subjects (people AND pets — kind lives on the
# subject). Image-first: members carry no required name; the roster renders
# face emblems and names only when given. Roles (mum/dad/…) live on the
# membership; relationship detail lives in the subject profile.

def create_family(c: sqlite3.Connection, owner: str, name: str) -> dict:
    fid = _new_id(c, "fam")
    c.execute("INSERT INTO families (id,owner,name,created_at) VALUES (?,?,?,?)",
              (fid, owner, (name or "").strip()[:80], _now()))
    c.commit()
    return {"id": fid, "owner": owner, "name": (name or "").strip()[:80]}


def families_for(c: sqlite3.Connection, owner: str) -> list[dict]:
    return [dict(r) for r in c.execute(
        "SELECT * FROM families WHERE owner=? ORDER BY created_at", (owner,))]


def add_member(c: sqlite3.Connection, owner: str, family_id: str,
               subject_id: str, role: str = "") -> dict:
    fam = c.execute("SELECT * FROM families WHERE id=? AND owner=?",
                    (family_id, owner)).fetchone()
    if not fam:
        raise KeyError("family not found")
    sub = get_subject(c, owner, subject_id)
    if not sub:
        raise KeyError("subject not found")
    c.execute("INSERT INTO family_members (family_id,subject_id,role)"
              " VALUES (?,?,?) ON CONFLICT(family_id,subject_id) DO UPDATE SET"
              " role=excluded.role",
              (family_id, subject_id, (role or "").strip()[:40]))
    c.commit()
    return {"family_id": family_id, "subject_id": subject_id,
            "role": (role or "").strip()[:40]}


def remove_member(c: sqlite3.Connection, owner: str, family_id: str,
                  subject_id: str) -> None:
    fam = c.execute("SELECT * FROM families WHERE id=? AND owner=?",
                    (family_id, owner)).fetchone()
    if not fam:
        raise KeyError("family not found")
    c.execute("DELETE FROM family_members WHERE family_id=? AND subject_id=?",
              (family_id, subject_id))
    c.commit()


def family_detail(c: sqlite3.Connection, owner: str, family_id: str) -> dict:
    """Family + members with profiles and a cover chip each (first confirmed
    photo face → thumbnail endpoint params; pets fall back to mesh photo)."""
    fam = c.execute("SELECT * FROM families WHERE id=? AND owner=?",
                    (family_id, owner)).fetchone()
    if not fam:
        return {}
    members = []
    for r in c.execute(
            "SELECT s.*, fm.role FROM family_members fm"
            " JOIN studio_subjects s ON s.id=fm.subject_id"
            " WHERE fm.family_id=? AND s.owner=?", (family_id, owner,)):
        s = dict(r)
        prof = profile_for(c, owner, s["id"])
        cover = c.execute(
            "SELECT ps.photo_id, ps.face_id FROM photo_subjects ps"
            " JOIN photos p ON p.id=ps.photo_id"
            " WHERE ps.subject_id=? AND ps.confirmed=1 AND p.owner=?"
            " ORDER BY ps.face_id DESC LIMIT 1",
            (s["id"], owner)).fetchone()
        if not cover:
            # Pets (and fresh subjects) link via mesh, not photos — cover
            # falls back to the mesh's source photo, faceless.
            cover = c.execute(
                "SELECT m.photo_id AS photo_id, '' AS face_id FROM mesh_subjects ms"
                " JOIN meshes m ON m.id=ms.mesh_id"
                " JOIN photos p ON p.id=m.photo_id"
                " WHERE ms.subject_id=? AND p.owner=? LIMIT 1",
                (s["id"], owner)).fetchone()
        members.append({
            "id": s["id"], "name": s["name"], "kind": s.get("kind", "person"),
            "role": r["role"] or "",
            "relationship": prof.get("relationship", ""),
            "birthday": prof.get("birthday", ""),
            "interests": (prof.get("profile", {}) or {}).get("interests", []),
            "cover": ({"photo_id": cover["photo_id"],
                       "face_id": cover["face_id"] or None}
                      if cover else None),
        })
    d = dict(fam)
    d["members"] = members
    return d


# ── migration from mesh-keyed profiles ────────────────────────────────

def migrate_mesh_profiles(c: sqlite3.Connection) -> int:
    """One subject per distinct (owner, name); meshes linked; facts moved.
    Idempotent: re-runs link what is missing and never duplicate subjects."""
    try:
        rows = c.execute("SELECT * FROM subject_profiles").fetchall()
    except sqlite3.Error:
        return 0
    n = 0
    for r in rows:
        d = dict(r)
        owner, mesh_id = d.get("owner", ""), d.get("mesh_id", "")
        name = (d.get("name") or "").strip() or "Friend"
        if not owner or not mesh_id:
            continue
        sub = find_subject_by_name(c, owner, name)
        if not sub:
            sub = create_subject(c, owner, name)
        link_mesh(c, mesh_id, sub["id"])
        try:
            interests = json.loads(d.get("interests") or "[]")
        except (ValueError, TypeError):
            interests = []
        prof = profile_for(c, owner, sub["id"])
        merged = dict(prof.get("profile", {}))
        merged.setdefault("name", name)
        if interests and not merged.get("interests"):
            merged["interests"] = interests
        set_profile(c, owner, sub["id"], birthday=d.get("birthday", "") or prof.get("birthday", ""),
                    profile=merged)
        n += 1
    return n


# ── assets registry ───────────────────────────────────────────────────

def register_asset(c: sqlite3.Connection, owner: str, kind: str, sha256: str,
                   storage_key: str, *, parent_id: str = "",
                   metadata: dict | None = None, provenance: str = "") -> dict:
    import uuid
    row = c.execute("SELECT * FROM assets WHERE owner=? AND sha256=? AND kind=? AND parent_id=?",
                    (owner, sha256, kind, parent_id)).fetchone()
    if row:
        return dict(row)
    aid = f"ast_{uuid.uuid4().hex[:12]}"
    c.execute("INSERT INTO assets (id,owner,kind,sha256,storage_key,parent_id,metadata,provenance,created_at)"
              " VALUES (?,?,?,?,?,?,?,?,?)",
              (aid, owner, kind, sha256, storage_key, parent_id,
               json.dumps(metadata or {}), provenance, _now()))
    c.commit()
    return dict(c.execute("SELECT * FROM assets WHERE id=?", (aid,)).fetchone())


def derived(c: sqlite3.Connection, parent_id: str) -> list[dict]:
    return [dict(r) for r in c.execute(
        "SELECT * FROM assets WHERE parent_id=? ORDER BY created_at", (parent_id,))]
