"""Card service contract: the acceptance flow + typed errors + frozen revisions.

Acceptance: create -> joke pick -> punchline refine -> render views ->
checkout pins the frozen revision. Later edits never touch the paid artwork.
"""
import shutil
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from backend import card_service as S, cards, config, db, storage
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
    yield {"owner": "svc_owner"}
    for p in reversed(patches):
        p.stop()
    tmp.cleanup()


def test_acceptance_typography_flow(env):
    o = env["owner"]
    d = S.create(o, "typography")
    assert d["revision"] == 1
    # headline refine -> rev 2, inside -> rev 3; rev 1 spec untouched
    r2 = S.set_slot(o, d["id"], "headline", "DAD'S MIDLIFE CRISIS")
    assert r2["revision"] == 2 and r2["supersedes"] == 1
    r3 = S.set_slot(o, d["id"], "inside_message", "Still fast. Still handsome. Still can't park.")
    assert r3["revision"] == 3
    rev1 = cards.record(o, d["id"], 1)["spec"]
    assert rev1["headline"] != "DAD'S MIDLIFE CRISIS"
    v = S.render(o, d["id"], 3)
    assert set(v["views"]) == {"front", "inside", "back"}
    ready = S.checkout_ready(o, d["id"], 3)
    assert ready["frozen"] is True
    # stale revision is not checkoutable
    with pytest.raises(S.ServiceError) as e:
        S.checkout_ready(o, d["id"], 1)
    assert e.value.code == "CHECKOUT_NOT_READY"


def test_joke_shelf_is_template_data(env):
    jokes = S.cardgen_jokes("solo_magazine_cover_v1")
    assert len(jokes) >= 1 and all("joke_id" in j for j in jokes)
    with pytest.raises(S.ServiceError) as e:
        S.cardgen_jokes("no_such_template")
    assert e.value.code == "NEEDS_PHOTO"


def test_typed_errors(env):
    o = env["owner"]
    d = S.create(o, "typography")
    with pytest.raises(S.ServiceError) as e:
        S.set_slot(o, d["id"], "headline", "x" * 61)
    assert e.value.code == "TEXT_TOO_LONG"
    with pytest.raises(S.ServiceError) as e:
        S.set_slot(o, d["id"], "joke_id", "made-up-joke")
    assert e.value.code == "TEXT_TOO_LONG"
    with pytest.raises(S.ServiceError) as e:
        S.set_slot(o, d["id"], "photo", "whatever")
    assert e.value.code == "NEEDS_PHOTO"
    with pytest.raises(S.ServiceError) as e:
        S.create(o, "no_such_template")
    assert e.value.code == "NEEDS_PHOTO"
    with pytest.raises(S.ServiceError) as e:
        S.render(o, "card_missing", 1)
    assert e.value.code == "RENDER_QA_FAILED"
    with pytest.raises(S.ServiceError) as e:
        S.get_order(o, "ord_missing")
    assert e.value.code == "CHECKOUT_NOT_READY"


def test_lettering_cache_key_and_modes(env):
    k1 = S.lettering_key("HI DAD", "type", "1", "fraunces", "1", (1563, 400), 300)
    k2 = S.lettering_key("HI DAD", "type", "1", "fraunces", "1", (1563, 400), 300)
    k3 = S.lettering_key("HI DAD", "type", "1", "inter", "1", (1563, 400), 300)
    assert k1 == k2 and k1 != k3  # typography change busts the cache
    p1 = S.lettering_plate("HI DAD")
    p2 = S.lettering_plate("HI DAD")
    assert p1["key"] == p2["key"] and p2["cached"] is True
    with pytest.raises(S.ServiceError) as e:
        S.lettering_plate("HI DAD", style_id="ai")
    assert e.value.code == "RENDER_QA_FAILED"


def test_slots_and_styles(env):
    s = S.get_slots("typography")
    assert s["text"]["headline"]["max"] == 60
    g = S.get_slots("solo_magazine_cover_v1")
    assert g["kind"] == "cardgen" and len(g["jokes"]) >= 1
    st = S.list_styles()
    assert st["modes"] == ["type", "styled"]
    assert st["ai"]["available"] is False
    assert len(S.list_templates()) >= 8
