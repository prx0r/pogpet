"""Vision loop: active-person gallery, re-roll, shelf of finished cards.

Isolated temp-DB style (mirrors test_cards.CardsJourney): fake R2, signed
owner headers, no live state touched.
"""
import io
import shutil
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
from PIL import Image

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
    owner = "vis_loop"
    client = app.test_client()
    headers = {"X-API-Token": config.API_TOKEN,
               "X-Owner-Sig": config.sign_owner(owner)}
    yield {"client": client, "owner": owner, "headers": headers}
    for p in reversed(patches):
        p.stop()
    tmp.cleanup()


def _upload(env, n):
    from PIL import ImageDraw
    img = Image.new("RGB", (800, 1000), "#f4e8cd")
    d = ImageDraw.Draw(img)
    d.rectangle((70 + n * 12, 150, 730, 850), fill=(50 + n * 10, 80, 110))
    d.ellipse((260, 190, 540, 470), fill="#dfb295")
    d.text((10, 10), f"vis-{n}", fill=(10, 10, 10))
    b = io.BytesIO()
    img.save(b, "JPEG")
    b.seek(0)
    r = env["client"].post("/api/photos",
                           data={"owner": env["owner"], "photo": (b, f"vis-{n}.jpg")},
                           headers=env["headers"])
    assert r.status_code == 200, r.get_data(as_text=True)[:200]
    return r.get_json()["photo"]["id"]


_UPLOAD_SEQ = [0]


def _subject_with_photos(env, name, count):
    from backend import subjects as sub
    base = _UPLOAD_SEQ[0]
    _UPLOAD_SEQ[0] += count
    pids = [_upload(env, base + i) for i in range(count)]
    with db.connect() as conn:
        s = sub.create_subject(conn, env["owner"], name)
        for pid in pids:
            sub.link_photo(conn, pid, s["id"], confirmed=True)
        conn.commit()
    return s["id"], pids


def _get(env, path):
    sep = "&" if "?" in path else "?"
    return env["client"].get("/api" + path + sep + "owner=" + env["owner"],
                             headers=env["headers"], buffered=True)


def _post(env, path, body):
    return env["client"].post("/api" + path,
                              json={"owner": env["owner"], **body},
                              headers=env["headers"])


def test_gallery_scopes_to_active_person(env):
    # Canonical shelf: exactly one birthday_4photo when 4+ photos exist,
    # scoped to the active person's confirmed photos.
    sid_dad, dad_pids = _subject_with_photos(env, "VisDad", 4)
    _subject_with_photos(env, "VisMum", 4)
    g = _get(env, f"/cards/gallery?subject_id={sid_dad}").get_json()
    assert g["ok"] and len(g["items"]) == 1, g
    assert g["scope"]["subject_id"] == sid_dad
    item = g["items"][0]
    assert item["template"] == "birthday_4photo"
    got = {p["id"] for p in item["photos"]}
    assert got <= set(dad_pids), (got, dad_pids)
    assert item["headline"] == "Happy Birthday, VisDad!"
    # fewer than 4 photos: no card, honest count of what's missing
    g3 = _get(env, "/cards/gallery?photo_ids=" + dad_pids[0]).get_json()
    assert g3["ok"] and g3["items"] == [] and g3["need_photos"] == 3, g3
    r = _get(env, "/cards/gallery?subject_id=nope")
    assert r.status_code == 404


def test_reroll_rotates_photos(env):
    _sid, pids = _subject_with_photos(env, "VisRoll", 3)
    d = _post(env, "/cards/designs", {"spec": {
        "template": "portrait", "format": "5x7",
        "photos": [{"photo_id": pids[0], "crop": [0, 0, 1, 1],
                    "focus": [0.5, 0.5], "cutout": ""}],
        "headline": "Hi", "recipient": "", "sender": "Me",
        "inside_message": "x"}}).get_json()
    assert d["ok"], d
    did = d["design"]["id"]
    r = _post(env, f"/cards/{did}/reroll", {}).get_json()
    assert r["ok"], r
    assert r["design"]["id"] != did
    assert r["rotated"]["to"] != r["rotated"]["from"]
    assert set(r["rotated"]["to"]) <= set(pids)
    assert r["card_url"].endswith(f"/cards/{r['design']['id']}/r1")
    assert r["proof_url"].endswith(f"/proof/{r['design']['id']}")


def test_reroll_refuses_photoless_template(env):
    d = _post(env, "/cards/designs", {"spec": {
        "template": "typography", "format": "5x7", "photos": [],
        "headline": "Hi", "recipient": "", "sender": "Me",
        "inside_message": "x"}}).get_json()
    assert d["ok"], d
    r = _post(env, f"/cards/{d['design']['id']}/reroll", {})
    assert r.status_code == 400


def test_shelf_lists_finished_cards_with_images_used(env):
    pid = _upload(env, 0)
    d = _post(env, "/cards/designs", {"spec": {
        "template": "portrait", "format": "5x7",
        "photos": [{"photo_id": pid, "crop": [0, 0, 1, 1],
                    "focus": [0.5, 0.5], "cutout": ""}],
        "headline": "Shelf card", "recipient": "Dad",
        "sender": "Me", "inside_message": "x"}}).get_json()
    assert d["ok"], d
    s = _get(env, "/cards/shelf").get_json()
    assert s["ok"] and s["count"] >= 1
    mine = [it for it in s["items"] if it["design_id"] == d["design"]["id"]]
    assert mine, s["count"]
    item = mine[0]
    assert item["photo_ids"] == [pid]
    assert item["photos"][0]["url"].endswith(f"/api/cards/photos/{pid}/image")
    assert item["year"] >= 2026 and item["order"] is None
    assert item["proof_url"].endswith(f"/proof/{d['design']['id']}")


def test_gallery_reroll_tools_registered_public():
    from backend import mcp_server as M
    names = [fn.__name__ for fns in M.TOOL_AREAS.values() for fn in fns]
    assert "figg_card_gallery" in names and "figg_card_reroll" in names
    # gallery display now flows through the six (make/get); the dedicated
    # display tools are keyed full-tier machinery, never anonymous
    assert "figg_card_gallery" not in M.PUBLIC_TOOLS
    assert "figg_card_reroll" not in M.PUBLIC_TOOLS
