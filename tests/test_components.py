"""Component registry + recipe runs. Offline, isolated temp DB."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from backend import components as C
from backend import config, db


class ComponentsTest(unittest.TestCase):
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

    def tearDown(self):
        for p in reversed(self.patches):
            p.stop()
        self.tmp.cleanup()

    def test_charm_lab_ready_in_shenzhen(self):
        r = C.check_recipe("charm_lab", "Shenzhen")
        self.assertTrue(r["ok"])
        self.assertTrue(r["ready_to_pack"])
        kinds = {l["component_id"]: l["kind"] for l in r["lines"]}
        self.assertEqual(kinds["OH-BEAD-001"], "stocked")
        self.assertEqual(kinds["OH-CHARM-SIG"], "made")
        self.assertEqual(r["box_quote"]["kitting_cents"], 50)
        self.assertEqual(r["box_quote"]["pick_pack_cents"], 99)

    def test_short_stock_blocks(self):
        r = C.check_recipe("charm_lab", "Shenzhen", qty=1000)
        self.assertFalse(r["ready_to_pack"])
        shorts = [l for l in r["lines"] if not l["feasible"]]
        self.assertTrue(shorts)
        self.assertTrue(shorts[0]["status"].startswith("short"))

    def test_unknown_recipe(self):
        self.assertFalse(C.check_recipe("nope")["ok"])

    def test_run_states_forward_only(self):
        run = C.start_run("charm_lab", "Shenzhen")
        self.assertTrue(run["ok"])
        rid = run["run_id"]
        # skip ahead: rejected
        bad = C.set_item_status(rid, "OH-BEAD-001", "verified")
        self.assertFalse(bad["ok"])
        # walk properly
        for st in ("ordered", "received", "verified"):
            r = C.set_item_status(rid, "OH-BEAD-001", st)
            self.assertTrue(r["ok"], st)
        # backwards: rejected
        back = C.set_item_status(rid, "OH-BEAD-001", "ordered")
        self.assertFalse(back["ok"])
        mid = C.run_status(rid)
        self.assertFalse(mid["eligible_to_pack"])
        # verify everything else
        with db.connect() as c:
            rest = [r["component_id"] for r in c.execute(
                "SELECT component_id FROM run_items WHERE run_id=?", (rid,))]
        for cid in rest:
            if cid == "OH-BEAD-001":
                continue
            for st in ("ordered", "received", "verified"):
                self.assertTrue(C.set_item_status(rid, cid, st)["ok"])
        done = C.run_status(rid)
        self.assertTrue(done["eligible_to_pack"])

    def test_living_cottage_recipe(self):
        from backend import components as C
        r = C.check_recipe("living_cottage_001", "Shenzhen")
        self.assertTrue(r["ok"])
        self.assertTrue(r["ready_to_pack"])
        kinds = {l["component_id"]: l["kind"] for l in r["lines"]}
        self.assertEqual(kinds["OH-SHELL-COTTAGE"], "made")
        self.assertEqual(kinds["OH-LED-STRIP"], "stocked")
        self.assertEqual(kinds["OH-VOICE-MOD"], "special")


if __name__ == "__main__":
    unittest.main()
