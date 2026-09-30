#!/usr/bin/env python3
"""Seed the demo/sample pet: our dog mesh + its source PNG, ready to preview.

    set -a; . ./.env; set +a; python3 scripts/seed_sample.py [--owner anon]

Creates (idempotently):
  * a photo row backed by the premesh-normalised PNG,
  * a mesh row backed by data/uploads/chibi-figure.glb (status succeeded),
  * product bindings for every entry in config.PRODUCTS,
  * the profile's active mesh.

The point: every visitor and every new product has something to render
against immediately. New products added later are picked up by the lazy
bind in GET /api/meshes/<id>/products (see docs/foundation.md — the
inheritance guarantee). 0 credits — this never touches Meshy.
"""
from __future__ import annotations

import argparse
import hashlib
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# load .env (storage uses rclone, config reads env)
env = ROOT / ".env"
if env.is_file():
    for line in env.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k, v.strip().strip("'\""))

from backend import config, db, storage  # noqa: E402

PHOTO = Path(os.environ.get("SEED_PHOTO",
                            "/tmp/opencode/premesh-out/golden.meshy.png"))
GLB = Path(os.environ.get("SEED_GLB", ROOT / "data" / "uploads" / "chibi-figure.glb"))
ORIG_NAME = "sample-dog.png"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--owner", default="anon")
    args = ap.parse_args()
    owner = args.owner

    if not PHOTO.is_file() or not GLB.is_file():
        print(f"missing inputs: photo={PHOTO.exists()} glb={GLB.exists()}")
        return 1

    sha = hashlib.sha256(PHOTO.read_bytes()).hexdigest()
    with db.connect() as c:
        # idempotency: the sample photo is identified by its content hash
        row = db.find_photo_by_hash(c, sha, owner)
        if row is None:
            from PIL import Image
            im = Image.open(PHOTO)
            r2_key = storage.photo_key(owner, sha)
            storage.put(PHOTO, r2_key)
            photo_id = db.insert_photo(
                c, owner=owner, sha256=sha, r2_key=r2_key, mime="image/png",
                width=im.width, height=im.height, bytes=PHOTO.stat().st_size,
                orig_name=ORIG_NAME)
            print(f"photo {photo_id} -> r2:{r2_key} ({im.width}x{im.height})")
        else:
            photo_id = row["id"]
            print(f"photo already present: {photo_id}")

        existing = [m for m in db.pogs_for(c, owner) if m.get("photo_id") == photo_id]
        if existing:
            mid = existing[0]["id"]
            print(f"mesh already present: {mid}")
        else:
            mid = db.create_mesh(c, photo_id, provider="sample")
            keys = storage.mesh_keys(owner, mid)
            storage.put(GLB, keys["glb"])
            db.update_mesh(c, mid, status="succeeded", error="",
                           glb_key=keys["glb"], thumb_keys="[]",
                           texture_keys="[]", print_ready=1, stub=0)
            print(f"mesh {mid} -> r2:{keys['glb']} ({GLB.stat().st_size:,} bytes)")

        created = db.bind_products(c, mid, config.PRODUCTS.keys())
        print(f"bindings: +{created} (idempotent — re-runs keep existing rows)")
        db.set_active(c, owner, mid)
        print(f"active mesh for {owner!r} = {mid}")
        bound = {r["product"] for r in c.execute(
            "SELECT product FROM product_bindings WHERE mesh_id=?", (mid,))}
        print(f"mesh now bound to {len(bound)}/{len(config.PRODUCTS)} products")
    print("done — 0 credits spent")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
