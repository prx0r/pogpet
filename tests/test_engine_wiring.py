"""Freaktown engine wiring: adapter contracts, public files, unique renders."""
import unittest

from tests.test_cards import CardsJourney
from backend import db


class TestEngineWiring(CardsJourney):
    def test_jaw_adapter_returns_path_contract(self):
        import backend.creative.providers.local as L
        import inspect
        src = inspect.getsource(L.JawBakeAdapter.run)
        for token in ("--script", "--out", "--name", "--voice", '"path"', '"duration"', '"bytes"'):
            self.assertIn(token, src)

    def test_performance_kernel_envelope(self):
        from backend import performance as _p
        import wave, struct
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            name = f.name
        with wave.open(name, "wb") as w:
            w.setnchannels(1); w.setsampwidth(2); w.setframerate(16000)
            w.writeframes(struct.pack("<4000h", *([8000] * 4000)))
        env = _p.audio_envelope(name, fps=15)
        self.assertTrue(env)
        self.assertGreater(max(env), 0)
        self.assertEqual(_p.viseme_for_char("b"), "MBP")
        beats = _p.compile_beats([{"text": "hi", "duration_s": 2.0, "pause_after_ms": 600}])
        self.assertEqual(beats[0]["end"], 2.0)

    def test_video_file_public(self):
        r = self.client.get("/api/videos/feed", headers=self.headers, buffered=True)
        r.close()
        self.assertTrue(r.json["ok"])

    def test_stage_assets_exist(self):
        from pathlib import Path as _P
        from backend import config
        self.assertTrue((_P(config.ROOT) / "data" / "uploads" / "chibi-figure-hook-jaw.glb").exists())
        self.assertTrue((_P("/home/ubuntu/opt/blender-4.2.9-linux-x64/blender")).exists())


if __name__ == "__main__":
    unittest.main()
