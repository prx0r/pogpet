"""Faces + restore dispatcher tests. No model, no network, no key."""
import unittest

from backend import faces as F
from backend import restore as R


class CosineTest(unittest.TestCase):
    def test_identical_is_one(self):
        self.assertAlmostEqual(F.cosine([1, 0, 0], [1, 0, 0]), 1.0)

    def test_orthogonal_is_zero(self):
        self.assertAlmostEqual(F.cosine([1, 0], [0, 1]), 0.0)

    def test_opposite_is_minus_one(self):
        self.assertAlmostEqual(F.cosine([1, 0], [-1, 0]), -1.0)

    def test_empty_is_zero(self):
        self.assertEqual(F.cosine([], []), 0.0)
        self.assertEqual(F.cosine([1], []), 0.0)


class SuggestTest(unittest.TestCase):
    def test_unknown_owner_is_new_person(self):
        r = F.suggest([1.0] + [0.0] * 127, "owner_who_never_existed_xyz")
        self.assertTrue(r["new_person"])
        self.assertEqual(r["suggestions"], [])
        self.assertFalse(r["strong"])


class RestorePlanTest(unittest.TestCase):
    def test_chain_order(self):
        ops = R.plan({"lowres": True, "face": True, "blur": True})
        self.assertEqual([o["defect"] for o in ops],
                         ["blur", "face", "lowres"])

    def test_empty_signals_no_ops(self):
        self.assertEqual(R.plan({}), [])

    def test_run_without_key_is_staged(self):
        ops = R.plan({"face": True})
        r = R.run(ops[0], "https://example.com/a.jpg")
        self.assertFalse(r["ok"])
        self.assertTrue(r["staged"])

    def test_estimate_counts_ops(self):
        e = R.estimate(R.plan({"face": True, "lowres": True}))
        self.assertEqual(e["ops"], 2)


if __name__ == "__main__":
    unittest.main()


class UnitsTest(unittest.TestCase):
    def test_pixels_normalize(self):
        self.assertEqual(F.to_unit([660, 705, 199, 268], 1200, 1600),
                         [0.55, 0.440625, 0.16583333333333333, 0.1675])

    def test_normalized_passthrough(self):
        self.assertEqual(F.to_unit([0.3, 0.2, 0.4, 0.4], 1200, 1600),
                         [0.3, 0.2, 0.4, 0.4])

    def test_garbage_empty(self):
        self.assertEqual(F.to_unit([], 100, 100), [])
        self.assertEqual(F.to_unit([1, 2], 100, 100), [])
        self.assertEqual(F.to_unit([10, 10, 5, 5], 0, 0), [])

    def test_face_box_defensive(self):
        import json
        import tempfile
        from pathlib import Path
        from unittest.mock import patch
        from backend import config, db
        from backend import cards as C
        from backend import studio_library
        tmp = Path(tempfile.mkdtemp())
        patches = [patch.object(config, "DATA", tmp),
                   patch.object(config, "DB_PATH", tmp / "t.db")]
        for p in patches:
            p.start()
        try:
            db.init()
            studio_library.init()
            with db.connect() as c:
                c.execute("INSERT INTO photos (id,owner,sha256,r2_key,mime,width,height,bytes,orig_name,created_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
                          ("p1", "o", "s", "k", "image/jpeg", 1000, 1000, 1, "a.jpg", 1.0))
                c.execute("INSERT INTO photo_faces (id,photo_id,box,score,source) VALUES (?,?,?,?,?)",
                          ("f1", "p1", json.dumps([100, 100, 200, 200]), 0.9, "x"))
            boxes = C.face_box("o", "p1")
            self.assertEqual(len(boxes), 1)
            self.assertTrue(max(abs(v) for v in boxes[0]) <= 1.001)
        finally:
            for p in reversed(patches):
                p.stop()
            import shutil
            shutil.rmtree(tmp, ignore_errors=True)
