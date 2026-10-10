"""Gift compiler + feasibility gate + booklet proof. Offline."""
import subprocess
import unittest

from backend import components as C
from backend import config
from backend import feasibility as F
from backend.server import app


class GiftCompileTest(unittest.TestCase):
    def test_little_witch_viable_with_sane_postage(self):
        r = C.compile_gift("little_witch", "Shenzhen", ship_cents=800)
        self.assertTrue(r["ok"])
        self.assertEqual(r["verdict"], "viable")
        kinds = {l["id"]: l["kind"] for l in r["lines"]}
        self.assertEqual(kinds["OH-JOURNAL-A6"], "component")
        self.assertEqual(kinds["brick"], "product")
        self.assertEqual(r["materials_cents"], 2000 + 299)

    def test_postage_rule_rejects_bad_unit(self):
        # £30 gift, £8 materials, £22 postage is NOT viable.
        r = C.compile_gift("little_witch", "Shenzhen", ship_cents=2200)
        self.assertEqual(r["verdict"], "unviable")
        self.assertTrue(any("postage" in s for s in r["reasons"]))

    def test_missing_shipment_pends(self):
        r = C.compile_gift("little_witch", "Shenzhen")
        self.assertEqual(r["verdict"], "pending-shipment")

    def test_unknown_recipe(self):
        self.assertFalse(C.compile_gift("nope")["ok"])

    def test_feasibility_gate(self):
        good = C.compile_gift("little_witch", "Shenzhen", ship_cents=500)
        s = F.score_gift(good)
        self.assertGreaterEqual(s["score"], F.GATE)
        # Rights unreviewed → scored well but NOT publishable (canonical
        # vision §4: purchasable false until rights + manufacturing proven).
        self.assertFalse(good["purchasable"])
        self.assertFalse(s["publishable"])
        cleared = dict(good, purchasable=True)
        self.assertTrue(F.score_gift(cleared)["publishable"])
        bad = C.compile_gift("little_witch", "Shenzhen", ship_cents=2200)
        s2 = F.score_gift(bad)
        self.assertFalse(s2["publishable"])
        kid = F.score_gift(good, ["kids", "battery"])
        self.assertLess(kid["parts"]["safety"], 10)
        self.assertTrue(any("kids" in x for x in kid["reasons"]))

    def test_endpoints(self):
        headers = {"X-API-Token": config.API_TOKEN}
        client = app.test_client()
        tok = config.API_TOKEN
        r = client.get("/api/recipes/check?recipe=charm_lab&token=" + tok,
                       headers=headers)
        self.assertEqual(r.status_code, 200, r.json)
        self.assertTrue(r.json["ready_to_pack"])
        r = client.post("/api/gifts/compile?token=" + tok,
                        json={"recipe": "little_witch", "ship_cents": 800},
                        headers=headers)
        self.assertEqual(r.status_code, 200, r.json)
        self.assertEqual(r.json["verdict"], "viable")
        self.assertIn("feasibility", r.json)

    def test_mcp_registered_full_tier_only(self):
        from backend import mcp_server as M
        names = [fn.__name__ for fns in M.TOOL_AREAS.values() for fn in fns]
        for t in ("oddhobb_recipe_check", "oddhobb_gift_compile"):
            self.assertIn(t, names)
            self.assertNotIn(t, M.PUBLIC_TOOLS)

    def test_openapi_documents_recipe_paths(self):
        import json
        import pathlib
        d = json.loads(pathlib.Path("site/openapi.json").read_text())
        for p in ("/backend/api/recipes/check", "/backend/api/gifts/compile"):
            self.assertIn(p, d["paths"], f"missing {p}")

    def test_booklet_generates(self):
        import tempfile
        from pathlib import Path
        tmp = Path(tempfile.mkdtemp())
        r = subprocess.run(
            ["python3", "scripts/booklet_preview.py", "--title", "T",
             "--message", "M", "--out", str(tmp)],
            capture_output=True, text=True, cwd=".")
        self.assertEqual(r.returncode, 0, r.stderr[-300:])
        pdfs = list(tmp.glob("*.pdf"))
        self.assertEqual(len(pdfs), 1)
        self.assertTrue(pdfs[0].read_bytes().startswith(b"%PDF"))


if __name__ == "__main__":
    unittest.main()
