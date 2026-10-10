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
