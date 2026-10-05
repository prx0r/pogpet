#!/usr/bin/env python3
"""Factory unit tests — pure stdlib, no Blender, pass offline.

    python3 tests/test_factory.py   (or: python3 -m unittest tests.test_factory)

Covers the review findings: known-volume cube, broken STL, ASCII STL,
3MF unit scaling, invalid-triangle count integrity, ingest collision
namespacing + size caps, adapter schema, and production-gate logic.
"""
from __future__ import annotations

import importlib.util
import json
import struct
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

FACTORY = Path(__file__).resolve().parent.parent / "scripts" / "factory"


def load(name: str):
    spec = importlib.util.spec_from_file_location(name, FACTORY / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


measure = load("measure")
normalize_3mf = load("normalize_3mf")
ingest = load("ingest")
register = load("register")


def cube_stl(size_mm: float = 10.0) -> bytes:
    """Binary STL of an axis-aligned cube, corner at origin."""
    s = size_mm
    v = [(0, 0, 0), (s, 0, 0), (s, s, 0), (0, s, 0),
         (0, 0, s), (s, 0, s), (s, s, s), (0, s, s)]
    # outward-wound face loops (signed volume needs consistency)
    quads = [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4),
             (1, 2, 6, 5), (0, 4, 7, 3), (3, 7, 6, 2)]
    out = bytearray(b"cube".ljust(80, b"\0"))
    out += struct.pack("<I", len(quads) * 2)
    for a, b, c, d in quads:
        for tri in ((a, b, c), (a, c, d)):
            pa, pb, pc = v[tri[0]], v[tri[1]], v[tri[2]]
            out += struct.pack("<3f", 0, 0, 0)
            out += struct.pack("<3f", *pa) + struct.pack("<3f", *pb) + struct.pack("<3f", *pc)
            out += struct.pack("<H", 0)
    return bytes(out)


MODEL_XML = """<?xml version="1.0" encoding="UTF-8"?>
<model unit="{unit}" xmlns="http://schemas.microsoft.com/3dmanufacturing/core/2015/02">
 <resources><object id="1" type="model"><mesh><vertices>
  <vertex x="0" y="0" z="0"/><vertex x="10" y="0" z="0"/>
  <vertex x="10" y="10" z="0"/><vertex x="0" y="10" z="0"/>
 </vertices><triangles>
  <triangle v1="0" v2="1" v3="2"/><triangle v1="0" v2="2" v3="3"/>
  {extra}
 </triangles></mesh></object></resources>
 <build><item objectid="1"/></build>
</model>"""


def threemf_bytes(unit: str = "millimeter", extra: str = "") -> bytes:
    import io
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("3D/3dmodel.model", MODEL_XML.format(unit=unit, extra=extra))
    return buf.getvalue()


def model_xml(data_3mf: bytes) -> bytes:
    """Inner 3dmodel XML out of a 3MF zip — what stl_from_3mf_xml consumes."""
    import io
    with zipfile.ZipFile(io.BytesIO(data_3mf)) as z:
        return z.read("3D/3dmodel.model")


class TestMeasure(unittest.TestCase):
    def test_cube_volume(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "cube.stl"
            p.write_bytes(cube_stl(10.0))
            r = measure.stl_volume_dims(p)
            self.assertEqual(r["facets"], 12)
            self.assertAlmostEqual(r["volume_cm3"], 1.0, places=2)
            self.assertAlmostEqual(r["weight_pla_g"], 1.2, places=1)
            self.assertIsNone(r["weight_watertight"])  # no validate.json passed

    def test_broken_stl_raises(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "bad.stl"
            p.write_bytes(b"not a mesh at all" * 10)
            with self.assertRaises(ValueError):
                measure.stl_volume_dims(p)

    def test_ascii_stl(self):
        body = ["solid test"]
        vs = [(0, 0, 0), (10, 0, 0), (10, 10, 0), (0, 10, 0)]
        for tri in ((0, 1, 2), (0, 2, 3)):
            body.append(" facet normal 0 0 1")
            body.append("  outer loop")
            for i in tri:
                body.append(f"   vertex {vs[i][0]} {vs[i][1]} {vs[i][2]}")
            body.append("  endloop")
            body.append(" endfacet")
        body.append("endsolid test")
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "flat.stl"
            p.write_bytes(("\n".join(body) + "\n").encode())
            r = measure.stl_volume_dims(p)
            self.assertEqual(r["stl_kind"], "ascii")
            self.assertEqual(r["facets"], 2)
            self.assertEqual(r["dims_mm"], [10.0, 10.0, 0.0])


class TestNormalize(unittest.TestCase):
    def test_unit_scaling(self):
        stl, info = normalize_3mf.stl_from_3mf_xml(model_xml(threemf_bytes(unit="inch")))
        self.assertIsNotNone(stl)
        self.assertEqual(info["unit"], "inch")
        self.assertEqual(info["scale"], 25.4)
        (n,) = struct.unpack("<I", stl[80:84])
        self.assertEqual(n, 2)
        x = struct.unpack("<f", stl[84 + 12:84 + 16])[0]
        self.assertAlmostEqual(x, 0.0)

    def test_invalid_triangles_skipped_count_honest(self):
        # one good tri, one degenerate (all same vertex), one out-of-range
        extra = ('<triangle v1="0" v2="0" v3="0"/>'
                 '<triangle v1="0" v2="1" v3="99"/>')
        stl, info = normalize_3mf.stl_from_3mf_xml(model_xml(threemf_bytes(extra=extra)))
        self.assertIsNotNone(stl)
        (n,) = struct.unpack("<I", stl[80:84])
        self.assertEqual(n, 2)  # header count == bytes actually written
        self.assertEqual(len(stl), 84 + 50 * 2)
        self.assertEqual(info["skipped_tris"], 2)

    def test_empty_model_returns_none(self):
        stl, _ = normalize_3mf.stl_from_3mf_xml(b"<model/>")
        self.assertIsNone(stl)


class TestIngest(unittest.TestCase):
    def test_collision_namespacing(self):
        with tempfile.TemporaryDirectory() as td:
            zp = Path(td) / "demo-model_files.zip"
            with zipfile.ZipFile(zp, "w") as z:
                z.writestr("a/part.stl", b"fake-a")
                z.writestr("b/part.stl", b"fake-b")
                z.writestr("licence.txt", b"terms")
            ingest.OUT = Path(td) / "_ingest"  # exercise the real path
            try:
                rec = ingest.ingest(zp)
            finally:
                ingest.OUT = ingest.SRC / "_ingest"
            self.assertEqual(len(rec["stl"]), 2)
            got = sorted(p.relative_to(Path(td) / "_ingest" / "demo").as_posix()
                         for p in (Path(td) / "_ingest" / "demo").rglob("*.stl"))
            self.assertEqual(len(got), 2)  # no silent overwrite
            self.assertNotEqual(got[0], got[1])

    def test_size_caps_defined(self):
        self.assertGreater(ingest.MAX_MEMBER_BYTES, 0)
        self.assertGreater(ingest.MAX_ARCHIVE_BYTES, ingest.MAX_MEMBER_BYTES)


class TestAdapters(unittest.TestCase):
    def test_adapter_schema(self):
        ads = sorted((FACTORY / "adapters").glob("*.json"))
        self.assertGreaterEqual(len(ads), 6)
        for f in ads:
            ad = json.loads(f.read_text())
            s = ad["surface"]
            self.assertIn(tuple(s["normal"]), [(0, 0, 1), (0, 0, -1), (0, 1, 0),
                                              (0, -1, 0), (1, 0, 0), (-1, 0, 0)],
                          f"{f.name}: normal must be axis-aligned")
            for k in ("origin_mm", "width_mm", "height_mm", "embed_mm"):
                self.assertIn(k, s, f"{f.name}: surface.{k}")
            self.assertIn("max_chars", ad.get("text", {}), f"{f.name}")


class TestGates(unittest.TestCase):
    def _entry(self, **kw):
        e = {"base": "", "personalization": {"method": "emboss"},
             "provenance": {"commercial_use": "unverified"},
             "sample": "needed", "recipes": {"production_3mf": "todo"}}
        e.update(kw)
        return e

    def test_nothing_ready_without_evidence(self):
        ok, missing = register.production_gates(self._entry(), {})
        self.assertFalse(ok)
        self.assertIn("no-master", missing)

    def test_reference_blocked_on_commerce_and_sample(self):
        e = self._entry(base="masters/line_reader.stl",
                        personalization={"method": "emboss",
                                         "adapter": "adapters/line_reader.json"})
        ok, missing = register.production_gates(e, {"line_reader.stl": "PASS"})
        self.assertFalse(ok)
        self.assertIn("commercial-use-unverified", missing)
        self.assertIn("no-sample", missing)
        self.assertIn("no-production-3mf", missing)

    def test_full_evidence_passes(self):
        e = self._entry(base="masters/line_reader.stl",
                        personalization={"method": "emboss",
                                         "adapter": "adapters/line_reader.json"},
                        provenance={"commercial_use": "yes (own geometry)"},
                        sample="have",
                        recipes={"production_3mf": "exists"})
        ok, missing = register.production_gates(e, {"line_reader.stl": "PASS"})
        self.assertTrue(ok)
        self.assertEqual(missing, [])

    def test_fixable_master_blocks(self):
        e = self._entry(base="masters/rummy_rack.stl",
                        personalization={"method": "emboss",
                                         "adapter": "adapters/rummy.json"},
                        provenance={"commercial_use": "yes (own geometry)"},
                        sample="have",
                        recipes={"production_3mf": "exists"})
        ok, missing = register.production_gates(e, {"rummy_rack.stl": "FIXABLE"})
        self.assertFalse(ok)
        self.assertIn("master-not-validated-PASS", missing)


if __name__ == "__main__":
    unittest.main()
