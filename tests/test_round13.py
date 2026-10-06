"""Round 13 regression: account/cart link, factory validation, shelf honesty."""
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

from backend import db
from scripts.factory import register
import backend.config as config


class TestOrdersDesignLink(unittest.TestCase):
    def test_design_id_column_and_persist(self):
        db.init()
        with db.connect() as c:
            cols = [r[1] for r in c.execute("PRAGMA table_info(orders)").fetchall()]
            self.assertIn("design_id", cols)
            o = db.create_order(
                c, owner="test_round13", line="golf_marker", mesh_id="",
                coat="none", hat="none", qty=1, price_cents=100,
                note="design tst_123 (PLA/DAD)", design_id="tst_123",
            )
            self.assertEqual(o.get("design_id"), "tst_123")
            # cleanup
            c.execute("DELETE FROM orders WHERE owner=?", ("test_round13",))
            c.commit()


class TestFactoryValidation(unittest.TestCase):
    def test_clog_golf_adapters_exist(self):
        for name in ("clog_charm.json", "golf_marker.json"):
            ad = json.loads((ROOT / "scripts" / "factory" / "adapters" / name).read_text())
            self.assertIn("surface", ad)
            self.assertIn("max_chars", ad.get("text", {}))

    def test_clog_golf_no_longer_missing_validation(self):
        verdicts = {"clog_charm.stl": "PASS", "golf_marker.stl": "PASS"}
        for line, base in (("clog_charm", "masters/clog_charm.stl"),
                           ("golf_marker", "masters/golf_marker.stl")):
            e = {"base": base,
                 "personalization": {"method": "emboss", "adapter": f"adapters/{line}.json"},
                 "provenance": {"commercial_use": "unverified"},
                 "sample": "needed", "recipes": {"production_3mf": "todo"}}
            ok, missing = register.production_gates(e, verdicts)
            self.assertFalse(ok)  # still blocked on sample/3MF/commerce — honest
            self.assertNotIn("master-not-validated-PASS", missing)
            self.assertIn("no-sample", missing)
            self.assertIn("no-production-3mf", missing)


class TestShelfHonesty(unittest.TestCase):
    def test_render_live_where_stills_exist(self):
        for lid in ("keycap", "book_holder", "golf_marker", "straw_charm",
                    "line_reader", "card_rack", "tcg_stand"):
            spec = config.STUDIO_LINES[lid]
            self.assertEqual(spec.get("status"), "live")
            self.assertEqual(spec.get("recipes", {}).get("render"), "live",
                             f"{lid}: 4-angle stills exist, recipes.render should be live")
            # production still blocked until sample + 3MF
            self.assertEqual(spec.get("sample"), "needed")
            self.assertEqual(spec.get("recipes", {}).get("production_3mf"), "todo")

    def test_clog_stays_soon_until_sample(self):
        spec = config.STUDIO_LINES["clog_charm"]
        self.assertEqual(spec.get("status"), "soon")


if __name__ == "__main__":
    unittest.main()
