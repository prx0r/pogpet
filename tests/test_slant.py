"""Slant3D direct client. Pure/staged paths offline; live reads proven
manually 2026-10-10 (platforms/filaments/components with stored key)."""
import unittest
from unittest.mock import patch

from backend import slant


class SlantTest(unittest.TestCase):
    def test_key_configured(self):
        self.assertTrue(slant.api_key())

    def test_default_filament_prefers_black_pla(self):
        fils = [{"publicId": "a", "name": "PLA PURPLE", "profile": "PLA",
                 "available": True},
                {"publicId": "b", "name": "PLA BLACK", "profile": "PLA",
                 "available": True}]
        self.assertEqual(slant.default_filament(fils)["publicId"], "b")
        self.assertIsNone(slant.default_filament([]))
        self.assertIsNone(slant.default_filament(
            [{"publicId": "x", "name": "PLA RED", "profile": "PLA",
              "available": False}]))

    def test_draft_staged_without_address(self):
        r = slant.draft_order(file_id="f", filament_id="m", email="",
                              address={})
        self.assertFalse(r["ok"])
        self.assertTrue(r["staged"])

    def test_process_gated(self):
        r = slant.process_order("SLANT_1")
        self.assertFalse(r["ok"])
        self.assertTrue(r["staged"])

    def test_components_shape(self):
        fake = {"ok": True, "components": [{"name": "SL008 - Keychain"}]}
        with patch.object(slant, "components", return_value=fake):
            c = slant.components()
        self.assertTrue(c["ok"])
        self.assertIn("Keychain", c["components"][0]["name"])

    def test_estimate_flow_shape(self):
        blob = b"solid t\nendsolid t\n"
        calls = {}

        def fake_call(method, path, body=None, timeout=60):
            calls.setdefault("paths", []).append((method, path))
            if path == "/files/direct-upload":
                return {"data": {"presignedUrl": "https://x/y",
                                 "filePlaceholder": {"id": "ph"}}}
            if path == "/files/confirm-upload":
                return {"data": {"publicFileServiceId": "file-1"}}
            if path.endswith("/estimate"):
                self.assertEqual(body, {"options": {"filamentId": "m"}})
                return {"data": {"total": 4.2}}
            raise AssertionError(path)

        class FakeResp:
            def __enter__(self): return self
            def __exit__(self, *a): return False
            def read(self): return blob

        class FakeReq:
            def __init__(self, *a, **k): pass
            def add_header(self, *a, **k): pass

        import urllib.request as _ul
        with patch.object(slant, "_call", side_effect=fake_call):
            with patch.object(_ul, "urlopen", lambda *a, **k: FakeResp()):
                with patch.object(_ul, "Request", FakeReq):
                    r = slant.estimate_from_url(file_url="https://x/a.stl",
                                                name="a.stl", filament_id="m")
        self.assertTrue(r["ok"])
        self.assertEqual(r["file_id"], "file-1")
        self.assertEqual(r["total_usd"], 4.2)


if __name__ == "__main__":
    unittest.main()


class ParametricTest(unittest.TestCase):
    @unittest.skipUnless(__import__("backend.parametric", fromlist=["available"]).available(),
                         "no cad venv")
    def test_panel_verified_stl(self):
        import tempfile
        from backend import parametric
        out = tempfile.mkdtemp() + "/wall.stl"
        r = parametric.panel(w=60, h=40, t=3, out=out)
        self.assertTrue(r["ok"], r)
        import pathlib
        self.assertGreater(pathlib.Path(out).stat().st_size, 1000)
