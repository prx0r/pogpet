"""premesh — normalise an uploaded image into whatever comes next.

One job: take a photo a human uploaded (phone camera, screenshots, cropped
web images) and turn it into a well-formed input for the next stage — a
Meshy photo-to-3D call, a greeting-card subject cut-out, a thumbnail.

    from premesh import normalize

    out = normalize(photo_bytes, recipe="meshy")
    out.data        # the normalised PNG bytes
    out.url         # transformation URL actually requested (reproducible)
    out.report      # QC report — out.report.ok tells you it passed
    out.traces      # per-step record for the db

Nothing here imports the backend: PIL and the standard library only, so the
same folder can be dropped into another project (the greeting-card side) and
driven from its own CLI:

    python3 -m premesh photo.jpg -o out/ --recipe meshy

Requires the zone to have Image Transformations enabled and the bridge to
serve ``/premesh/`` from ``data/premesh/public/`` (see README.md).
"""
from __future__ import annotations

import io
from dataclasses import dataclass, field, asdict
from pathlib import Path

from PIL import Image, UnidentifiedImageError

from . import cloudflare, pixabay, qc, stage
from .recipes import RECIPES, Recipe, get

TransformError = cloudflare.TransformError


@dataclass
class Normalized:
    data: bytes
    recipe: str
    source: str                 # what we were given (url / path / "bytes:N")
    url: str                    # transformation URL requested for the main pass
    report: qc.Report
    options: tuple[str, ...]
    source_url: str = ""        # where Cloudflare fetched the image from
    meta: dict = field(default_factory=dict)   # provenance (e.g. Pixabay hit)
    traces: list[dict] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.report.ok

    @property
    def content_type(self) -> str:
        return self.report.content_type

    def as_dict(self) -> dict:
        d = asdict(self)
        d.pop("data")
        d["bytes"] = len(self.data)
        d["ok"] = self.report.ok
        return d


def _as_bytes(source) -> bytes:
    if isinstance(source, (bytes, bytearray)):
        return bytes(source)
    if isinstance(source, str) and source.startswith("http"):
        import urllib.request
        req = urllib.request.Request(source, headers={"User-Agent": "premesh/1.0"})
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.read()
    return Path(source).read_bytes()


def _short_side(source) -> int | None:
    """Short side of the source if we can read it locally, else None (URL)."""
    try:
        if isinstance(source, (bytes, bytearray)):
            img = Image.open(io.BytesIO(bytes(source)))
        elif isinstance(source, str) and source.startswith("http"):
            return None
        else:
            img = Image.open(Path(source))
        return min(img.size)
    except (UnidentifiedImageError, OSError, ValueError):
        return None


def normalize(source, recipe: str | Recipe = "meshy", *, zone: str | None = None,
              timeout: float = 90.0, retries: int = 1) -> Normalized:
    """Normalise ``source`` (URL, path or bytes) with ``recipe``.

    Raises ``TransformError`` if Cloudflare fails, and returns a ``Normalized``
    whose ``report.ok`` is False if the output fails QC — QC failure is a
    value, not an exception, because the caller usually wants to know *why*
    before deciding to retry.
    """
    rec = get(recipe) if isinstance(recipe, str) else recipe
    given = source if isinstance(source, str) and source.startswith("http") else \
        (f"bytes:{len(source)}B" if isinstance(source, (bytes, bytearray)) else str(source))

    traces: list[dict] = []
    meta: dict = {}

    # Pixabay page URLs are resolved through the API (licence requires it,
    # the CDN blocks non-browser clients anyway) before anything else.
    if pixabay.is_pixabay(source):
        raw, hit = pixabay.fetch(source)
        meta = {"provider": "pixabay", **hit}
        traces.append({"step": "pixabay", **hit})
        source = raw

    # Passthrough recipes (no options) never touch the edge: QC the source
    # bytes as-is. "Meet the spec, change nothing."
    if not rec.options:
        raw = _as_bytes(source)
        traces.append({"step": "passthrough", "bytes": len(raw)})
        report = qc.check(raw, rec.qc)
        traces.append({"step": "qc", **report.as_dict()})
        return Normalized(data=raw, recipe=rec.name, source=given, url="",
                          report=report, options=rec.options, meta=meta,
                          traces=traces)

    source_url = stage.ensure_url(source, zone=zone)
    traces.append({"step": "stage", "url": source_url})
    work_url = source_url

    # Prelude — e.g. AI upscale on the opaque source, before segmentation.
    src_short = _short_side(source)
    if rec.prelude and src_short is not None and src_short < rec.prelude_below:
        pre = _transform(work_url, rec.prelude, zone, timeout, retries, traces, "prelude")
        work_url = stage.stage(pre, zone=zone)
        traces.append({"step": "prelude-staged", "url": work_url,
                       "short_side": src_short})

    data = _transform(work_url, rec.options, zone, timeout, retries, traces, "transform")

    report = qc.check(data, rec.qc)
    traces.append({"step": "qc", **report.as_dict()})

    return Normalized(data=data, recipe=rec.name, source=given,
                      url=cloudflare.build_url(work_url, rec.options, zone=zone),
                      source_url=source_url, report=report, options=rec.options,
                      meta=meta, traces=traces)


def _transform(url: str, options: tuple[str, ...], zone: str | None,
               timeout: float, retries: int, traces: list[dict], step: str) -> bytes:
    last: Exception | None = None
    for attempt in range(retries + 1):
        try:
            data = cloudflare.transform(url, options, zone=zone, timeout=timeout)
            traces.append({"step": step, "bytes": len(data), "options": list(options)})
            return data
        except TransformError as e:      # transient edge/origin hiccups
            last = e
            traces.append({"step": step, "attempt": attempt + 1, "error": str(e)})
    raise last  # type: ignore[misc]


__all__ = ["normalize", "Normalized", "RECIPES", "Recipe", "get", "TransformError",
           "cloudflare", "pixabay", "qc", "stage"]
