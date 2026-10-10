"""Template slot-filling over photo labels. Isolated temp DB, no network."""
import json
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from backend import config, db, studio_library, subject_assets
from backend.server import app


def _photo(c, pid, owner, w=1000, h=1000):
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


class SelectForTemplateTest(unittest.TestCase):
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
        self.owner = "pog_labeltests"
        with db.connect() as c:
            _photo(c, "p-solo", self.owner)
            _face(c, "p-solo", 0.9, [0.3, 0.2, 0.4, 0.4])  # close-up
            _photo(c, "p-group1", self.owner)
            for i in range(3):
                _face(c, "p-group1", 0.8, [0.1 * i, 0.1, 0.05, 0.05])
            _photo(c, "p-group2", self.owner)
            for i in range(4):
                _face(c, "p-group2", 0.7, [0.1 * i, 0.2, 0.05, 0.05])
            _photo(c, "p-couple", self.owner)
            _face(c, "p-couple", 0.85, [0.2, 0.2, 0.1, 0.1])
            _face(c, "p-couple", 0.85, [0.6, 0.2, 0.1, 0.1])
            c.execute(
                "INSERT INTO studio_subjects VALUES (?,?,?,?,?)",
                ("sub-dad", self.owner, "Dad", "person", time.time()))
            c.execute(
                "INSERT INTO photo_subjects VALUES (?,?,?,1,?)",
                ("p-solo", "sub-dad", "", "user-confirmed"))

    def tearDown(self):
        for p in reversed(self.patches):
            p.stop()
        self.tmp.cleanup()

    def test_funny_trio_two_groups_one_face(self):
        r = subject_assets.select_for_template(
            self.owner, {"groups": 2, "faces": 1})
        self.assertEqual(set(r["slots"]),
                         {"group_1", "group_2", "face_1"})
        self.assertEqual(r["slots"]["face_1"]["photo_id"], "p-solo")
        self.assertEqual(r["hero"]["photo_id"], "p-solo")
        self.assertEqual(r["shortfall"], [])
        # distinct photos, best first
        self.assertEqual(r["slots"]["group_1"]["photo_id"], "p-group1")

    def test_shortfall_reports_missing(self):
        r = subject_assets.select_for_template(self.owner, {"groups": 5})
        self.assertEqual(r["shortfall"], ["group 2/5"])

    def test_reserved_layers_shortfall(self):
        r = subject_assets.select_for_template(
            self.owner, {"solos": 1, "emotions": ["happy"]})
        self.assertIn("emotions labelling reserved — vision call not wired",
                      r["shortfall"])
        self.assertEqual(r["slots"]["solo_1"]["photo_id"], "p-solo")

    def test_subject_filter(self):
        r = subject_assets.select_for_template(
            self.owner, {"solos": 1, "subjects": ["Dad"]})
        self.assertEqual(r["slots"]["solo_1"]["photo_id"], "p-solo")
        r2 = subject_assets.select_for_template(
            self.owner, {"solos": 1, "subjects": ["Nobody"]})
        self.assertEqual(r2["slots"], {})
        self.assertTrue(r2["shortfall"])

    def test_mesh_template_needs_nothing(self):
        tmpl = config.PERSONAL_CARDS["merry_xmas"]
        r = subject_assets.select_for_template(self.owner, tmpl["requires"])
        self.assertEqual(r["slots"], {})
        self.assertEqual(r["shortfall"], [])

    def test_product_requires_declarations_valid(self):
        known = {"groups", "faces", "solos", "couples", "subjects",
                 "min_face_score", "emotions", "occasion", "mesh_fit"}
        for pid, spec in {**config.PRODIGI_PRODUCTS,
                          **config.PERSONAL_CARDS}.items():
            for k in (spec.get("requires") or {}):
                self.assertIn(k, known, f"{pid} requires.{k}")

    def test_product_assets_fills_wrap(self):
        r = subject_assets.product_assets(
            self.owner, "prodigi", "wrapping_paper")
        self.assertEqual(r["product_id"], "wrapping_paper")
        self.assertEqual(r["slots"]["solo_1"]["photo_id"], "p-solo")
        self.assertEqual(r["shortfall"], [])

    def test_candidates_ranked_shortlist(self):
        with db.connect() as c:
            _photo(c, "p-solo2", self.owner)
            _face(c, "p-solo2", 0.7, [0.3, 0.2, 0.4, 0.4])
        r = subject_assets.product_assets(
            self.owner, "prodigi", "wrapping_paper", per_slot=8)
        solos = r["candidates"]["solo"]
        self.assertEqual([s["photo_id"] for s in solos],
                         ["p-solo", "p-solo2"])
        self.assertIn("face_id", solos[0])

    def test_candidates_endpoint(self):
        headers = {"X-API-Token": config.API_TOKEN,
                   "X-Owner-Sig": config.sign_owner(self.owner)}
        client = app.test_client()
        r = client.get("/api/products/candidates",
                       query_string={"owner": self.owner, "kind": "prodigi",
                                     "line": "wrapping_paper", "n": 8},
                       headers=headers)
        self.assertEqual(r.status_code, 200, r.json)
        self.assertTrue(r.json["candidates"]["solo"])
        r = client.get("/api/products/candidates",
                       query_string={"owner": self.owner})
        self.assertEqual(r.status_code, 401)

    def test_provider_clients_stage_cleanly(self):
        from backend import gelato, printify
        g = gelato.fill_from_template(template_id="", title="t")
        self.assertFalse(g["ok"])
        self.assertIn("staged", g)
        p = printify.create_product(title="t", blueprint_id=1,
                                    print_provider_id=1, variants=[],
                                    print_areas=[])
        self.assertFalse(p["ok"])
        self.assertIn("staged", p)

    def test_quotes_compare_wrap(self):
        headers = {"X-API-Token": config.API_TOKEN,
                   "X-Owner-Sig": config.sign_owner(self.owner)}
        client = app.test_client()

        def fake_quote(sku, copies=1, country="GB", attrs=None,
                       shipping_method="Standard"):
            if country == "US":
                return {"currency": "GBP", "item": 4.53, "shipping": 10.57,
                        "tax": 0.0, "total": 15.10, "carrier": "USPS Priority",
                        "lab_country": "US", "warnings": ["sales tax may apply"]}
            return {"currency": "GBP", "item": 3.0, "shipping": 5.7,
                    "tax": 1.74, "total": 10.44, "carrier": "RM24",
                    "lab_country": "GB", "warnings": []}

        with patch("backend.prodigi.quote", side_effect=fake_quote):
            r = client.get("/api/quotes/compare",
                           query_string={"line": "wrapping_paper"},
                           headers=headers)
        self.assertEqual(r.status_code, 200, r.json)
        by_sup = {o["supplier"]: o for o in r.json["options"]}
        self.assertEqual(by_sup["prodigi"]["grade"], "LIVE")
        self.assertEqual(by_sup["printify"]["grade"], "catalog")
        self.assertEqual(by_sup["printify"]["blueprint_id"], 848)
        self.assertEqual(by_sup["gelato"]["grade"], "unavailable")
        self.assertEqual(r.json["picks"]["value"]["supplier"], "prodigi")
        m = r.json["matrix"]
        self.assertEqual(m["GB"]["total"], 10.44)
        self.assertEqual(m["US"]["total"], 15.10)
        self.assertEqual(m["US"]["lab_country"], "US")
        self.assertIn("duty_note", r.json)
        r = client.get("/api/quotes/compare",
                       query_string={"line": "mug"},
                       headers=headers)
        self.assertEqual(r.status_code, 400)

    def test_templates_fill_endpoint(self):
        headers = {"X-API-Token": config.API_TOKEN,
                   "X-Owner-Sig": config.sign_owner(self.owner)}
        client = app.test_client()
        r = client.get("/api/templates/fill",
                       query_string={"owner": self.owner,
                                     "template_id": "wrap_solo"},
                       headers=headers)
        self.assertEqual(r.status_code, 200, r.json)
        self.assertEqual(r.json["fills"]["HeroFace"]["photo_id"], "p-solo")
        self.assertIn("gelato", r.json["providers"])
        r = client.get("/api/templates/fill",
                       query_string={"owner": self.owner,
                                     "template_id": "nope"},
                       headers=headers)
        self.assertEqual(r.status_code, 400)


class AgentSurfacesTest(unittest.TestCase):
    def test_mcp_tools_registered_full_tier_only(self):
        from backend import mcp_server as M
        names = [fn.__name__ for fns in M.TOOL_AREAS.values() for fn in fns]
        for t in ("oddhobb_candidates", "oddhobb_fill_template",
                  "oddhobb_families", "oddhobb_reminders", "oddhobb_quotes"):
            self.assertIn(t, names)
            self.assertNotIn(t, M.PUBLIC_TOOLS)

    def test_openapi_documents_new_paths(self):
        import json
        import pathlib
        d = json.loads(pathlib.Path("site/openapi.json").read_text())
        for p in ("/backend/api/products/candidates",
                  "/backend/api/quotes/compare",
                  "/backend/api/templates/fill",
                  "/backend/api/studio/families",
                  "/backend/api/family/reminders"):
            self.assertIn(p, d["paths"], f"missing {p}")


if __name__ == "__main__":
    unittest.main()
