"""Surface parity: endpoint → MCP tool → openapi path. Guards the rule."""
import json
import pathlib
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from backend import config, db

PARITY = [
    ("/api/products/candidates", "oddhobb_candidates",
     "/backend/api/products/candidates"),
    ("/api/quotes/compare", "oddhobb_quotes",
     "/backend/api/quotes/compare"),
    ("/api/templates/fill", "oddhobb_fill_template",
     "/backend/api/templates/fill"),
    ("/api/studio/families", "oddhobb_families",
     "/backend/api/studio/families"),
    ("/api/family/reminders", "oddhobb_reminders",
     "/backend/api/family/reminders"),
    ("/api/recipes/check", "oddhobb_recipe_check",
     "/backend/api/recipes/check"),
    ("/api/gifts/compile", "oddhobb_gift_compile",
     "/backend/api/gifts/compile"),
    ("/api/projects/check", "oddhobb_project_check",
     "/backend/api/projects/check"),
    ("/api/orders/track", "oddhobb_track_order",
     "/backend/api/orders/track"),
]


class ParityTest(unittest.TestCase):
    def test_every_endpoint_has_tool_and_spec(self):
        from backend import mcp_server as M
        from backend.server import app
        names = [fn.__name__ for fns in M.TOOL_AREAS.values() for fn in fns]
        routes = {r.rule for r in app.url_map.iter_rules()}
        spec = json.loads(pathlib.Path("site/openapi.json").read_text())
        for endpoint, tool, path in PARITY:
            self.assertIn(tool, names, tool)
            self.assertNotIn(tool, M.PUBLIC_TOOLS, tool)
            self.assertIn(path, spec["paths"], path)
            self.assertTrue(any(endpoint in r for r in routes), endpoint)


class TrackOrderTest(unittest.TestCase):
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
        from backend.server import app
        self.client = app.test_client()
        self.owner = "pog_tracktests"
        self.headers = {"X-API-Token": config.API_TOKEN,
                        "X-Owner-Sig": config.sign_owner(self.owner)}

    def tearDown(self):
        for p in reversed(self.patches):
            p.stop()
        self.tmp.cleanup()

    def test_track_roundtrip(self):
        from backend.server import app  # noqa
        with db.connect() as c:
            o = db.create_order(c, owner=self.owner, line="ornament",
                                mesh_id="msh_x", coat="none", hat="none",
                                qty=1, price_cents=1500, note="t")
        r = self.client.get("/api/orders/track",
                            query_string={"owner": self.owner,
                                          "order_id": o["id"]},
                            headers=self.headers)
        self.assertEqual(r.status_code, 200, r.json)
        self.assertEqual(r.json["order"]["id"], o["id"])
        r = self.client.get("/api/orders/track",
                            query_string={"owner": self.owner,
                                          "order_id": "ord_nope"},
                            headers=self.headers)
        self.assertEqual(r.status_code, 404)
        r = self.client.get("/api/orders/track",
                            query_string={"owner": self.owner,
                                          "order_id": o["id"]})
        self.assertEqual(r.status_code, 401)


if __name__ == "__main__":
    unittest.main()
