"""Creative projects + immutable revisions (cardgen.md §8).

Generalizes card_designs/card_revisions: a project binds a subject to a
template lineage; every edit is a new revision; orders reference revisions,
never mutate them.
"""
from __future__ import annotations

import json
import sqlite3
import time
import uuid


def ensure_tables(c: sqlite3.Connection) -> None:
    c.executescript("""
    CREATE TABLE IF NOT EXISTS creative_projects (
      id              TEXT PRIMARY KEY,
      owner           TEXT NOT NULL,
      subject_id      TEXT NOT NULL DEFAULT '',
      template_id     TEXT NOT NULL DEFAULT '',
      latest_revision INTEGER NOT NULL DEFAULT 0,
      created_at      REAL NOT NULL
    );
    CREATE INDEX IF NOT EXISTS idx_creative_owner ON creative_projects(owner);
    CREATE TABLE IF NOT EXISTS creative_revisions (
      project_id       TEXT NOT NULL,
      revision         INTEGER NOT NULL,
      template_id      TEXT NOT NULL,
      template_version INTEGER NOT NULL DEFAULT 1,
      brief_snapshot   TEXT NOT NULL DEFAULT '{}',
      scene            TEXT NOT NULL DEFAULT '{}',
      created_at       REAL NOT NULL,
      PRIMARY KEY (project_id, revision)
    );
    """)
    c.commit()


def create_project(c: sqlite3.Connection, owner: str, subject_id: str = "",
                   template_id: str = "") -> dict:
    pid = f"crp_{uuid.uuid4().hex[:12]}"
    c.execute("INSERT INTO creative_projects (id,owner,subject_id,template_id,latest_revision,created_at)"
              " VALUES (?,?,?,?,0,?)", (pid, owner, subject_id, template_id, time.time()))
    c.commit()
    return {"id": pid, "owner": owner, "subject_id": subject_id,
            "template_id": template_id, "latest_revision": 0}


def find_project(c: sqlite3.Connection, owner: str, subject_id: str,
                 template_id: str) -> dict:
    """Lineage key: (owner, subject, template). Mum never lands in Dad's project."""
    row = c.execute("SELECT * FROM creative_projects WHERE owner=? AND subject_id=? AND template_id=?",
                    (owner, subject_id, template_id)).fetchone()
    return dict(row) if row else {}


def save_revision(c: sqlite3.Connection, project_id: str, template_id: str,
                  template_version: int, brief: dict, scene: dict,
                  expected_revision: int | None = None) -> dict:
    row = c.execute("SELECT latest_revision, template_id FROM creative_projects WHERE id=?",
                    (project_id,)).fetchone()
    if row is None:
        raise KeyError("no such project")
    cur = dict(row)
    if cur["template_id"] != template_id:
        raise ValueError(f"template lineage locked to {cur['template_id']} — start a new project")
    if expected_revision is not None and int(expected_revision) != int(cur["latest_revision"]):
        raise ValueError(f"stale write: latest is r{cur['latest_revision']}")
    rev = int(cur["latest_revision"]) + 1
    c.execute("INSERT INTO creative_revisions (project_id,revision,template_id,template_version,brief_snapshot,scene,created_at)"
              " VALUES (?,?,?,?,?,?,?)",
              (project_id, rev, template_id, template_version,
               json.dumps(brief), json.dumps(scene), time.time()))
    n = c.execute("UPDATE creative_projects SET latest_revision=? WHERE id=? AND latest_revision=?",
                  (rev, project_id, cur["latest_revision"])).rowcount
    if not n:
        raise ValueError("concurrent write lost — refetch and retry")
    c.commit()
    return {"project_id": project_id, "revision": rev, "template_id": template_id,
            "template_version": template_version}


def get_revision(c: sqlite3.Connection, project_id: str, revision: int) -> dict:
    row = c.execute("SELECT * FROM creative_revisions WHERE project_id=? AND revision=?",
                    (project_id, revision)).fetchone()
    if row is None:
        return {}
    d = dict(row)
    for k in ("brief_snapshot", "scene"):
        try:
            d[k] = json.loads(d.get(k) or "{}")
        except (ValueError, TypeError):
            d[k] = {}
    return d
