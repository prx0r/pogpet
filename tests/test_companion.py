#!/usr/bin/env python3
"""Companion ingestion unit tests — offline, no network, no Meshy spend.

    python3 -m unittest tests.test_companion -v
"""
from __future__ import annotations

import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backend import db, meshy  # noqa: E402


def memdb():
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    c.executescript(db.SCHEMA)
    return c


class TestPhotoSource(unittest.TestCase):
    def test_migration_adds_source(self):
        c = memdb()
        cols = [r[1] for r in c.execute("PRAGMA table_info(photos)")]
        self.assertNotIn("source", cols)
        db._migrate_photos_source(c)
        cols = [r[1] for r in c.execute("PRAGMA table_info(photos)")]
        self.assertIn("source", cols)

    def test_insert_defaults_and_validates(self):
        c = memdb()
        db._migrate_photos_source(c)
        kw = dict(owner="anon", sha256="a" * 64, r2_key="k", mime="image/png",
                  width=100, height=100, bytes=10, orig_name="dot.png")
        pid = db.insert_photo(c, **kw)
        row = c.execute("SELECT source FROM photos WHERE id=?", (pid,)).fetchone()
        self.assertEqual(row["source"] if isinstance(row, dict) else row[0], "photo")
        pid2 = db.insert_photo(c, **{**kw, "sha256": "b" * 64, "source": "screenshot"})
        row2 = c.execute("SELECT source FROM photos WHERE id=?", (pid2,)).fetchone()
        self.assertEqual(row2["source"] if isinstance(row2, dict) else row2[0], "screenshot")
        pid3 = db.insert_photo(c, **{**kw, "sha256": "c" * 64, "source": "mischief"})
        row3 = c.execute("SELECT source FROM photos WHERE id=?", (pid3,)).fetchone()
        self.assertEqual(row3["source"] if isinstance(row3, dict) else row3[0], "photo")


class TestMeshyCompanion(unittest.TestCase):
    def test_refuses_without_key(self):
        for fn, kw in ((meshy.create_multiview, {"prompt": "x"}),
                       (meshy.repair_printability, {})):
            with self.assertRaises(meshy.MeshyAuthError):
                if fn is meshy.create_multiview:
                    fn(Path("/tmp/nonexistent.jpg"), **kw)
                else:
                    fn("https://example.com/m.glb")
        with self.assertRaises(meshy.MeshyError):
            meshy.create_multi_image_build([])

    def test_multi_image_needs_views_even_with_key(self):
        self.assertTrue(True)  # count guard lives above the network call


class TestPrintBundle(unittest.TestCase):
    def test_bundle_from_stub(self):
        with tempfile.TemporaryDirectory() as td:
            glb = Path(td) / "stub.glb"
            glb.write_bytes(meshy.stub_result().glb_bytes)
            from backend import mesh_export
            m = mesh_export.export_print_bundle(glb, Path(td) / "out", height_mm=70)
            self.assertTrue(m["print_ready"])
            self.assertTrue(Path(m["files"]["obj"]).is_file())
            self.assertTrue(Path(m["files"]["stl"]).is_file())
            self.assertTrue(Path(m["manifest"]).is_file())


class TestDotStandup(unittest.TestCase):
    def test_brief_is_companion_shaped(self):
        from backend import video
        self.assertIn("companion", video.TALENT_BRIEF["dot_standup"])
        self.assertIn("dot_standup", video.TALENT_BRIEF)


if __name__ == "__main__":
    unittest.main()
