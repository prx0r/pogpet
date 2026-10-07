#!/usr/bin/env python3
"""Supplier registry unit tests — offline, no keys, no network.

    python3 -m unittest tests.test_suppliers -v
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backend import suppliers as sup  # noqa: E402


class TestRegistry(unittest.TestCase):
    def test_fourteen_suppliers(self):
        self.assertEqual(len(sup.SUPPLIERS), 14)
        for sid, s in sup.SUPPLIERS.items():
            for k in ("label", "ships", "materials", "order", "est"):
                self.assertIn(k, s, sid)

    def test_home_farm_present(self):
        self.assertIn("PLA", sup.SUPPLIERS["makr3d"]["materials"])
        self.assertEqual(sup.SUPPLIERS["makr3d"]["est"]["kind"], "band")


class TestEstimate(unittest.TestCase):
    def test_tiny_pla_band(self):
        r = sup.estimate("makr3d", material="PLA", weight_g=1.6)
        self.assertTrue(r["feasible"])
        self.assertEqual(r["est_cents"], 129)

    def test_per_cm3(self):
        r = sup.estimate("fdfarm", material="PLA", volume_cm3=2.63)
        self.assertTrue(r["feasible"])
        self.assertEqual(r["est_cents"], round(2.63 * 320))

    def test_material_gap(self):
        r = sup.estimate("makr3d", material="TPU")
        self.assertFalse(r["feasible"])
        self.assertTrue(any("TPU" in g for g in r["gaps"]))

    def test_color_gap(self):
        r = sup.estimate("makr3d", material="PLA", colors=5)
        self.assertFalse(r["feasible"])

    def test_build_gap(self):
        r = sup.estimate("makr3d", material="PLA", dims_mm=[300, 10, 10])
        self.assertFalse(r["feasible"])

    def test_quote_suppliers(self):
        for sid in ("treatstock", "craftcloud", "dapi3d", "sculpteo", "yorkshire3d",
                    "slant3d", "shapeways", "xometry", "gelato", "mixam", "printify"):
            r = sup.estimate(sid, material="PLA", weight_g=5)
            if sup.SUPPLIERS[sid]["est"]["kind"] == "quote" or "PLA" not in sup.SUPPLIERS[sid]["materials"]:
                # paper lanes are correctly infeasible for filament; quote lanes never fake numbers
                if "PLA" not in sup.SUPPLIERS[sid]["materials"]:
                    self.assertFalse(r["feasible"])
                else:
                    self.assertTrue(r["feasible"])
                    self.assertIsNone(r["est_cents"])  # live quote, never faked
            else:
                self.assertTrue(r["feasible"])

    def test_options_ranking(self):
        opts = sup.options_for(material="PLA", weight_g=1.6, region="UK")
        self.assertTrue(opts[0]["feasible"])
        by_id = {o["supplier"]: o for o in opts}
        # paper lanes are correctly infeasible for filament lines
        self.assertFalse(by_id["gelato"]["feasible"])
        self.assertFalse(by_id["mixam"]["feasible"])
        # every filament lane that ships UK/worldwide stays feasible
        for sid, s in sup.SUPPLIERS.items():
            if "PLA" in s["materials"]:
                self.assertTrue(by_id[sid]["feasible"], sid)


if __name__ == "__main__":
    unittest.main()


FARM_IDS = {"makr3d", "yorkshire3d", "3dfarm", "treatstock", "craftcloud", "dapi3d", "sculpteo",
            "slant3d", "shapeways", "xometry", "gelato", "mixam", "printify", "printie", "fdfarm"}


class TestStorefrontAnonymity(unittest.TestCase):
    def test_fulfilment_options_carry_no_names(self):
        import sys
        sys.path.insert(0, ".")
        from backend import suppliers as sup
        import backend.server  # noqa: F401 (ensures _fulfilment_options importable)
        from backend.server import _fulfilment_options
        for lid, spec in {
            "golf_marker": {"material": "PLA", "weight_g": 1.2, "dims_mm": [24, 12, 24]},
            "controller_stand": {"material": "PLA", "weight_g": 286.9,
                                 "dims_mm": [124.5, 67.6, 56.9]},
        }.items():
            opts = _fulfilment_options(spec)
            blob = __import__("json").dumps(opts).lower()
            for fid in FARM_IDS:
                self.assertNotIn(fid.replace("3d", "3d"), blob, lid)
            self.assertTrue(opts["printable"])


class TestNoCommitment(unittest.TestCase):
    def test_qty1_everywhere(self):
        from backend import suppliers as sup
        for sid in sup.SUPPLIERS:
            r = sup.can_single_order(sid)
            self.assertTrue(r["ok"], sid)
            self.assertEqual(r["min_qty"], 1, sid)

    def test_registry_fields(self):
        from backend import suppliers as sup
        for sid, s in sup.SUPPLIERS.items():
            for k in ("min_qty", "account", "commitment"):
                self.assertIn(k, s, sid)
