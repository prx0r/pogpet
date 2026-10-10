"""Agent-addressable objects. Isolated temp DB; no network."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from backend import config, db, objects as OB
from backend.server import app


class ObjectsTest(unittest.TestCase):
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
        self.owner = "pog_objecttests"
        self.headers = {"X-API-Token": config.API_TOKEN,
                        "X-Owner-Sig": config.sign_owner(self.owner)}
        self.client = app.test_client()

    def tearDown(self):
        for p in reversed(self.patches):
            p.stop()
        self.tmp.cleanup()

    def test_register_resolve_state(self):
        rec = OB.register(self.owner, kind="room",
                          digital_asset="/img/room.glb",
                          capabilities=["light", "status"],
                          compatible_worlds=["tinyworld-180"])
        self.assertTrue(rec["object_id"].startswith("oddhobb-"))
        got = OB.get(rec["object_id"])
        self.assertEqual(got["capabilities"], ["light", "status"])
        self.assertIsNone(OB.get("oddhobb-nope"))
        r = OB.set_state(self.owner, rec["object_id"], "working",
                         {"task": "render"})
        self.assertTrue(r["ok"])
        self.assertEqual(r["state"]["event"], "working")
        bad = OB.set_state(self.owner, rec["object_id"], "dance")
        self.assertFalse(bad["ok"])
        foreign = OB.set_state("someone", rec["object_id"], "idle")
        self.assertFalse(foreign["ok"])
        st = OB.set_status(self.owner, rec["object_id"], "validated")
        self.assertTrue(st["ok"])
        self.assertFalse(OB.set_status(self.owner, rec["object_id"],
                                       "teleported")["ok"])

    def test_endpoints(self):
        r = self.client.post("/api/objects?token=" + config.API_TOKEN,
                             json={"owner": self.owner, "kind": "podium",
                                   "capabilities": ["display", "messages"]},
                             headers=self.headers)
        self.assertEqual(r.status_code, 200, r.json)
        oid = r.json["object_id"]
        # resolve needs the service gate but no owner (QR clients carry it)
        tok = {"token": config.API_TOKEN}
        r = self.client.get(f"/api/objects/{oid}/resolve", query_string=tok)
        self.assertEqual(r.status_code, 200, r.json)
        self.assertEqual(r.json["kind"], "podium")
        self.assertNotIn("owner", r.json)
        r = self.client.get("/api/objects/oddhobb-nope/resolve",
                            query_string=tok)
        self.assertEqual(r.status_code, 404)
        # state needs owner auth
        r = self.client.post(f"/api/objects/{oid}/state",
                             json={"owner": self.owner, "event": "new_message",
                                   "detail": {"from": "pog-1"}},
                             headers=self.headers)
        self.assertEqual(r.status_code, 200, r.json)
        self.assertEqual(r.json["state"]["event"], "new_message")
        r = self.client.post(f"/api/objects/{oid}/state",
                             json={"owner": self.owner, "event": "dance"},
                             headers=self.headers)
        self.assertEqual(r.status_code, 400)
        r = self.client.post(f"/api/objects/{oid}/state",
                             json={"owner": self.owner, "event": "idle"})
        self.assertEqual(r.status_code, 401)


if __name__ == "__main__":
    unittest.main()
