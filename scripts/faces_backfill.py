#!/usr/bin/env python3
"""Backfill face boxes + SFace embeddings for an owner's photos.

    python3 scripts/faces_backfill.py --owner hark-dad-a7a5cc [--limit 50] [--dry-run]

Boxes land in photo_faces (source 'sface-import', unconfirmed — identity
links still need explicit user confirm per the studio_library contract).
Embeddings land in face_embeddings. studio_photo_meta.detection_status
moves pending → embedded. CPU only, 0 credits.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backend import config, db
from backend import faces as F


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--owner", required=True)
    ap.add_argument("--limit", type=int, default=200)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    import cv2 as _cv2
    import struct as _st
    import time as _t

    F.ensure_schema()
    # One connection for the whole run: per-photo commits, no lock upgrades
    # against ourselves while the live server is writing too.
    import sqlite3 as _s3

    with db.connect() as c:
        photos = [dict(r) for r in c.execute(
            "SELECT * FROM photos WHERE owner=? ORDER BY created_at DESC LIMIT ?",
            (args.owner, args.limit)).fetchall()]
    print(f"photos: {len(photos)}")

    from backend import pipeline
    n_faces = n_embed = 0
    with db.connect() as c:
        for p in photos:
            try:
                local = pipeline._local_photo(p)
            except Exception as e:
                print(f"  {p['id']}: no local bytes ({e})")
                continue
            if not local:
                print(f"  {p['id']}: no local bytes")
                continue
            bgr = _cv2.imread(str(local))
            if bgr is None:
                print(f"  {p['id']}: unreadable")
                continue
            boxes = F.detect_boxes(bgr)
            print(f"  {p['id']}: {len(boxes)} face(s)")
            if args.dry_run:
                continue
            for f in boxes:
                x, y, w, h = (float(v) for v in f[:4])
                fid = db.new_id("face")
                h_px, w_px = bgr.shape[:2]
                box = F.to_unit([x, y, w, h], w_px, h_px)
                c.execute(
                    "INSERT OR IGNORE INTO photo_faces (id,photo_id,box,score,source)"
                    " VALUES (?,?,?,?,?)",
                    (fid, p["id"], json.dumps(box),
                     float(f[-1]), "sface-import"))
                vec = F.embed_face(bgr, f)
                if vec is not None:
                    blob = _st.pack(f"{len(vec)}f", *[float(v) for v in vec])
                    c.execute(
                        "INSERT INTO face_embeddings"
                        " (face_id,photo_id,owner,model,dim,vec,created_at)"
                        " VALUES (?,?,?,?,?,?,?) ON CONFLICT(face_id) DO UPDATE SET"
                        " vec=excluded.vec, created_at=excluded.created_at",
                        (fid, p["id"], args.owner, F.MODEL, len(vec),
                         blob, _t.time()))
                    n_embed += 1
                n_faces += 1
            c.execute(
                "INSERT INTO studio_photo_meta (photo_id,detection_status)"
                " VALUES (?,?) ON CONFLICT(photo_id) DO UPDATE SET"
                " detection_status=excluded.detection_status",
                (p["id"], "embedded"))
            c.commit()
    print(f"faces: {n_faces}, embedded: {n_embed}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
