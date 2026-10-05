#!/usr/bin/env python3
"""Voice brain unit tests — offline safe, no keys, no network.

    python3 -m unittest tests.test_voice -v

Provider registry, stub sessions, model swap via config, and the
no-key refusal of the live path.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backend import config, voice_chat as vc  # noqa: E402


class TestRegistry(unittest.TestCase):
    def test_both_providers_registered(self):
        self.assertIn("stub", vc.PROVIDERS)
        self.assertIn("gemini_live", vc.PROVIDERS)

    def test_tools_named(self):
        self.assertIn("figg_guide_packs", vc.VOICE_TOOLS)
        self.assertIn("figg_checkout", vc.VOICE_TOOLS)

    def test_instructions_person_first(self):
        self.assertIn("person", vc.SHOPPER_INSTRUCTIONS)


class TestStub(unittest.TestCase):
    def test_stub_session_offline(self):
        s = vc.PROVIDERS["stub"].create_session("anon")
        self.assertTrue(s["ok"])
        self.assertEqual(s["provider"], "stub")
        self.assertTrue(s["session_id"].startswith("vs_"))
        self.assertIn("figg_checkout", s["tools"])


class TestLive(unittest.TestCase):
    def test_no_key_means_unconfigured(self):
        self.assertFalse(bool(config.GOOGLE_API_KEY))
        self.assertFalse(vc.PROVIDERS["gemini_live"].is_configured())

    def test_no_key_refuses_session(self):
        with self.assertRaises(vc.VoiceError):
            vc.PROVIDERS["gemini_live"].create_session("anon")

    def test_default_is_stub_without_key(self):
        self.assertEqual(vc.active_provider().name, "stub")

    def test_model_swappable(self):
        self.assertTrue(config.GEMINI_VOICE_MODEL)
        models = vc.PROVIDERS["gemini_live"].list_models()
        self.assertEqual(models[0]["id"], config.GEMINI_VOICE_MODEL)


if __name__ == "__main__":
    unittest.main()
