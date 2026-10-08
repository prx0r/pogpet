"""50-customer auth: keyed tiers, agent grants, isolation, log hygiene.

Isolated temp-DB style: fake R2, real accounts/agents/keys.
"""
import io
import shutil
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from backend import cards, config, db, storage
from backend.server import app


@pytest.fixture()
def env():
    tmp = tempfile.TemporaryDirectory()
    root = Path(tmp.name)
    patches = [
        patch.object(config, "DATA", root),
        patch.object(config, "DB_PATH", root / "test.db"),
        patch.object(config, "LOCAL_TMP", root / "tmp"),
        patch.object(config, "LOCAL_MESH", root / "meshes"),
        patch.object(config, "UPLOAD_DIR", root / "uploads"),
    ]
    objects = root / "r2"

    def put(src, k):
        dest = objects / k
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, dest)
        return k

    def get(k, dest):
        src = objects / k
        if not src.exists():
            raise storage.StorageError("missing")
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, dest)
        return dest

    patches += [patch.object(storage, "put", side_effect=put),
                patch.object(storage, "get", side_effect=get)]
    for p in patches:
        p.start()
    db.init()
    cards.init()
    from backend import studio_library as sl
    with db.connect() as c:
        c.executescript(sl.SCHEMA)
        c.commit()
    client = app.test_client()
    yield {"client": client}
    for p in reversed(patches):
        p.stop()
    tmp.cleanup()


def _h(api_key=None):
    h = {"X-API-Token": config.API_TOKEN}
    if api_key:
        h["X-API-Key"] = api_key
    return h


def _signup(env, handle):
    r = env["client"].post("/api/accounts",
                           json={"handle": handle, "password": "test-pass-123"},
                           headers=_h())
    assert r.status_code == 200, r.get_data(as_text=True)[:200]
    body = r.get_json()
    assert body["api_key"] and len(body["api_key"]) > 20
    return body["handle"], body["api_key"]


def _mint(env, user_key, name, perms):
    r = env["client"].post("/api/agents", json={"name": name, "permissions": perms},
                           headers=_h(user_key))
    assert r.status_code == 200, r.get_data(as_text=True)[:200]
    body = r.get_json()
    akey = (body.get("agent") or {}).get("agent_api_key", "")
    assert akey and akey.startswith("fagg_")
    return body["agent"], akey


def test_user_key_full_owner_access(env):
    handle, ukey = _signup(env, "custone")
    c = env["client"]
    assert c.get("/api/cards/gallery", query_string={"owner": handle},
                 headers=_h(ukey)).status_code == 200
    r = c.post("/api/cards/designs",
               json={"owner": handle, "spec": {
                   "template": "typography", "format": "5x7", "photos": [],
                   "headline": "Hi", "recipient": "", "sender": "Me",
                   "inside_message": "x"}}, headers=_h(ukey))
    assert r.status_code == 200, r.get_data(as_text=True)[:200]
    assert c.get("/api/cards/shelf", query_string={"owner": handle},
                 headers=_h(ukey)).status_code == 200


def test_agent_act_as_parent_with_grants(env):
    handle, ukey = _signup(env, "custtwo")
    c = env["client"]
    ag, akey = _mint(env, ukey, "chatgpt", ["cards:read", "cards:create"])
    # reads + creates pass as parent
    assert c.get("/api/cards/gallery", query_string={"owner": handle},
                 headers=_h(akey)).status_code == 200
    r = c.post("/api/cards/designs",
               json={"owner": handle, "spec": {
                   "template": "typography", "format": "5x7", "photos": [],
                   "headline": "Hi", "recipient": "", "sender": "Me",
                   "inside_message": "x"}}, headers=_h(akey))
    assert r.status_code == 200, r.get_data(as_text=True)[:200]
    # money without the grant → 403
    did = r.get_json()["design"]["id"]
    assert c.post(f"/api/cards/{did}/order",
                  json={"owner": handle, "revision": 1, "qty": 1,
                        "idempotency_key": "agent-order-12345678"},
                  headers=_h(akey)).status_code == 403


def test_agent_read_only_cannot_create(env):
    handle, ukey = _signup(env, "custthree")
    c = env["client"]
    ag, akey = _mint(env, ukey, "reader", ["cards:read"])
    assert c.get("/api/cards/gallery", query_string={"owner": handle},
                 headers=_h(akey)).status_code == 200
    r = c.post("/api/cards/designs",
               json={"owner": handle, "spec": {
                   "template": "typography", "format": "5x7", "photos": [],
                   "headline": "Hi", "recipient": "", "sender": "Me",
                   "inside_message": "x"}}, headers=_h(akey))
    assert r.status_code == 403


def test_agent_isolation_and_revoke(env):
    handle_a, ukey_a = _signup(env, "custfoura")
    handle_b, _ukey_b = _signup(env, "custfourb")
    c = env["client"]
    ag, akey = _mint(env, ukey_a, "chatgpt", ["cards:read", "cards:create"])
    # foreign owner → 403
    assert c.get("/api/cards/gallery", query_string={"owner": handle_b},
                 headers=_h(akey)).status_code == 403
    # revoke → denied everywhere
    r = c.post(f"/api/agents/{ag['id']}/revoke", json={}, headers=_h(ukey_a))
    assert r.status_code == 200
    assert c.get("/api/cards/gallery", query_string={"owner": handle_a},
                 headers=_h(akey)).status_code in (401, 403)


def test_anon_unchanged_without_key(env):
    # operator channel, no user key: anon gallery behaves as before
    c = env["client"]
    assert c.get("/api/cards/gallery", query_string={"owner": "anon"},
                 headers=_h()).status_code == 200


def test_log_scrub_redacts_secrets():
    from backend import logscrub as L
    line = ('POST /mcp?token=SECRET123 200 OK; '
            '"GET /api/cards/shelf?owner=anon&api_key=ABCDEF&owner_sig=S3CR3T HTTP/1.1" 200; '
            "return_to=/x?auth=AUTH9 done")
    out = L.scrub(line)
    assert "SECRET123" not in out and "S3CR3T" not in out and "AUTH9" not in out
    assert "token=REDACTED" in out and "owner_sig=REDACTED" in out
    assert L.scrub("GET /health 200") == "GET /health 200"
    import logging
    rec = logging.LogRecord("uvicorn.access", logging.INFO, __file__, 1,
                            '%s - "POST %s HTTP/1.1" %s',
                            ("127.0.0.1", "/mcp?api_key=ABCDEF", 200), None)
    assert L._ScrubFilter().filter(rec) is True
    assert "ABCDEF" not in rec.getMessage()
    assert "api_key=REDACTED" in rec.getMessage()
    L.install("test-logscrub-witness")
    import logging
    assert any(isinstance(f, L._ScrubFilter)
               for f in logging.getLogger("test-logscrub-witness").filters)


def test_bridge_keyed_callers_reach_full_tier():
    import bridge.llm_bridge as B
    H = B.Handler

    def fake(path="", headers=None):
        return SimpleNamespace(path=path, headers=headers or {})

    assert H._user_keyed(fake("/mcp", {"X-API-Key": "fagg_x"})) is True
    assert H._user_keyed(fake("/mcp?api_key=fagg_x", {})) is True
    assert H._user_keyed(fake("/mcp", {"Authorization": "Bearer abc"})) is True
    assert H._user_keyed(fake("/mcp", {})) is False
