"""Accept or reject a normalised image.

The transforms are cheap and the next step (Meshy) is not, so everything
gets checked before it goes anywhere: did the cut-out happen, is the subject
actually in frame, is it big enough. Failures come back as a report rather
than an exception so a caller can retry with a different recipe.
"""
from __future__ import annotations

import io
from dataclasses import dataclass, field, asdict

from PIL import Image, UnidentifiedImageError

from .recipes import QCConfig


@dataclass
class Report:
    ok: bool
    width: int = 0
    height: int = 0
    mode: str = ""
    fmt: str = ""                # actual container: PNG / JPEG / WEBP
    has_alpha: bool = False
    coverage: float = 0.0        # fraction of frame the subject occupies
    bbox: tuple[int, int, int, int] | None = None
    issues: list[str] = field(default_factory=list)

    @property
    def content_type(self) -> str:
        return {"PNG": "image/png", "JPEG": "image/jpeg",
                "MPO": "image/jpeg", "WEBP": "image/webp"}.get(
                    self.fmt, "application/octet-stream")

    def as_dict(self) -> dict:
        return asdict(self)


def _alpha_bbox(img: Image.Image):
    """Bounding box of the non-transparent pixels, or None if fully opaque/empty."""
    if img.mode != "RGBA":
        img = img.convert("RGBA")
    alpha = img.getchannel("A")
    lo, hi = alpha.getextrema()
    if lo == 255:                    # no transparency at all — cut-out didn't happen
        return None, 0.0
    if hi == 0:                      # fully transparent — nothing survived
        return (0, 0, 0, 0), 0.0
    bbox = alpha.getbbox()
    if not bbox:
        return None, 0.0
    w, h = img.size
    coverage = ((bbox[2] - bbox[0]) * (bbox[3] - bbox[1])) / float(w * h)
    return bbox, coverage


def check(data: bytes, cfg: QCConfig) -> Report:
    rep = Report(ok=False)
    try:
        img = Image.open(io.BytesIO(data))
        img.load()
    except (UnidentifiedImageError, OSError):
        rep.issues.append("output is not a readable image")
        return rep

    rep.width, rep.height = img.size
    rep.mode = img.mode
    rep.fmt = (img.format or "").upper()
    rep.has_alpha = img.mode in ("RGBA", "LA", "PA") or "transparency" in img.info

    if min(img.size) < cfg.min_side:
        rep.issues.append(f"short side {min(img.size)}px < {cfg.min_side}px")
    if cfg.min_long and max(img.size) < cfg.min_long:
        rep.issues.append(f"long side {max(img.size)}px < {cfg.min_long}px")
    if max(img.size) > cfg.max_side:
        rep.issues.append(f"long side {max(img.size)}px > {cfg.max_side}px")

    aspect = img.size[0] / img.size[1]
    if not (cfg.aspect_min <= aspect <= cfg.aspect_max):
        rep.issues.append(f"aspect {aspect:.2f} outside "
                          f"[{cfg.aspect_min}, {cfg.aspect_max}]")

    if cfg.require_alpha:
        if not rep.has_alpha:
            rep.issues.append("expected a transparent cut-out, got no alpha channel")
        else:
            bbox, coverage = _alpha_bbox(img)
            rep.coverage = round(coverage, 4)
            rep.bbox = bbox
            if bbox is None:
                rep.issues.append("no transparency — segmentation produced nothing")
            elif coverage < cfg.min_coverage:
                rep.issues.append(f"subject covers {coverage:.1%} of frame "
                                  f"(< {cfg.min_coverage:.0%}) — wrong thing cut out?")
            elif coverage > cfg.max_coverage:
                rep.issues.append(f"subject covers {coverage:.1%} of frame "
                                  f"(> {cfg.max_coverage:.0%}) — background still present")

    rep.ok = not rep.issues
    return rep
