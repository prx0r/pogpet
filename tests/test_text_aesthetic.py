"""Text primitive + aesthetic onboarding. Isolated temp DB, no network."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from backend import config, db, studio_library, subjects
from backend.server import app


class TextAestheticTest(unittest.TestCase):
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
        # seed one hero still so the text preview renderer runs
        from PIL import Image as _Image
        prod = root / "productimg" / "prod"
        prod.mkdir(parents=True, exist_ok=True)
        _Image.new("RGB", (400, 400), (250, 250, 248)).save(prod / "dart_stand-hero.png")
        _Image.new("RGB", (400, 400), (250, 250, 248)).save(prod / "prod-hero.png")
        self.owner = "pog_texttests"
        self.headers = {"X-API-Token": config.API_TOKEN,
                        "X-Owner-Sig": config.sign_owner(self.owner)}
        self.client = app.test_client()

    def tearDown(self):
        for p in reversed(self.patches):
            p.stop()
        self.tmp.cleanup()

    def _post(self, path, body):
        return self.client.post("/api" + path, json={"owner": self.owner, **body},
                               headers=self.headers)

    def test_dart_live_and_text(self):
        r = self._post("/products/personalise", {"line": "dart_stand"})
        self.assertEqual(r.status_code, 200, r.json)
        r = self._post("/products/personalise",
                       {"line": "dart_stand", "text": "chris"})
        self.assertEqual(r.status_code, 200, r.json)
        self.assertEqual(r.json["text"], "CHRIS")
        self.assertTrue((r.json["text_preview"] or "").startswith("/img/text/"))
        # too long / wrong line / bad charset
        r = self._post("/products/personalise",
                       {"line": "dart_stand", "text": "x" * 15})
        self.assertEqual(r.status_code, 400)
        r = self._post("/products/personalise",
                       {"line": "ornament", "text": "CHRIS"})
        self.assertEqual(r.status_code, 400)
        r = self._post("/products/personalise",
                       {"line": "dart_stand", "text": "chris!!!"})
        self.assertEqual(r.status_code, 400)

    def test_order_carries_text(self):
        r = self._post("/products/order",
                       {"line": "dart_stand", "text": "Dad's Darts", "qty": 1})
        self.assertEqual(r.status_code, 200, r.json)
        self.assertIn("DAD'S DARTS", r.json["label"])

    def test_aesthetic_picker_and_auto_colour(self):
        r = self.client.get("/api/onboarding/aesthetic?token=" + config.API_TOKEN)
        self.assertEqual(r.status_code, 200, r.json)
        self.assertEqual(len(r.json["pairs"]), 3)
        with db.connect() as c:
            s = subjects.create_subject(c, self.owner, "Chris Prior")
        r = self.client.post(
            "/api/onboarding/aesthetic",
            json={"owner": self.owner, "subject_id": s["id"],
                  "picks": {"warm_cool": "a", "light_dark": "b",
                            "plain_pattern": "skip"}},
            headers=self.headers)
        self.assertEqual(r.status_code, 200, r.json)
        colors = r.json["aesthetic"]["colors"]
        # warm-hearth ∩ dark = chocolate first
        self.assertEqual(colors[0], "chocolate")
        # auto-colour: ornament allows coats, none requested → chocolate
        r = self._post("/products/personalise",
                       {"line": "ornament", "subject_id": s["id"]})
        self.assertEqual(r.status_code, 200, r.json)
        self.assertEqual(r.json["coat"], "chocolate")
        self.assertEqual(r.json["subject_id"], s["id"])

    def test_aesthetic_rejects(self):
        r = self.client.post("/api/onboarding/aesthetic",
                             json={"owner": self.owner},
                             headers=self.headers)
        self.assertEqual(r.status_code, 400)
        r = self.client.post(
            "/api/onboarding/aesthetic",
            json={"owner": self.owner, "subject_id": "sub_nope",
                  "picks": {}},
            headers=self.headers)
        self.assertEqual(r.status_code, 404)


class SlotPrimitiveTest(unittest.TestCase):
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
        self.owner = "pog_slottests"
        self.headers = {"X-API-Token": config.API_TOKEN,
                        "X-Owner-Sig": config.sign_owner(self.owner)}
        self.client = app.test_client()

    def tearDown(self):
        for p in reversed(self.patches):
            p.stop()
        self.tmp.cleanup()

    def _post(self, path, body):
        return self.client.post("/api" + path, json={"owner": self.owner, **body},
                               headers=self.headers)

    def test_validate_and_autofill(self):
        from backend import slots as S
        r = S.validate("dart_stand", {"name": "Sam", "tagline": "Junior 180 club",
                                      "arc": "Sam's oche",
                                      "colours": {"base": "navy", "accent": "silver"}})
        self.assertTrue(r["ok"])
        self.assertEqual(r["resolved"]["name"], "SAM")
        self.assertEqual(r["resolved"]["base"], "navy")
        with self.assertRaises(ValueError):
            S.validate("dart_stand", {"name": "Maximilian Bartholomew"})
        with self.assertRaises(ValueError):
            S.validate("dart_stand", {"name": "Sam@Home"})
        with self.assertRaises(ValueError):
            S.validate("nope", {"name": "Sam"})
        with db.connect() as c:
            s = subjects.create_subject(c, self.owner, "Chris Prior")
            subjects.set_profile(c, self.owner, s["id"], relationship="dad",
                                 profile={"interests": ["darts"]})
        auto = S.autofill(self.owner, s["id"])
        self.assertTrue(auto["ok"])
        self.assertEqual(auto["slots"]["name"], "Chris")
        self.assertEqual(auto["slots"]["arc"], "DAD'S DARTS")
        self.assertEqual(auto["slots"]["tagline"], "180 CLUB")
        self.assertFalse(S.autofill(self.owner, "sub_nope")["ok"])

    def test_personalise_slots_and_fallbacks(self):
        r = self._post("/products/personalise",
                       {"line": "dart_stand",
                        "slots": {"name": "Ben", "tagline": "Bullseye Ben",
                                  "arc": "Ben's oche",
                                  "colours": {"base": "navy", "accent": "silver"}}})
        self.assertEqual(r.status_code, 200, r.json)
        self.assertEqual(r.json["slots"]["name"], "BEN")
        self.assertEqual(r.json["slots"]["base"], "navy")
        # too long → hard error with retry hint, never silent truncate
        r = self._post("/products/personalise",
                       {"line": "dart_stand", "slots": {"name": "Maximilian Bartholomew"}})
        self.assertEqual(r.status_code, 400)
        self.assertIn("nickname", r.json.get("error", ""))
        # autofill from subject when name omitted
        with db.connect() as c:
            s = subjects.create_subject(c, self.owner, "Ben")
        r = self._post("/products/personalise",
                       {"line": "dart_stand", "subject_id": s["id"],
                        "slots": {"tagline": "180 Club"}})
        self.assertEqual(r.status_code, 200, r.json)
        self.assertEqual(r.json["slots"]["name"], "BEN")

    def test_order_slots_label(self):
        r = self._post("/products/order",
                       {"line": "dart_stand",
                        "slots": {"name": "Ben", "arc": "Ben's oche"},
                        "qty": 1})
        self.assertEqual(r.status_code, 200, r.json)
        self.assertIn("BEN", r.json["label"])


if __name__ == "__main__":
    unittest.main()
