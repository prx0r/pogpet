"""Project feasibility runner. Offline except mocked paper quotes."""
import unittest
from unittest.mock import patch

from backend import config, project_check
from backend.server import app


CHARM = {
    "name": "Charm Lab",
    "parts_3d": [{"name": "signature charm", "material": "PLA",
                  "weight_g": 8, "dims_mm": [30, 10, 30], "colors": 2}],
    "paper_skus": ["SKU-1"],
    "components_std": ["chains", "clasps"],
    "kitting": True,
}


class ProjectCheckTest(unittest.TestCase):
    def test_charm_lab_staged_with_knowns(self):
        with patch("backend.prodigi.quote",
                   return_value={"item": 1.10, "shipping": 0.95,
                                 "currency": "GBP"}):
            r = project_check.check_idea(CHARM)
        self.assertTrue(r["ok"])
        self.assertEqual(r["verdict"], "staged")
        by_lane = {l["lane"]: l for l in r["lanes"]}
        self.assertEqual(by_lane["fdm_3d"]["grade"], "LIVE")
        self.assertEqual(by_lane["fdm_3d"]["best_supplier"], "makr3d")
        self.assertEqual(by_lane["paper"]["grade"], "LIVE")
        self.assertEqual(by_lane["aliexpress"]["grade"], "staged")
        self.assertEqual(by_lane["us_station"]["grade"], "staged")
        self.assertEqual(r["known_costs"], {"GBP": 129, "USD": 140})

    def test_blocked_when_nothing_fits(self):
        idea = {"name": "Huge",
                "parts_3d": [{"material": "PLA", "weight_g": 5,
                              "dims_mm": [900, 900, 900]}]}
        r = project_check.check_idea(idea)
        self.assertEqual(r["verdict"], "blocked")
        self.assertTrue(r["lanes"][0]["gaps"])

    def test_resin_routes_to_quote_lane(self):
        idea = {"name": "Mini",
                "parts_3d": [{"material": "Resin", "weight_g": 20,
                              "dims_mm": [40, 40, 40]}]}
        r = project_check.check_idea(idea)
        lane = r["lanes"][0]
        self.assertTrue(lane["feasible"])
        self.assertIn("jlc3dp", lane["feasible_suppliers"])
        self.assertEqual(r["verdict"], "staged")  # quote grade, not live

    def test_electronics_lane(self):
        idea = {"name": "Nightlight",
                "parts_elec": [{"name": "voice module sub-assembly"}],
                "kitting": True}
        r = project_check.check_idea(idea)
        by_lane = {l["lane"]: l for l in r["lanes"]}
        elec = by_lane["electronics"]
        self.assertTrue(elec["feasible"])
        self.assertEqual(elec["grade"], "quote")
        self.assertIn("elecrow", elec["quote_houses"])
        self.assertEqual(r["verdict"], "staged")
        kit = by_lane["us_station"]
        partners = [o["partner"] for o in kit["options"]]
        self.assertIn("china_fulfillment", partners)
        self.assertIn("leicester", partners)

    def test_endpoint(self):
        headers = {"X-API-Token": config.API_TOKEN}
        client = app.test_client()
        with patch("backend.prodigi.quote",
                   return_value={"item": 1.10, "shipping": 0.95,
                                 "currency": "GBP"}):
            r = client.post("/api/projects/check?token=" + config.API_TOKEN,
                            json={"idea": CHARM}, headers=headers)
        self.assertEqual(r.status_code, 200, r.json)
        self.assertEqual(r.json["verdict"], "staged")
        r = client.post("/api/projects/check?token=" + config.API_TOKEN,
                        json={}, headers=headers)
        self.assertEqual(r.status_code, 400)

    def test_mcp_registered_full_tier_only(self):
        from backend import mcp_server as M
        names = [fn.__name__ for fns in M.TOOL_AREAS.values() for fn in fns]
        self.assertIn("oddhobb_project_check", names)
        self.assertNotIn("oddhobb_project_check", M.PUBLIC_TOOLS)

    def test_openapi_documents_check(self):
        import json
        import pathlib
        d = json.loads(pathlib.Path("site/openapi.json").read_text())
        self.assertIn("/api/projects/check".replace("/api/", "/backend/api/"),
                      d["paths"])


if __name__ == "__main__":
    unittest.main()
