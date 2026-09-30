"""Pixabay — resolve a page URL (or bare id) to image bytes, legally.

We hold a Pixabay API key, and Pixabay's licence requires fetching images
through the API rather than scraping the CDN, so every Pixabay source goes
through here: page URL -> image id -> API lookup -> download via the signed
`largeImageURL` with a referer. The API also hands back the licence flags
(`noAiTraining`, `isAiGenerated`, `isGRated`) which we surface so a demo
image's provenance can be checked later.
"""
from __future__ import annotations

import json
import re
import urllib.error
import urllib.request

from .cloudflare import _env

API = "https://pixabay.com/api/"
# .../photos/some-slug-2706681/  ·  ?id=2706681  ·  bare "2706681"
_ID_RE = re.compile(
    r"pixabay\.com/photos/[a-z0-9\-]*?-(\d+)/?(?:\?.*)?$"   # page URL
    r"|[?&]id=(\d+)"                                          # api-style
    r"|^(\d+)$"                                               # bare id
)


class PixabayError(Exception):
    pass


def parse_id(source: str) -> str:
    m = _ID_RE.search(source.strip())
    if not m:
        raise PixabayError(f"not a Pixabay photo URL or id: {source[:90]!r}")
    return next(g for g in m.groups() if g)


def lookup(source: str, key: str | None = None) -> dict:
    """API lookup for one photo id. Returns the hit (licence flags included)."""
    key = key or _env("PIXABAY_API_KEY")
    if not key:
        raise PixabayError("no PIXABAY_API_KEY — set it in .env to fetch Pixabay sources")
    pid = parse_id(source)
    url = f"{API}?key={key}&id={pid}"
    try:
        with urllib.request.urlopen(urllib.request.Request(
                url, headers={"User-Agent": "premesh/1.0"}), timeout=30) as r:
            payload = json.loads(r.read().decode() or "{}")
    except urllib.error.HTTPError as e:
        raise PixabayError(f"pixabay API HTTP {e.code}") from None
    hits = payload.get("hits") or []
    if not hits:
        raise PixabayError(f"pixabay has no photo with id {pid}")
    return hits[0]


def fetch(source: str, key: str | None = None) -> tuple[bytes, dict]:
    """Download the photo. Returns (bytes, hit-metadata) — metadata carries
    the licence flags, tags and dimensions for provenance."""
    hit = lookup(source, key=key)
    img_url = hit.get("largeImageURL") or hit.get("webformatURL")
    if not img_url:
        raise PixabayError(f"pixabay returned no image URL for id {hit.get('id')}")
    req = urllib.request.Request(img_url, headers={
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) premesh/1.0",
        "Referer": "https://pixabay.com/",
    })
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            data = r.read()
    except urllib.error.HTTPError as e:
        raise PixabayError(f"download failed: HTTP {e.code}") from None
    meta = {k: hit.get(k) for k in
            ("id", "tags", "imageWidth", "imageHeight", "user",
             "noAiTraining", "isAiGenerated", "isGRated", "pageURL")}
    meta["bytes"] = len(data)
    return data, meta


def is_pixabay(source) -> bool:
    return isinstance(source, str) and (
        "pixabay.com/" in source or source.strip().isdigit())
