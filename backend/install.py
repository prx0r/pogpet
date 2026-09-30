"""Install a GLB as a pog — shared by file upload and style presets.

Both callers hand us a path to a GLB; everything after that is identical:
validate, derive a portrait by rendering it, store under the owner's R2
namespace, bind every product, and activate it if it's their first.

Kept out of server.py so the style presets and the agent upload can't drift.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

from . import config, db, storage


class InstallError(Exception):
    def __init__(self, message: str, code: int = 400):
        super().__init__(message)
        self.code = code


def validate_glb(path: Path) -> int:
    if not path.exists():
        raise InstallError("GLB not found", 404)
    size = path.stat().st_size
    if size < 64:
        raise InstallError("that file is empty", 400)
    if size > 64 * 1024 * 1024:
        raise InstallError("GLB over 64 MB", 413)
    with path.open("rb") as f:
        if f.read(4) != b"glTF":
            raise InstallError("not a GLB (missing glTF magic) — export as .glb", 400)
    return size


def install_glb(owner: str, glb_path: Path, source: str = "upload",
                label: str = "") -> dict:
    """GLB -> a live, active, product-bound pog. No Meshy involved."""
    size = validate_glb(glb_path)
    config.ensure_dirs()

    from . import render as meshrender          # lazy: pulls in numpy
    portrait = config.LOCAL_TMP / f"pf_{glb_path.stem}_{__import__('uuid').uuid4().hex[:8]}.png"
    try:
        meshrender.render_glb(glb_path, portrait, 512)
    except Exception as e:
        raise InstallError(f"could not render that mesh: {str(e)[:200]}", 422)

    try:
        with db.connect() as c:
            psha = hashlib.sha256(portrait.read_bytes()).hexdigest()
            pkey = storage.photo_key(owner, psha)
            if not storage.exists(pkey):
                storage.put(portrait, pkey)
            row = db.find_photo_by_hash(c, psha, owner)
            pid = row["id"] if row else db.insert_photo(
                c, owner=owner, sha256=psha, r2_key=pkey, mime="image/png",
                width=512, height=512, bytes=portrait.stat().st_size,
                orig_name=(label or glb_path.name)[:120])

            mid = db.new_id("msh")
            c.execute(
                "INSERT INTO meshes (id,photo_id,provider,status,stub,print_ready,"
                "created_at,updated_at) VALUES (?,?,?, 'succeeded', 0, 1, ?, ?)",
                (mid, pid, source, db.now(), db.now()))
            gkey = storage.mesh_keys(owner, mid)["glb"]
            storage.put(glb_path, gkey)
            db.update_mesh(c, mid, glb_key=gkey)
            db.bind_products(c, mid, config.PRODUCTS.keys())
            was_first = not db.get_profile(c, owner).get("active_mesh_id")
            if was_first:
                db.set_active(c, owner, mid)
            mesh = db.get_mesh(c, mid)
            products = db.products_for(c, mid)
    finally:
        portrait.unlink(missing_ok=True)

    return {"ok": True, "owner": owner, "mesh": db.dump(mesh),
            "products": len(products), "active": was_first, "bytes": size,
            "source": source,
            "note": "stored under your own R2 namespace"}
