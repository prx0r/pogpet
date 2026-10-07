"""Photo intake — accept one good photo, reject bad ones politely.

Mirrors the constraints from the build prompt: single JPEG/PNG, max 10MB.
Does the boring-but-critical work: magic-byte sniffing (not trusting the
client's content-type), EXIF orientation, downscale to MAX_EDGE, and a
content hash so re-uploads of the same photo are free.
"""
from __future__ import annotations

import hashlib
import io
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageOps, UnidentifiedImageError

from . import config


class IntakeError(Exception):
    """A user-fixable problem with the photo. Message is safe to show."""

    def __init__(self, message: str, code: int = 400):
        super().__init__(message)
        self.code = code


@dataclass
class Accepted:
    path: Path
    sha256: str
    mime: str
    width: int
    height: int
    nbytes: int
    orig_name: str


def sniff_mime(head: bytes) -> str:
    if head.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if head.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        return "image/webp"
    if head[:6] in (b"GIF87a", b"GIF89a"):
        return "image/gif"
    return "application/octet-stream"


def _has_face_like_subject(img: Image.Image) -> bool:
    """Cheap sanity check: a fully flat frame is almost always a bad upload.

    Not a face detector — just catches the 'uploaded a solid colour by
    accident' and 'file is a screenshot of nothing' cases early, before we
    spend Meshy credits on them.
    """
    small = img.convert("L").resize((32, 32))
    px = list(small.getdata())
    lo, hi = min(px), max(px)
    return (hi - lo) > 6


def accept(data: bytes, orig_name: str, owner: str = "") -> Accepted:
    if not data:
        raise IntakeError("That upload came through empty — try again?")
    if len(data) > config.MAX_UPLOAD_BYTES:
        mb = config.MAX_UPLOAD_BYTES / (1024 * 1024)
        raise IntakeError(f"That file is {len(data)/1048576:.1f} MB — max is {mb:.0f} MB.")

    mime = sniff_mime(data[:16])
    if mime not in config.ALLOWED_MIME:
        raise IntakeError("Please upload a JPEG, PNG or WebP photo of your pet.")

    try:
        img = Image.open(io.BytesIO(data))
        img.load()
    except (UnidentifiedImageError, OSError):
        raise IntakeError("That file doesn't look like an image we can read.") from None

    # EXIF orientation first — phone photos are routinely sideways and Meshy
    # will happily build a sideways pet.
    img = ImageOps.exif_transpose(img) or img

    if img.width < 256 or img.height < 256:
        raise IntakeError(
            f"That photo is only {img.width}×{img.height} — we need at least 256px "
            "on the short side so the sculpt comes out sharp."
        )

    if not _has_face_like_subject(img):
        raise IntakeError(
            "That image looks flat or blank — could you upload a clearer photo "
            "with your pet filling the frame?"
        )

    if img.mode in ("RGBA", "P", "LA"):
        img = img.convert("RGB")
    elif img.mode != "RGB":
        img = img.convert("RGB")

    if max(img.size) > config.MAX_EDGE:
        img.thumbnail((config.MAX_EDGE, config.MAX_EDGE), Image.LANCZOS)

    sha = hashlib.sha256(data).hexdigest()
    # Hash the *processed* bytes too, so a re-upload after our own downscale
    # still dedupes.
    out = io.BytesIO()
    img.save(out, format="JPEG", quality=90, optimize=True)
    processed = out.getvalue()
    content_sha = hashlib.sha256(processed).hexdigest()

    config.ensure_dirs()
    dest = config.LOCAL_TMP / f"{content_sha}.jpg"
    if not dest.exists():
        dest.write_bytes(processed)

    return Accepted(
        path=dest,
        sha256=content_sha,
        mime="image/jpeg",
        width=img.width,
        height=img.height,
        nbytes=len(processed),
        orig_name=Path(orig_name or "photo.jpg").name[:120],
    )
