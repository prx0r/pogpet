"""Template engine tests. Isolated temp DB, no network, no keys."""
import json
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from backend import config, db, studio_library, template_engine


def _photo(c, pid, owner, w=1200, h=1200):
    c.execute(
        "INSERT INTO photos (id,owner,sha256,r2_key,mime,width,height,bytes,"
        "orig_name,created_at,person,source) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
        (pid, owner, "sha" + pid, "k/" + pid, "image/jpeg", w, h, 10,
         pid + ".jpg", time.time(), "", "photo"))


def _face(c, pid, score, box):
    c.execute(
        "INSERT INTO photo_faces (id,photo_id,box,score,source)"
        " VALUES (?,?,?,?,?)",
        (db.new_id("face"), pid, json.dumps(box), score, "test"))


class EngineTest(unittest.TestCase):
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
        self.owner = "pog_enginetests"
        with db.connect() as c:
            _photo(c, "p-solo", self.owner)
            _face(c, "p-solo", 0.9, [0.3, 0.2, 0.4, 0.4])
            _photo(c, "p-group1", self.owner)
            for i in range(3):
                _face(c, "p-group1", 0.8, [0.1 * i, 0.1, 0.05, 0.05])
            _photo(c, "p-group2", self.owner)
            for i in range(4):
                _face(c, "p-group2", 0.7, [0.1 * i, 0.2, 0.05, 0.05])
            _photo(c, "p-tiny", self.owner, w=400, h=400)
            _face(c, "p-tiny", 0.99, [0.3, 0.2, 0.4, 0.4])

    def tearDown(self):
        for p in reversed(self.patches):
            p.stop()
        self.tmp.cleanup()

    def test_unknown_template(self):
        r = template_engine.fill(self.owner, "nope")
        self.assertFalse(r["ok"])

    def test_wrap_solo_fills_best(self):
        r = template_engine.fill(self.owner, "wrap_solo")
        self.assertTrue(r["ok"])
        # p-tiny scores higher but fails min_px → p-solo wins honestly
        self.assertEqual(r["fills"]["HeroFace"]["photo_id"], "p-solo")
        self.assertTrue(r["providers"]["prodigi"]["renderable"])

    def test_trio_distinct_and_payloads(self):
        r = template_engine.fill(self.owner, "trio_card")
        g1 = r["fills"]["Group1"]["photo_id"]
        g2 = r["fills"]["Group2"]["photo_id"]
        self.assertNotEqual(g1, g2)
        self.assertEqual((g1, g2), ("p-group1", "p-group2"))
        gel = r["providers"]["gelato"]
        self.assertTrue(gel["staged"])
        self.assertEqual(gel["imagePlaceholders"][0]["name"], "HeroFace")
        pri = r["providers"]["printify"]
        self.assertIn("staged", pri)

    def test_subjects_filter(self):
        with db.connect() as c:
            c.execute("INSERT INTO studio_subjects VALUES (?,?,?,?,?)",
                      ("sub-x", self.owner, "Dad", "person", time.time()))
            c.execute("INSERT INTO photo_subjects VALUES (?,?,?,1,?)",
                      ("p-group2", "sub-x", "", "user"))
        r = template_engine.fill(self.owner, "trio_card", subjects=["Dad"])
        got = {v["photo_id"] for v in r["fills"].values() if v}
        self.assertEqual(got, {"p-group2"})


if __name__ == "__main__":
    unittest.main()
