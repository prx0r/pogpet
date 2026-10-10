"""Canonical path: recipes registry, matcher, compiler, six tools."""
import io
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
    owner = "rec_owner"
    headers = {"X-API-Token": config.API_TOKEN,
               "X-Owner-Sig": config.sign_owner(owner)}
    yield {"client": client, "owner": owner, "headers": headers}
    for p in reversed(patches):
        p.stop()
    tmp.cleanup()


_SEQ = [0]


def _upload(env, tag):
    _SEQ[0] += 1
    n = _SEQ[0]
    img = Image.new("RGB", (800, 1000), "#f4e8cd")
    d = ImageDraw.Draw(img)
    d.rectangle((70 + n * 7, 150, 730, 850), fill=(50 + n * 6, 80, 110))
    d.ellipse((260, 190, 540, 470), fill="#dfb295")
    d.text((10, 10), f"{tag}-{n}", fill=(10, 10, 10))
    b = io.BytesIO()
    img.save(b, "JPEG")
    b.seek(0)
    r = env["client"].post("/api/photos",
                           data={"owner": env["owner"], "photo": (b, f"rec-{n}.jpg")},
                           headers=env["headers"])
    assert r.status_code == 200, r.get_data(as_text=True)[:200]
    return r.get_json()["photo"]["id"]


def _dad(env, nphotos=4):
    from backend import subjects as sub
    pids = [_upload(env, "dad") for _ in range(nphotos)]
    with db.connect() as conn:
        s = sub.create_subject(conn, env["owner"], "Dad")
        sub.set_profile(conn, env["owner"], s["id"], relationship="father",
                        profile={"name": "Dad", "relationship": "father",
                                 "interests": ["golf"]})
        for pid in pids:
            sub.link_photo(conn, pid, s["id"], confirmed=True)
        conn.commit()
    return s, pids


def test_registry_loads_first_published_recipe():
    from backend.recipes import registry as R
    from backend.recipes import schemas as S
    reg = R.published()
    assert "birthday_four_photos_party_title_v1" in reg
    r = reg["birthday_four_photos_party_title_v1"]
    assert r["product"]["price_cents"] == 299
    assert r["renderer"]["template"] == "birthday_4photo"
    assert S.validate_recipe({"id": "x"}) != []


def test_matcher_eligibility_and_ranking():
    from backend.recipes import matcher as M
    from backend.recipes import registry as R
    reg = R.published()
    rid = "birthday_four_photos_party_title_v1"
    brief = {"occasion": "birthday", "subject_kind": "person",
             "photo_count": 4,
             "recipient": {"relationship": "father", "interests": ["golf"]},
             "vibe": "dry funny"}
    assert M.eligible(reg[rid], brief) == []
    assert M.eligible(reg[rid], {**brief, "occasion": "halloween"}) != []
    assert M.eligible(reg[rid], {**brief, "photo_count": 1}) != []
    ranked = M.match(brief, reg)
    assert ranked and ranked[0]["id"] == rid
    assert any("golf" in r or "father" in r or "dad" in r
               for r in ranked[0]["reasons"])


def test_compiler_compiles_finished_product(env):
    from backend.recipes import compiler as C
    from backend import subjects as sub
    s, _pids = _dad(env)
    with db.connect() as conn:
        prof = sub.profile_for(conn, env["owner"], s["id"])
    p = prof.get("profile", {})
    subject = {"id": s["id"], "name": p.get("name", "Dad"),
               "relationship": p.get("relationship", "father"),
               "interests": p.get("interests", []), "memories": []}
    out = C.compile(env["owner"], "birthday_four_photos_party_title_v1",
                    subject=subject, occasion="birthday", tone="funny",
                    message_hint="", signature="Love, Pete")
    assert out["ok"], out
    assert out["design"]["spec"]["template"] == "birthday_4photo"
    assert out["design"]["spec"]["recipe_id"] == "birthday_four_photos_party_title_v1"
    assert out["proof_url"].endswith("/proof/" + out["design"]["id"])
    assert out["copy_source"] in ("caller-hint", "server-llm", "template-fallback")


def test_compiler_refuses_without_signature_or_photos(env):
    from backend.recipes import compiler as C
    s, _pids = _dad(env, nphotos=1)
    from backend import subjects as sub
    with db.connect() as conn:
        prof = sub.profile_for(conn, env["owner"], s["id"])
    p = prof.get("profile", {})
    subject = {"id": s["id"], "name": "Dad", "relationship": "father",
               "interests": [], "memories": []}
    unsigned = C.compile(env["owner"], "birthday_four_photos_party_title_v1",
                         subject=subject, signature="")
    assert unsigned["ok"] is False and "need 4 photos" in unsigned["error"]
    s4, _p4 = _dad(env, nphotos=4)
    with db.connect() as conn:
        prof4 = sub.profile_for(conn, env["owner"], s4["id"])
    p4 = prof4.get("profile", {})
    subject4 = {"id": s4["id"], "name": p4.get("name", "Dad"),
                "relationship": p4.get("relationship", "father"),
                "interests": p4.get("interests", []), "memories": []}
    free = C.compile(env["owner"], "birthday_four_photos_party_title_v1",
                     subject=subject4, signature="")
    assert free["ok"] is True
    assert any("unsigned" in w for w in free.get("warnings", [])), free
    bad3 = C.compile(env["owner"], "nope_v1", subject=subject4,
                     signature="Love, Pete")
    assert bad3["ok"] is False


def test_recommend_unsigned_and_make_flow(monkeypatch, env):
    import asyncio
    import json
    from backend import mcp_server as M
    s, _pids = _dad(env)

    async def fake_call(method, path, body=None, api_key="", owner_sig=""):
        if path.startswith("/api/oddhobb/people"):
            return {"ok": True, "people": [
                {"subject": {"id": s["id"], "name": "Dad", "relationship": "father"},
                 "profile": {"profile": {"name": "Dad", "relationship": "father",
                                          "interests": ["golf"]}}}]}
        raise AssertionError(f"unexpected call {method} {path}")
    monkeypatch.setattr(M, "_call", fake_call)

    rec = asyncio.run(M.oddhobb_recommend(
        person="Dad", occasion="birthday", vibe="dry funny",
        owner=env["owner"]))
    body = json.loads(rec[0].text)
    assert body["ok"] and body["ideas"], body
    assert body["ideas"][0]["preview_status"] == "needs-signature"
    assert body["ideas"][0]["recipe"] == "birthday_four_photos_party_title_v1"

    rec2 = asyncio.run(M.oddhobb_recommend(
        person="Dad", occasion="birthday", vibe="dry funny",
        signature="Love, Pete", owner=env["owner"]))
    body2 = json.loads(rec2[0].text)
    assert body2["ok"] and body2["ideas"], body2
    first = body2["ideas"][0]
    assert first["preview_status"] == "ready", first
    assert first["proof_url"].endswith("/proof/" + first["design_id"])
    return first


def test_variants_and_get(monkeypatch, env):
    import asyncio
    import json
    from backend import mcp_server as M
    s, _pids = _dad(env)

    async def fake_call(method, path, body=None, api_key="", owner_sig=""):
        if path.startswith("/api/oddhobb/people"):
            return {"ok": True, "people": [
                {"subject": {"id": s["id"], "name": "Dad", "relationship": "father"},
                 "profile": {"profile": {"name": "Dad", "relationship": "father",
                                          "interests": ["golf"]}}}]}
        if path.startswith("/api/cards/designs/"):
            did = path.split("/api/cards/designs/")[1].split("?")[0]
            with db.connect() as conn:
                row = conn.execute(
                    "SELECT id,latest FROM card_designs WHERE id=?", (did,)).fetchone()
                assert row is not None
                from backend import cards as _C
                rec = _C.record(env["owner"], did, row["latest"])
            return {"ok": True, "design": {"id": did, "revision": rec["revision"],
                                           "spec": rec["spec"]}}
        if path.startswith("/api/cards/") and "/scene" in path.split("?")[0]:
            did = path.split("/api/cards/")[1].split("/scene")[0]
            with db.connect() as conn:
                row = conn.execute(
                    "SELECT latest FROM card_designs WHERE id=?", (did,)).fetchone()
            rev = row["latest"]
            base = f"/api/cards/{did}/r{rev}"
            return {"ok": True, "proof_url": f"https://oddhobb.com/proof/{did}",
                    "scene": {"id": did, "revision": rev,
                              "outputs": {"preview": {"status": "ready"}}}}
        raise AssertionError(f"unexpected call {method} {path}")
    monkeypatch.setattr(M, "_call", fake_call)

    v = asyncio.run(M.oddhobb_variants(
        idea_id="idea_birthday_four_photos_party_title_v1",
        vibe="dry understated", signature="Love, Pete", n=2, owner=env["owner"]))
    vb = json.loads(v[0].text)
    assert vb["ok"] and len(vb["variants"]) == 2, vb
    assert vb["variants"][0]["design_id"] != vb["variants"][1]["design_id"]

    g = asyncio.run(M.oddhobb_get(
        vb["variants"][0]["design_id"], owner=env["owner"]))
    gb = json.loads(g[0].text)
    assert gb["ok"] and "triptych" in gb["artifacts"], gb


def test_canonical_six_tiers():
    from backend import mcp_server as M
    names = [fn.__name__ for fns in M.TOOL_AREAS.values() for fn in fns]
    for t in ("oddhobb_people", "oddhobb_recommend", "oddhobb_make",
              "oddhobb_variants", "oddhobb_get", "oddhobb_checkout_card"):
        assert t in names, t
    # get displays (public); compiling tools need the caller's key.
    # oddhobb_make is the public sixth tool (unsigned previews allowed).
    assert "oddhobb_get" in M.PUBLIC_TOOLS
    assert "oddhobb_make" in M.PUBLIC_TOOLS
    for t in ("oddhobb_recommend", "oddhobb_variants"):
        assert t not in M.PUBLIC_TOOLS, t


def test_gallery_compiles_shelf_from_recipes(env):
    s, _pids = _dad(env)
    r = env["client"].get("/api/cards/gallery?owner=" + env["owner"],
                          headers=env["headers"])
    assert r.status_code == 200, r.json
    d = r.json
    assert d["need_photos"] == 0
    assert len(d["items"]) >= 5, [it.get("template") for it in d["items"]]
    templates = {it["template"] for it in d["items"]}
    assert len(templates) >= 4, templates  # distinct layouts, not one product
    for it in d["items"]:
        assert it["price_cents"] == 299
        assert it["design_id"].startswith("card_")
        assert it["headline"]
        assert it["recipient"] == "Dad"
        assert len(it["photos"]) >= 1


def test_gallery_single_photo_unlocks_shelf(env):
    s, _pids = _dad(env, nphotos=1)
    r = env["client"].get("/api/cards/gallery?owner=" + env["owner"],
                          headers=env["headers"])
    assert r.status_code == 200, r.json
    d = r.json
    assert d["need_photos"] == 0
    assert len(d["items"]) >= 3, [it.get("template") for it in d["items"]]
