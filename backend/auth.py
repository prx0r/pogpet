"""Google sign-in, stdlib only — no pip, no SDK.

Two endpoints do the whole flow:
    GET /api/auth/google/start       -> 302 to Google
    GET /api/auth/google/callback    -> exchange code, find-or-create the
                                        account, redirect back with api_key

Config comes from .env (GOOGLE_CLIENT_ID / GOOGLE_CLIENT_SECRET / PUBLIC_BASE).
When those are empty the start endpoint says so instead of 500ing, so the
site still works while you're setting up credentials.
"""
from __future__ import annotations

import json
import secrets
import urllib.error
import urllib.parse
import urllib.request

from . import config

AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
INFO_URL = "https://openidconnect.googleapis.com/v1/userinfo"
SCOPE = "openid email profile"


def configured() -> bool:
    return bool(config.GOOGLE_CLIENT_ID and config.GOOGLE_CLIENT_SECRET)


def redirect_uri() -> str:
    return f"{config.PUBLIC_BASE.rstrip('/')}/api/auth/google/callback"


def make_state() -> str:
    return secrets.token_urlsafe(24)


def authorize_url(state: str) -> str:
    q = urllib.parse.urlencode({
        "client_id": config.GOOGLE_CLIENT_ID,
        "redirect_uri": redirect_uri(),
        "response_type": "code",
        "scope": SCOPE,
        "state": state,
        "access_type": "online",
        "prompt": "select_account",
    })
    return f"{AUTH_URL}?{q}"


def _post(url: str, data: dict) -> dict:
    body = urllib.parse.urlencode(data).encode()
    req = urllib.request.Request(url, data=body, method="POST")
    req.add_header("Content-Type", "application/x-www-form-urlencoded")
    # Cloudflare 1010s urllib's default UA.
    req.add_header("User-Agent", ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                                  "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"))
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")[:300]
        raise RuntimeError(f"google token endpoint {e.code}: {detail}") from None


def _get_json(url: str, token: str) -> dict:
    req = urllib.request.Request(url)
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("User-Agent", ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                                  "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"))
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")[:300]
        raise RuntimeError(f"google userinfo {e.code}: {detail}") from None


def exchange(code: str) -> dict:
    """code -> Google profile {sub, email, name, picture}."""
    tok = _post(TOKEN_URL, {
        "code": code,
        "client_id": config.GOOGLE_CLIENT_ID,
        "client_secret": config.GOOGLE_CLIENT_SECRET,
        "redirect_uri": redirect_uri(),
        "grant_type": "authorization_code",
    })
    if "access_token" not in tok:
        raise RuntimeError(f"no access_token: {json.dumps(tok)[:200]}")
    return _get_json(INFO_URL, tok["access_token"])


def handle_from(profile: dict) -> str:
    """Stable, url-safe handle derived from the Google account."""
    import re
    email = (profile.get("email") or "").split("@")[0].lower()
    raw = re.sub(r"[^a-z0-9._-]", "", email) or f"pog{str(profile.get('sub', ''))[-8:]}"
    return (raw[:24] or "pogger").strip("._-") or "pogger"
