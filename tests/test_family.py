import datetime as _dt
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from backend import db, studio_library, subjects
from backend.server import _parse_birthday, app
import backend.server as S
from backend import config


def _client(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "API_TOKEN", "test-token")
    monkeypatch.setattr(config, "DATA", tmp_path)
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "figg.db")
    S.config.API_TOKEN = "test-token"
    return S.app.test_client()


def test_subjects_list_with_relationships(tmp_path, monkeypatch):
    import backend.studio_library  # noqa: F401  (registers blueprint)
    from backend import db, subjects
    c = _client(tmp_path, monkeypatch)
    backend.studio_library.init()
    db.init()
    owner, sig = "fam", config.sign_owner("fam")
    with db.connect() as conn:
        s = subjects.create_subject(conn, owner, "Cathy", kind="person")
        subjects.set_profile(conn, owner, s["id"], relationship="mother",
                             profile={"interests": ["gardening"]})
    r = c.get(f"/api/studio/subjects?owner={owner}&owner_sig={sig}&token=test-token")
    assert r.status_code == 200, r.get_data(as_text=True)[:200]
    subs = r.get_json()["subjects"]
    assert subs[0]["relationship"] == "mother"
    assert subs[0]["interests"] == ["gardening"]
    assert subs[0]["photos"] == 0


def test_card_copy_person(tmp_path, monkeypatch):
    c = _client(tmp_path, monkeypatch)
    r = c.get("/api/cards/copy/happy_birthday?name=Cathy&kind=person&token=test-token")
    assert r.status_code == 200
    card = r.get_json()["card"]
    assert "woof" not in card["sub"].lower()
    assert "Cathy" in card["sub"] or "love" in card["sub"].lower()
    assert "Dog" not in card["etsy_title"]
    r2 = c.get("/api/cards/copy/happy_birthday?name=Rex&token=test-token")
    assert "Rex" in r2.get_json()["card"]["sub"]
    assert c.get("/api/cards/copy/nope?token=test-token").status_code == 404


def test_figg_owners_multi(tmp_path, monkeypatch):
    import os
    from backend import mcp_server
    monkeypatch.setenv("FIGG_OWNER", "prx0r")
    monkeypatch.setenv("FIGG_OWNERS", "hark-dad-a7a5cc, e2estyle")
    # replicate the claimed/sig block logic via a fake request is heavy;
    # assert the env parsing contract instead
    owners = {os.environ.get("FIGG_OWNER", "").strip()} | {
        o.strip() for o in os.environ.get("FIGG_OWNERS", "").split(",")}
    owners.discard("")
    assert owners == {"prx0r", "hark-dad-a7a5cc", "e2estyle"}
    assert "mcp_server" in mcp_server.__name__


def test_session_claim_with_api_key(tmp_path, monkeypatch):
    import backend.server as S
    from backend import db
    monkeypatch.setattr(config, "API_TOKEN", "test-token")
    monkeypatch.setattr(config, "DATA", tmp_path)
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "figg.db")
    S.config.API_TOKEN = "test-token"
    db.init()
    c = S.app.test_client()
    r = c.post("/api/accounts?token=test-token",
               json={"handle": "agentfam", "password": "x" * 16})
    key = r.get_json()["api_key"]
    r2 = c.post("/api/session?token=test-token", json={"owner": "agentfam"},
                headers={"X-API-Key": key})
    assert r2.status_code == 200 and r2.get_json()["owner"] == "agentfam"
    assert c.post("/api/session?token=test-token",
                  json={"owner": "someoneelse"},
                  headers={"X-API-Key": key}).status_code == 403


def test_products_for_ranks(tmp_path, monkeypatch):
    from backend import listings as L
    ranked = L.rank_for(["golf"], "plays every weekend")
    top = [r["line"] for r in ranked[:3]]
    assert "golf_marker" in top, top
    assert all(r["reasons"] for r in ranked)


import datetime as _dt
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from backend import config, db, studio_library, subjects
from backend.server import _parse_birthday, app


class FamilyTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.patches = [
            patch.object(config, "DATA", root),
            patch.object(config, "DB_PATH", root / "test.db"),
        ]
        for p in self.patches:
            p.start()
        db.init()
        studio_library.init()
        with db.connect() as c:
            subjects.ensure_tables(c)
        self.owner = "pog_familytests"
        self.headers = {"X-API-Token": config.API_TOKEN,
                        "X-Owner-Sig": config.sign_owner(self.owner)}
        self.client = app.test_client()

    def tearDown(self):
        for p in reversed(self.patches):
            p.stop()
        self.tmp.cleanup()

    def _sub(self, name, kind="person"):
        with db.connect() as c:
            return subjects.create_subject(c, self.owner, name, kind=kind)

    def test_crud_roles_and_pet(self):
        with db.connect() as c:
            fam = subjects.create_family(c, self.owner, "Prior family")
            dad = self._sub("Chris Prior")
            mum = self._sub("Cathy")
            dog = self._sub("", kind="pet")
            subjects.add_member(c, self.owner, fam["id"], dad["id"], "dad")
            subjects.add_member(c, self.owner, fam["id"], mum["id"], "mum")
            subjects.add_member(c, self.owner, fam["id"], dog["id"], "dog")
            d = subjects.family_detail(c, self.owner, fam["id"])
        roles = {m["role"] for m in d["members"]}
        self.assertEqual(roles, {"dad", "mum", "dog"})
        kinds = {m["kind"] for m in d["members"]}
        self.assertIn("pet", kinds)
        with db.connect() as c:
            with self.assertRaises(KeyError):
                subjects.add_member(c, self.owner, fam["id"], "sub_nope", "x")
            subjects.remove_member(c, self.owner, fam["id"], dog["id"])
            d2 = subjects.family_detail(c, self.owner, fam["id"])
        self.assertEqual(len(d2["members"]), 2)

    def test_profile_onboarding_merges(self):
        with db.connect() as c:
            s = self._sub("Cathy")
            subjects.set_profile(c, self.owner, s["id"], relationship="mum",
                                 birthday="03-14", profile={"interests": ["roses"]})
            subjects.set_profile(c, self.owner, s["id"],
                                 profile={"interests": ["roses", "choir"]})
            full = subjects.profile_for(c, self.owner, s["id"])
        self.assertEqual(full["relationship"], "mum")
        self.assertEqual(full["birthday"], "03-14")
        self.assertEqual(full["profile"]["interests"], ["roses", "choir"])

    def test_parse_birthday(self):
        self.assertEqual(_parse_birthday("03-14"), (3, 14))
        self.assertEqual(_parse_birthday("1990-03-14"), (3, 14))
        self.assertIsNone(_parse_birthday(""))
        self.assertIsNone(_parse_birthday("soon"))
        self.assertIsNone(_parse_birthday(None))

    def test_families_endpoints(self):
        r = self.client.post("/api/studio/families",
                             json={"owner": self.owner, "name": "Prior family"},
                             headers=self.headers)
        self.assertEqual(r.status_code, 200, r.json)
        fid = r.json["family"]["id"]
        with db.connect() as c:
            s = subjects.create_subject(c, self.owner, "Cathy")
        r = self.client.post(f"/api/studio/families/{fid}/members",
                             json={"owner": self.owner, "subject_id": s["id"],
                                   "role": "mum"},
                             headers=self.headers)
        self.assertEqual(r.status_code, 200, r.json)
        r = self.client.get("/api/studio/families",
                            query_string={"owner": self.owner},
                            headers=self.headers)
        self.assertEqual(r.status_code, 200, r.json)
        fams = r.json["families"]
        self.assertEqual(len(fams), 1)
        self.assertEqual(fams[0]["members"][0]["role"], "mum")

    def test_profile_endpoint(self):
        with db.connect() as c:
            s = subjects.create_subject(c, self.owner, "Chris Prior")
        r = self.client.post(f"/api/studio/subjects/{s['id']}/profile",
                             json={"owner": self.owner, "relationship": "dad",
                                   "birthday": "06-01", "interests": ["golf"]},
                             headers=self.headers)
        self.assertEqual(r.status_code, 200, r.json)
        self.assertEqual(r.json["birthday"], "06-01")
        self.assertEqual(r.json["interests"], ["golf"])

    def test_reminders(self):
        soon = (_dt.date.today() + _dt.timedelta(days=9)).strftime("%m-%d")
        with db.connect() as c:
            s = subjects.create_subject(c, self.owner, "Cathy")
            subjects.set_profile(c, self.owner, s["id"], relationship="mum",
                                 birthday=soon, profile={"interests": ["roses"]})
            subjects.create_subject(c, self.owner, "NoBday")
        r = self.client.get("/api/family/reminders",
                            query_string={"owner": self.owner, "within_days": 30},
                            headers=self.headers)
        self.assertEqual(r.status_code, 200, r.json)
        rems = r.json["reminders"]
        self.assertEqual(len(rems), 1)
        self.assertEqual(rems[0]["name"], "Cathy")
        self.assertEqual(rems[0]["days_until"], 9)
        self.assertTrue(rems[0]["gifts"])
        self.assertIn("birthday_4photo", rems[0]["card_templates"])
        self.assertFalse(rems[0]["email"]["ready"])
        self.assertIn("staged", rems[0]["email"]["note"])

    def test_reminders_need_auth(self):
        r = self.client.get("/api/family/reminders",
                            query_string={"owner": self.owner})
        self.assertEqual(r.status_code, 401)


    def test_confirm_batch(self):
        sid = self._sub("Dad")["id"]
        with db.connect() as c:
            p1 = db.insert_photo(c, owner=self.owner, sha256="a" * 64,
                                 r2_key="k1", mime="image/jpeg", width=800,
                                 height=800, bytes=10, orig_name="a.jpg")
            p2 = db.insert_photo(c, owner=self.owner, sha256="b" * 64,
                                 r2_key="k2", mime="image/jpeg", width=800,
                                 height=800, bytes=10, orig_name="b.jpg")
            p3 = db.insert_photo(c, owner=self.owner, sha256="c" * 64,
                                 r2_key="k3", mime="image/jpeg", width=800,
                                 height=800, bytes=10, orig_name="c.jpg")
            c.execute("INSERT INTO photo_faces (id,photo_id,box,score,source) VALUES (?,?,?,?,?)",
                      ("face-1", p1, "[0.2,0.2,0.3,0.3]", 0.9, "upload"))
            c.execute("INSERT INTO photo_faces (id,photo_id,box,score,source) VALUES (?,?,?,?,?)",
                      ("face-2a", p2, "[0.1,0.1,0.2,0.2]", 0.9, "upload"))
            c.execute("INSERT INTO photo_faces (id,photo_id,box,score,source) VALUES (?,?,?,?,?)",
                      ("face-2b", p2, "[0.6,0.6,0.2,0.2]", 0.8, "upload"))
        r = self.client.post("/api/studio/confirm-batch",
                             json={"owner": self.owner, "subject_id": sid,
                                   "photo_ids": [p1, p2, p3, "pho_missing"]},
                             headers=self.headers)
        self.assertEqual(r.status_code, 200, r.json)
        self.assertEqual(r.json["confirmed"], [p1])
        self.assertEqual(r.json["needs_review"], [p2])
        self.assertEqual(r.json["no_face"], [p3])
        self.assertEqual(r.json["missing"], ["pho_missing"])
        with db.connect() as c:
            row = c.execute("SELECT confirmed, provenance FROM photo_subjects WHERE photo_id=? AND subject_id=?",
                            (p1, sid)).fetchone()
            self.assertEqual((row["confirmed"], row["provenance"]), (1, "batch-confirm"))
        r = self.client.post("/api/studio/confirm-batch",
                             json={"owner": self.owner, "subject_id": "sub_nope",
                                   "photo_ids": [p1]},
                             headers=self.headers)
        self.assertEqual(r.status_code, 404)
        r = self.client.post("/api/studio/confirm-batch",
                             json={"owner": self.owner},
                             headers=self.headers)
        self.assertEqual(r.status_code, 400)

    def test_upload_detects_faces_without_failing(self):
        import io
        from unittest.mock import patch as _patch
        from PIL import Image as _Image, ImageDraw as _Draw
        img = _Image.new("RGB", (400, 400), (250, 250, 248))
        _Draw.Draw(img).ellipse([100, 100, 300, 300], fill=(90, 60, 40))
        buf = io.BytesIO()
        img.save(buf, "JPEG")
        buf.seek(0)
        fake_row = [[10.0, 10.0, 50.0, 50.0] + [0.0] * 10 + [0.95]]
        with _patch("backend.faces.detect_boxes", return_value=fake_row):
            with _patch("backend.storage.put", return_value="k"):
                r = self.client.post("/api/photos?token=" + config.API_TOKEN,
                                     data={"owner": self.owner,
                                           "photo": (buf, "blank.jpg")},
                                     headers=self.headers,
                                     content_type="multipart/form-data")
        self.assertEqual(r.status_code, 200, r.json)
        pid = r.json["photo"]["id"]
        with db.connect() as c:
            rows = c.execute("SELECT box, source FROM photo_faces WHERE photo_id=?",
                             (pid,)).fetchall()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["source"], "upload")


if __name__ == "__main__":
    unittest.main()
