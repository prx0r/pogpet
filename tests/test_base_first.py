"""Base-first enforcement: fulfil refuses drafts saved without the line base."""
import unittest

from tests.test_cards import CardsJourney


class TestBaseFirst(CardsJourney):
    def test_save_without_base_flags_and_fulfil_refuses(self):
        r = self.post("/design/save", {"line": "golf_marker", "text": "DAD"})
        self.assertEqual(r.status_code, 200)
        body = r.json
        self.assertTrue(body["ok"])
        self.assertFalse(body["base_first"])
        did = body["design_id"]
        # reserve (no fulfil) still allowed
        r2 = self.post("/design/order", {"design_id": did, "qty": 1})
        self.assertEqual(r2.status_code, 200)
        # fulfil refused with a base-first error
        r3 = self.post("/design/order", {"design_id": did, "qty": 1, "fulfil": True})
        self.assertEqual(r3.status_code, 400)
        self.assertIn("base", r3.json["error"])

    def test_fetch_then_save_passes_fulfil_gate(self):
        g = self.get("/design/base/golf_marker")
        self.assertEqual(g.status_code, 200)
        r = self.post("/design/save", {"line": "golf_marker", "text": "DAD"})
        self.assertTrue(r.json["base_first"])
        did = r.json["design_id"]
        # fulfil passes the gate now (Shopify unconfigured → attempted, not ok —
        # the point is it is NOT a base_first refusal)
        r2 = self.post("/design/order", {"design_id": did, "qty": 1, "fulfil": True})
        body = r2.json
        self.assertTrue(body["ok"])
        self.assertTrue(body["shopify"]["attempted"])

    def test_croc_base_serves_pin_base(self):
        g = self.get("/design/base/croc_tag")
        self.assertEqual(g.status_code, 200)
        self.assertIn("stl", g.headers.get("Content-Type", ""))
        self.assertLess(len(g.data), 200000)  # pin base, not the dog

    def test_base_json_format(self):
        import base64
        import hashlib
        g = self.client.get("/api/design/base/croc_tag",
                            query_string={"owner": self.owner, "format": "json"},
                            headers=self.headers, buffered=True)
        g.close()
        body = g.json
        self.assertTrue(body["ok"])
        self.assertEqual(body["axes"], "[x, y, z]")
        raw = base64.b64decode(body["base64"])
        self.assertEqual(hashlib.md5(raw).hexdigest(), body["md5"])
        self.assertEqual(len(raw), body["bytes"])
        # mesh bases are too big for inline JSON — download note instead
        g2 = self.client.get("/api/design/base/ornament",
                             query_string={"owner": self.owner, "format": "json"},
                             headers=self.headers, buffered=True)
        g2.close()
        self.assertIsNone(g2.json.get("base64"))
        self.assertIn("download", g2.json)

    def test_validate_gaps(self):
        r = self.post("/design/validate", {"line": "nope"})
        self.assertEqual(r.status_code, 400)
        self.assertIn("croc_tag", r.json["error"])
        r = self.post("/design/validate", {"line": "golf_marker", "material": "chocolate",
                                           "dims_mm": [1, 1, 1]})
        self.assertFalse(r.json["feasible"])
        self.assertTrue(any("chocolate" in g for g in r.json["gaps"]))
        self.assertIn("axes", r.json)
        # adapter max_chars enforced: croc allows 8, not 27
        r = self.post("/design/validate", {"line": "croc_tag", "text": "x" * 27})
        self.assertFalse(r.json["feasible"])
        self.assertTrue(any("chars" in g for g in r.json["gaps"]))

    def test_gift_pack_occasion_and_addon(self):
        r = self.post("/gift-packs", {"budget_cents": 2500, "occasion": "madeup"})
        self.assertEqual(r.status_code, 400)
        self.assertIn("occasion", r.json["error"])
        r = self.post("/gift-packs", {"budget_cents": 2500, "line": "croc_tag",
                                      "occasion": "birthday"})
        body = r.json
        self.assertTrue(body["ok"])
        self.assertEqual(body["pack"]["occasion"], "birthday")
        self.assertIn("label", body["pack"]["card"])
        self.assertIn("suggested_addon", body["pack"])
        self.assertIn("needs a mesh", body["pack"]["video"]["note"])


if __name__ == "__main__":
    unittest.main()
