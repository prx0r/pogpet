"""Cloudflare Images — build the transformation URL and fetch the result.

The URL interface needs no API token: transformations are served from the
zone, and the zone has the feature enabled (`/zones/{id}/settings/transformations`
= on). By default Cloudflare only pulls sources from the same zone, which is
why every local file has to be staged onto the zone first (see stage.py).
"""
from __future__ import annotations

import os
import urllib.error
import urllib.request
from pathlib import Path

PREFIX = "/cdn-cgi/image/"


class TransformError(Exception):
    """Cloudflare refused or failed the transformation."""

    def __init__(self, message: str, status: int | None = None, body: bytes = b""):
        super().__init__(message)
        self.status = status
        self.body = body[:400]


def _env(name: str) -> str:
    """Env var, falling back to the repo .env so the CLI works out of the box.

    Deliberately dependency-free (no python-dotenv): read-only, first match
    wins, and real environment variables always take precedence.
    """
    val = os.environ.get(name, "")
    if val:
        return val
    env_file = Path(__file__).resolve().parent.parent / ".env"
    try:
        for line in env_file.read_text().splitlines():
            line = line.strip()
            if line.startswith(f"{name}="):
                return line.split("=", 1)[1].strip().strip("'\"")
    except OSError:
        pass
    return ""


def zone_base(zone: str | None = None) -> str:
    """Base URL of the zone that serves transformations."""
    base = (zone or _env("PUBLIC_BASE")).rstrip("/")
    if not base:
        raise TransformError(
            "no zone — set PUBLIC_BASE (e.g. https://pog.pet) or pass zone="
        )
    if not base.startswith("http"):
        base = "https://" + base
    return base


def build_url(source_url: str, options: tuple[str, ...] | list[str],
              zone: str | None = None) -> str:
    if not source_url.startswith("http"):
        raise TransformError(f"source must be an absolute http(s) URL: {source_url!r}")
    if not options:
        raise TransformError("a recipe must send at least one option")
    return f"{zone_base(zone)}{PREFIX}{','.join(options)}/{source_url}"


def fetch(url: str, timeout: float = 90.0) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "premesh/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read()
    except urllib.error.HTTPError as e:
        body = e.read() if hasattr(e, "read") else b""
        hint = ""
        if e.code == 404:
            hint = (" (404: transformations disabled on the zone, or the source "
                    "URL is not reachable from it)")
        elif e.code == 9422:
            hint = " (9422: free-plan transformation quota exhausted this month)"
        raise TransformError(f"HTTP {e.code} from Cloudflare{hint}",
                             status=e.code, body=body) from None
    except urllib.error.URLError as e:
        raise TransformError(f"network error talking to the zone: {e.reason}") from None


def transform(source_url: str, options: tuple[str, ...] | list[str],
              zone: str | None = None, timeout: float = 90.0) -> bytes:
    return fetch(build_url(source_url, options, zone=zone), timeout=timeout)
