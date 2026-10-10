"""Mesh gate: 3 angles or explicit single; provider failure refunds."""
import unittest

from tests.test_cards import CardsJourney
from backend import db, pipeline


class TestMeshGate(CardsJourney):
    _n = 0

    def _photo(self, person=""):
        TestMeshGate._n += 1
        with db.connect() as c:
            pid = db.insert_photo(c, owner=self.owner, sha256=f"abc{TestMeshGate._n}",
                                  r2_key="k", mime="image/jpeg", width=800, height=600,
                                  bytes=100, orig_name="t.jpg")
            if person:
                try:
                    c.execute("UPDATE photos SET person=? WHERE id=?", (person, pid))
                except Exception:  # noqa: BLE001 — pre-migration table
                    pass
            c.commit()
            return pid

    def test_single_photo_defaults_to_single(self):
        # Single-photo onboarding: one angle sculpts single-view by default
        # (no 400). Explicit single=False still demands 3 angles.
        pid = self._photo()
        out = pipeline.start_mesh(pid)
        self.assertFalse(out["reused"])
        self.assertEqual(out["mesh"]["status"], "queued")
        self.assertFalse(out["mesh"].get("multi_image"))
        self.assertEqual(out["mesh"].get("angles"), 1)

    def test_explicit_single_false_still_demands_angles(self):
        pid = self._photo()
        with self.assertRaises(pipeline.PipelineError) as cm:
            pipeline.start_mesh(pid, single=False)
        self.assertEqual(cm.exception.code, 400)

    def test_three_angles_auto_multi(self):
        pids = [self._photo(person="Dad") for _ in range(3)]
        out = pipeline.start_mesh(pids[0])
        self.assertTrue(out["mesh"].get("multi_image"))
        self.assertEqual(out["mesh"].get("angles"), 3)
    def test_refund_decrements(self):
        with db.connect() as c:
            day = "2099-01-01"
            db.spend_credit(c, self.owner, day, "mesh", 3)
            db.spend_credit(c, self.owner, day, "mesh", 3)
            db.refund_credit(c, self.owner, day, "mesh")
            self.assertEqual(db.credit_used(c, self.owner, day, "mesh"), 1)


class TestGenesisOnly(unittest.TestCase):
    """Meshy is genesis only: the live pipeline may create meshes
    (single/multi image-to-3d) and poll them — never synthesize views,
    repair, retexture, or animate through Meshy."""

    def test_pipeline_never_calls_non_genesis(self):
        from pathlib import Path
        src = (Path(__file__).resolve().parents[1] / "backend" / "pipeline.py").read_text()
        for banned in ("create_multiview", "repair_printability"):
            self.assertNotIn(banned, src)


if __name__ == "__main__":
    unittest.main()
