"""Make a local image fetchable from the zone.

Cloudflare only pulls transformation sources from the zone that serves them
(or from explicitly allowed origins), so an upload sitting on local disk has
to be published first. Files are staged into a public directory that the
bridge serves at ``/premesh/`` and deleted by ``prune()`` afterwards.

An already-public URL is passed straight through — normalising a photo that
lives in R2 behind a public route costs nothing extra.
"""
from __future__ import annotations

import hashlib
import os
import time
from pathlib import Path

from .cloudflare import zone_base

_REPO = Path(__file__).resolve().parent.parent
STAGE_DIR = Path(os.environ.get("PREMESH_STAGE_DIR", _REPO / "data" / "premesh" / "public"))
STAGE_PREFIX = "/premesh/"


class StageError(Exception):
    pass


def _ext_for(data: bytes) -> str:
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "webp"
    return "jpg"


def stage(data: bytes, name: str | None = None, zone: str | None = None) -> str:
    """Publish ``data`` on the zone and return its public URL."""
    if not data:
        raise StageError("nothing to stage")
    digest = hashlib.sha256(data).hexdigest()
    ext = _ext_for(data)
    # Content-addressed: the same bytes never get staged twice, so Cloudflare
    # hits its cache and we never pay for a duplicate transformation.
    filename = f"{digest[:32]}.{ext}"
    STAGE_DIR.mkdir(parents=True, exist_ok=True)
    dest = STAGE_DIR / filename
    if not dest.exists():
        tmp = dest.with_suffix(dest.suffix + ".part")
        tmp.write_bytes(data)
        tmp.replace(dest)
    return f"{zone_base(zone)}{STAGE_PREFIX}{filename}"


def ensure_url(source, zone: str | None = None) -> str:
    """Accept a URL, path or raw bytes and return a URL the zone can fetch."""
    if isinstance(source, str) and source.startswith("http"):
        return source
    if isinstance(source, (bytes, bytearray)):
        return stage(bytes(source), zone=zone)
    path = Path(source)
    if not path.is_file():
        raise StageError(f"no such file: {path}")
    return stage(path.read_bytes(), name=path.name, zone=zone)


def prune(max_age_hours: float = 12.0) -> int:
    """Drop staged files older than the cutoff. Returns files removed."""
    if not STAGE_DIR.is_dir():
        return 0
    cutoff = time.time() - max_age_hours * 3600
    removed = 0
    for p in STAGE_DIR.iterdir():
        if p.is_file() and p.stat().st_mtime < cutoff:
            p.unlink(missing_ok=True)
            removed += 1
    return removed
