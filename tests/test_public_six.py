"""The six public tools: intent in, finished products out."""
import asyncio
import base64
import io
import json
import shutil
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
from PIL import Image, ImageDraw

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
    owner = "six_owner"
    headers = {"X-API-Token": config.API_TOKEN,
               "X-Owner-Sig": config.sign_owner(owner)}
    yield {"client": client, "owner": owner, "headers": headers}
    for p in reversed(patches):
        p.stop()
    tmp.cleanup()


_SEQ = [100]


def _upload(env, tag="six"):
    _SEQ[0] += 1
    n = _SEQ[0]
    img = Image.new("RGB", (800, 1000), "#f4e8cd")
    d = ImageDraw.Draw(img)
    d.rectangle((70 + n * 3, 150, 730, 850), fill=(50 + n * 2, 80, 110))
    d.ellipse((260, 190, 540, 470), fill="#dfb295")
    d.text((10, 10), f"{tag}-{n}", fill=(10, 10, 10))
    b = io.BytesIO()
    img.save(b, "JPEG")
    b.seek(0)
    r = env["client"].post("/api/photos",
                           data={"owner": env["owner"], "photo": (b, f"six-{n}.jpg")},
                           headers=env["headers"])
    assert r.status_code == 200, r.get_data(as_text=True)[:200]
    return r.get_json()["photo"]["id"]


def _dad(env, nphotos=4):
    from backend import subjects as sub
    pids = [_upload(env) for _ in range(nphotos)]
    with db.connect() as conn:
        s = sub.create_subject(conn, env["owner"], "Dad")
        sub.set_profile(conn, env["owner"], s["id"], relationship="father",
                        profile={"name": "Dad", "relationship": "father",
                                 "interests": ["golf"]})
        for pid in pids:
            sub.link_photo(conn, pid, s["id"], confirmed=True)
        conn.commit()
    return s, pids


def _people_fake(s):
    async def fake_call(method, path, body=None, api_key="", owner_sig=""):
        if path.startswith("/api/oddhobb/people"):
            return {"ok": True, "people": [
                {"subject": {"id": s["id"], "name": "Dad", "relationship": "father"},
                 "profile": {"profile": {"name": "Dad", "relationship": "father",
                                         "interests": ["golf"]}}}]}
        raise AssertionError(f"unexpected call {method} {path}")
    return fake_call


def test_make_needs_photos_not_errors(env, monkeypatch):
    import json as _json
    from backend import mcp_server as M
    from backend import subjects as sub
    with db.connect() as conn:
        s = sub.create_subject(conn, env["owner"], "Dad")
        conn.commit()
    monkeypatch.setattr(M, "_call", _people_fake({"id": s["id"]}))

    async def fake_bundle(*a, **k):
        raise AssertionError("no renders on needs_input")
    monkeypatch.setattr(M, "_card_spread_bundle", fake_bundle)

    out = asyncio.run(M.oddhobb_make(
        subject_id=s["id"], request="birthday, golf, dry funny", count=4,
        owner=env["owner"]))
    body = _json.loads(out[0].text)
    assert body["ok"] is True and body["status"] == "needs_input", body
    assert body["requires_action"]["type"] == "add_media"
    assert body["requires_action"]["subject_id"] == s["id"]


def test_make_returns_finished_options(env, monkeypatch):
    import json as _json
    from backend import mcp_server as M
    s, _pids = _dad(env)
    monkeypatch.setattr(M, "_call", _people_fake(s))

    async def fake_bundle(design_id, revision, owner, api_key="", owner_sig="", timeout_s=90):
        base = f"https://oddhobb.com/backend/api/cards/{design_id}/r{revision}"
        return {"ok": True,
                "views": {"front": base + "/preview", "inside": base + "/inside",
                          "back": base + "/back"},
                "views_abs": {"front": base + "/preview", "inside": base + "/inside",
                              "back": base + "/back"},
                "proof_url": f"https://oddhobb.com/proof/{design_id}"}
    monkeypatch.setattr(M, "_card_spread_bundle", fake_bundle)

    out = asyncio.run(M.oddhobb_make(
        subject_id=s["id"], request="birthday golf dry funny", count=2,
        owner=env["owner"]))
    body = _json.loads(out[0].text)
    assert body["ok"] is True and body["status"] == "ready", body
    assert len(body["options"]) == 2
    for opt in body["options"]:
        assert set(opt["views"]) == {"front", "inside", "back"}, opt
        assert opt["price_cents"] == 799 and opt["proof_url"]
    assert body["price"] == {"amount_cents": 799, "currency": "GBP"}
    assert body["next_actions"] == ["change", "buy"]


def test_change_rewrites_copy(env, monkeypatch):
    import json as _json
    from backend import mcp_server as M
    from backend.recipes import compiler as C
    s, _pids = _dad(env)
    base = C.compile(env["owner"], "birthday_four_photos_party_title_v1",
                     subject={"id": s["id"], "name": "Dad",
                              "relationship": "father",
                              "interests": ["golf"], "memories": []},
                     occasion="birthday", tone="funny", message_hint="",
                     signature="Love, Pete")
    assert base["ok"], base
    did = base["design"]["id"]

    async def fake_call(method, path, body=None, api_key="", owner_sig=""):
        if path.startswith("/api/cards/designs/"):
            rec = cards.record(env["owner"], did, None)
            return {"ok": True, "design": {"id": did,
                                           "revision": rec["revision"],
                                           "spec": rec["spec"]}}
        if path == "/api/cards/designs":
            saved = cards.validate(env["owner"], (body or {}).get("spec", {}))
            import time as _t
            import uuid as _u
            with db.connect() as conn:
                conn.execute("BEGIN IMMEDIATE")
                cur = conn.execute("SELECT latest FROM card_designs WHERE id=?",
                                   (body["id"],)).fetchone()
                rev = int(cur["latest"]) + 1
                conn.execute("INSERT INTO card_revisions VALUES (?,?,?,?)",
                             (body["id"], rev, cards.json_dump(saved), _t.time()))
                conn.execute("UPDATE card_designs SET latest=?,updated_at=? WHERE id=?",
                             (rev, _t.time(), body["id"]))
                conn.commit()
            return {"ok": True, "design": {"id": body["id"], "revision": rev},
                    "proof_url": f"https://oddhobb.com/proof/{body['id']}"}
        raise AssertionError(f"unexpected call {method} {path}")
    monkeypatch.setattr(M, "_call", fake_call)

    async def fake_bundle(design_id, revision, owner, api_key="", owner_sig="", timeout_s=90):
        base = f"https://x/{design_id}/r{revision}"
        return {"ok": True,
                "views": {"front": base, "inside": base, "back": base},
                "views_abs": {"front": base, "inside": base, "back": base}}
    monkeypatch.setattr(M, "_card_spread_bundle", fake_bundle)

    out = asyncio.run(M.oddhobb_change(
        design_id=did, instruction="make it drier, more golf", owner=env["owner"]))
    body = _json.loads(out[0].text)
    assert body["ok"] is True and body["status"] == "ready", body
    assert body["revision"] == 2
    assert "inside copy" in body["changed"], body


def test_add_media_tags_photo(env, monkeypatch):
    import json as _json
    from backend import mcp_server as M
    from backend import subjects as sub
    with db.connect() as conn:
        s = sub.create_subject(conn, env["owner"], "Dad")
        conn.commit()

    async def fake_call(method, path, body=None, api_key="", owner_sig=""):
        if path.startswith("/api/oddhobb/people"):
            return {"ok": True, "people": [
                {"subject": {"id": s["id"], "name": "Dad", "relationship": "father"},
                 "profile": {"profile": {}}}]}
        raise AssertionError(f"unexpected call {method} {path}")
    monkeypatch.setattr(M, "_call", fake_call)

    img = Image.new("RGB", (400, 500), (80, 120, 160))
    buf = io.BytesIO()
    img.save(buf, "PNG")
    durl = "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()
    out = asyncio.run(M.oddhobb_add_media(
        subject_id=s["id"], photo_url=durl, owner=env["owner"]))
    body = _json.loads(out[0].text)
    assert body["ok"] is True and body["status"] == "ready", body
    pid = body["photo_id"]
    with db.connect() as conn:
        row = conn.execute("SELECT owner FROM photos WHERE id=?", (pid,)).fetchone()
        assert row and row["owner"] == env["owner"]
        link = conn.execute(
            "SELECT confirmed FROM photo_subjects WHERE photo_id=? AND subject_id=?",
            (pid, s["id"])).fetchone()
        assert link and link["confirmed"] == 1


def test_buy_means_checkout_and_needs_signer(env, monkeypatch):
    import json as _json
    from backend import mcp_server as M
    from backend.recipes import compiler as C
    s, _pids = _dad(env)
    base = C.compile(env["owner"], "birthday_four_photos_party_title_v1",
                     subject={"id": s["id"], "name": "Dad",
                              "relationship": "father",
                              "interests": ["golf"], "memories": []},
                     occasion="birthday", tone="funny", message_hint="",
                     signature="")
    assert base["ok"], base
    did = base["design"]["id"]

    async def fake_call(method, path, body=None, api_key="", owner_sig=""):
        if path.startswith("/api/cards/designs/"):
            look = path.split("/api/cards/designs/")[1].split("?")[0]
            rec = cards.record(env["owner"], look, None)
            return {"ok": True, "design": {"id": look,
                                           "revision": rec["revision"],
                                           "spec": rec["spec"]}}
        if path.endswith("/checkout"):
            return {"ok": True, "checkout_url": "https://checkout/x",
                    "product_url": "https://oddhobb.com/cards/x",
                    "product": {"price_cents": 799, "name": "Personalised 5×7 Greeting Card"},
                    "order": {"price_cents": 799}}
        raise AssertionError(f"unexpected call {method} {path}")
    monkeypatch.setattr(M, "_call", fake_call)

    need = asyncio.run(M.oddhobb_buy(design_id=did, owner=env["owner"]))
    needb = json.loads(need[0].text)
    assert needb["status"] == "needs_input"
    assert needb["requires_action"]["type"] == "signature"
    # signed design buys
    signed = C.compile(env["owner"], "birthday_four_photos_party_title_v1",
                       subject={"id": s["id"], "name": "Dad",
                                "relationship": "father",
                                "interests": ["golf"], "memories": []},
                       occasion="birthday", tone="funny", message_hint="",
                       signature="Love, Pete")
    got = asyncio.run(M.oddhobb_buy(
        design_id=signed["design"]["id"], owner=env["owner"]))
    gotb = json.loads(got[0].text)
    assert gotb["status"] == "checkout_ready", gotb
    assert gotb["checkout_url"] == "https://checkout/x"
    assert gotb["price"] == {"amount_cents": 799, "currency": "GBP"}
