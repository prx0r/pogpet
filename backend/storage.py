"""R2 storage.

Uses the `rclone` remote (`r2:`) that is already configured on this box —
no credential handling here at all, which keeps the keys out of our code
and out of the repo. boto3 is available if we ever need signed URLs.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

from . import config


class StorageError(Exception):
    pass


def _run(args: list[str], timeout: int = 120) -> subprocess.CompletedProcess:
    proc = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
    if proc.returncode != 0:
        raise StorageError((proc.stderr or proc.stdout or "rclone failed").strip()[:400])
    return proc


def put(local: Path, key: str) -> str:
    """Upload a local file to R2 at `key`. Returns the key."""
    if not local.exists():
        raise StorageError(f"missing local file: {local}")
    config.ensure_dirs()
    _run([config.RCLONE, "copyto", str(local), f"{config.R2_REMOTE}{key}",
          "--retries", "3", "--low-level-retries", "5"])
    return key


def get(key: str, dest: Path) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists():
        dest.unlink()
    _run([config.RCLONE, "copyto", f"{config.R2_REMOTE}{key}", str(dest)])
    # rclone can exit 0 without materialising the target (empty/odd key);
    # surface that as a storage error rather than a downstream FileNotFoundError.
    if not dest.exists() or dest.stat().st_size == 0:
        raise StorageError(f"object not found or empty: {key}")
    return dest


def exists(key: str) -> bool:
    proc = subprocess.run([config.RCLONE, "lsf", f"{config.R2_REMOTE}{key}"],
                          capture_output=True, text=True, timeout=60)
    return proc.returncode == 0 and bool(proc.stdout.strip())


def public_url(key: str) -> str:
    """Read URL for an artifact.

    Objects are private, so this is the rclone-backed gateway path the
    backend serves (GET /api/artifacts/<key>), not a raw R2 URL. Returns a
    relative path the frontend can use directly.
    """
    return f"/api/artifacts/{key}"


def photo_key(owner: str, sha: str) -> str:
    """Content-addressed *within* an owner's namespace.

    Every account gets its own prefix under owners/<owner>/ so a user's
    assets are listable, quota-able and deletable as a unit. The sha suffix
    still makes re-uploads land on the same object for free.
    """
    safe = _slug(owner)
    return f"owners/{safe}/photos/{sha[:2]}/{sha}.jpg"


def mesh_keys(owner: str, mesh_id: str) -> dict[str, str]:
    base = f"owners/{_slug(owner)}/meshes/{mesh_id}"
    return {
        "glb": f"{base}/model.glb",
        "thumbnails": f"{base}/thumbs",
        "textures": f"{base}/textures",
        "preview": f"{base}/preview.jpg",
    }


def _slug(owner: str) -> str:
    """Namespace-safe owner token. Never trust a raw user string in a key."""
    import re
    s = re.sub(r"[^A-Za-z0-9._-]", "-", (owner or "anon").strip())[:64]
    return s.strip("-._") or "anon"


def claim_owner(old: str, new: str) -> None:
    """Move an anonymous owner's whole R2 subtree onto their real handle.

    Storage keys are derived from the owner, so without this the rows would
    point at a path nobody lists under. Best-effort: a missing old prefix is
    not an error (there may have been nothing stored yet).
    """
    a, b = _slug(old), _slug(new)
    if a == b:
        return
    for sub in ("photos", "meshes", "products"):
        src = f"{config.R2_REMOTE}owners/{a}/{sub}"
        dst = f"{config.R2_REMOTE}owners/{b}/{sub}"
        subprocess.run([config.RCLONE, "movetree", src, dst],
                       capture_output=True, text=True, timeout=180)


def list_keys(prefix: str) -> set[str]:
    """Filenames directly under a prefix, in ONE rclone call.

    Checking 12 keys with 12 round trips cost ~6s on the shop's first paint;
    a single list brings that to one call.
    """
    proc = subprocess.run([config.RCLONE, "lsf", f"{config.R2_REMOTE}{prefix}"],
                          capture_output=True, text=True, timeout=60)
    if proc.returncode != 0:
        raise StorageError((proc.stderr or "rclone failed").strip()[:300])
    return {line.strip().rstrip("/") for line in proc.stdout.splitlines() if line.strip()}


def list_owner(owner: str) -> list[str]:
    """Everything this owner has stored — their personal R2 bucket view."""
    proc = subprocess.run(
        [config.RCLONE, "lsf", f"{config.R2_REMOTE}owners/{_slug(owner)}/", "-R"],
        capture_output=True, text=True, timeout=60,
    )
    if proc.returncode != 0:
        raise StorageError((proc.stderr or "rclone failed").strip()[:300])
    # rclone -R emits directories too — count files only, and do it before
    # stripping the trailing slash (which would make a dir look like a file).
    return [line.strip() for line in proc.stdout.splitlines()
            if line.strip() and not line.rstrip().endswith("/")]
