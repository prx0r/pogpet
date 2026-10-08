#!/usr/bin/env python3
"""Seed a stock demo family: copy confirmed photos (bytes + faces + links +
profiles) from a real owner's subjects into another owner's demo subjects.

Dry run by default. --apply executes. Idempotent: existing demo subject
names under --into are skipped.

    python3 scripts/seed_stock_family.py --owner hark-dad-a7a5cc \\
        --subjects "Chris Prior,Cathy" --into anon --per 3
    python3 scripts/seed_stock_family.py ... --apply

Demo copies are independent rows + independent R2 keys: deleting them
revokes the demo without touching the source family.
"""
from __future__ import annotations

import argparse
import sys
import time
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backend import db, storage, subjects as sub  # noqa: E402


def plan(owner: str, names: list[str], per: int) -> list[dict]:
    steps = []
    with db.connect() as c:
        for name in names:
            s = sub.find_subject_by_name(c, owner, name)
            if not s:
                steps.append({"subject": name, "error": "not found"})
                continue
            links = c.execute(
                "SELECT photo_id FROM photo_subjects WHERE subject_id=? AND confirmed=1",
                (s["id"],)).fetchall()
            pids = [r["photo_id"] for r in links][:per]
            steps.append({"subject": name, "subject_id": s["id"],
                          "kind": s.get("kind", "person"), "photos": pids})
    return steps


def apply_step(into: str, step: dict, demo_names: dict) -> dict:
    done = {"subject": step["subject"], "photos": 0, "faces": 0}
    with db.connect() as c:
        ds = sub.find_subject_by_name(c, into, step["subject"])
        if not ds:
            ds = sub.create_subject(c, into, step["subject"],
                                    kind=step.get("kind") or "person")
        for pid in step["photos"]:
            p = c.execute("SELECT * FROM photos WHERE id=?", (pid,)).fetchone()
            if not p:
                continue
            p = dict(p)
            if p.get("sha256"):
                dupe = c.execute("SELECT id FROM photos WHERE sha256=? AND owner=?",
                                 (p["sha256"], into)).fetchone()
                if dupe:
                    # group photo already copied for the other parent: link it
                    dfaces = [dict(f) for f in c.execute(
                        "SELECT * FROM photo_faces WHERE photo_id=?", (dupe["id"],))]
                    if dfaces:
                        for f in dfaces:
                            sub.link_photo(c, dupe["id"], ds["id"], confirmed=True,
                                           face_id=f["id"], provenance="stock-family")
                    else:
                        sub.link_photo(c, dupe["id"], ds["id"], confirmed=True,
                                       provenance="stock-family")
                    done["photos"] += 1
                    continue
            nid = "pho_demo_" + uuid.uuid4().hex[:16]
            nkey = f"owners/{storage._slug(into)}/demo/{nid}.png"
            src = Path(f"/tmp/stockfam-{nid}.bin")
            try:
                storage.get(p["r2_key"], src)
                storage.put(src, nkey)
            finally:
                src.unlink(missing_ok=True)
            c.execute("INSERT INTO photos (id,owner,sha256,r2_key,mime,width,height,bytes,orig_name,created_at,person,source)"
                      " VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                      (nid, into, p.get("sha256") or "", nkey, p.get("mime") or "image/png",
                       p.get("width") or 0, p.get("height") or 0, p.get("bytes") or 0,
                       p.get("orig_name") or "demo", time.time(), step["subject"], "stock-family"))
            faces = [dict(f) for f in
                     c.execute("SELECT * FROM photo_faces WHERE photo_id=?", (pid,))]
            if faces:
                for f in faces:
                    fid = "fac_demo_" + uuid.uuid4().hex[:16]
                    c.execute("INSERT INTO photo_faces (id,photo_id,box,score,source) VALUES (?,?,?,?,?)",
                              (fid, nid, f.get("box") or "[]", f.get("score") or 0,
                               f.get("source") or "mediapipe"))
                    done["faces"] += 1
                    sub.link_photo(c, nid, ds["id"], confirmed=True, face_id=fid,
                                   provenance="stock-family")
            else:
                sub.link_photo(c, nid, ds["id"], confirmed=True, provenance="stock-family")
            done["photos"] += 1
        c.commit()
    demo_names[step["subject"]] = ds["id"]
    return done


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--owner", required=True)
    ap.add_argument("--subjects", required=True, help="comma-separated names")
    ap.add_argument("--into", default="anon")
    ap.add_argument("--per", type=int, default=3)
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()
    names = [n.strip() for n in args.subjects.split(",") if n.strip()]
    steps = plan(args.owner, names, args.per)
    for s in steps:
        if s.get("error"):
            print(f"SKIP {s['subject']}: {s['error']}")
        else:
            print(f"PLAN {s['subject']}: {len(s['photos'])} photos {s['photos']}")
    if not args.apply:
        print("dry run — pass --apply to execute")
        return 0
    # profiles need the source owner at copy time; stash per subject below
    with db.connect() as c:
        src_profiles = {}
        for s in steps:
            if s.get("error"):
                continue
            src_profiles[s["subject"]] = sub.profile_for(c, args.owner, s["subject_id"])
    demo_names: dict = {}
    for s in steps:
        if s.get("error"):
            continue
        with db.connect() as c:
            ds = sub.find_subject_by_name(c, args.into, s["subject"])
        res = apply_step(args.into, s, demo_names)
        print(f"COPIED {s['subject']}: {res['photos']} photos, {res['faces']} faces")
    with db.connect() as c:
        for s in steps:
            if s.get("error"):
                continue
            prof = (src_profiles.get(s["subject"]) or {}).get("profile", {})
            dsid = demo_names.get(s["subject"], "")
            if dsid and prof:
                sub.set_profile(c, args.into, dsid,
                                relationship=prof.get("relationship", ""),
                                birthday=prof.get("birthday", ""),
                                profile=prof)
        c.commit()
    print("profiles copied; demo subjects:", demo_names)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
