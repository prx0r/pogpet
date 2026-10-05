#!/usr/bin/env python3
"""Greeting + Marble unit tests — offline safe, no network, no keys.

    python3 -m unittest tests.test_greeting -v

Marble tests assert the stub: without MARBLE_API_KEY every paid path
refuses before touching the network. Greeting tests cover validation
(empty/long message, unknown room) and the PIL frame compose.
"""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backend import config, marble, video  # noqa: E402


class TestMarbleStub(unittest.TestCase):
    def test_no_key_means_stub(self):
        self.assertFalse(bool(config.MARBLE_API_KEY))

    def test_generate_refuses_without_key(self):
        with self.assertRaises(marble.MarbleAuthError):
            marble.generate_room(prompt="comedy club")

    def test_balance_none_without_key(self):
        self.assertIsNone(marble.balance())

    def test_export_refuses_without_key(self):
        with self.assertRaises(marble.MarbleAuthError):
            marble.export_world("whatever", asset="splats")


class TestRooms(unittest.TestCase):
    def test_five_rooms(self):
        self.assertEqual(set(config.ROOMS), {"void", "club", "podium", "press", "xmas"})
        for rid, r in config.ROOMS.items():
            self.assertTrue(r["label"])
            if rid == "void":
                self.assertEqual(r["backdrop"], "")

    def test_missing_backdrop_falls_back(self):
        self.assertIsNone(video.room_backdrop("club"))  # no PNGs yet
        self.assertIsNone(video.room_backdrop("nope"))


class TestGreetingValidation(unittest.TestCase):
    def test_empty_message_rejected_before_tts(self):
        with self.assertRaises(video.VideoError):
            video.make_greeting(message="  ", speaker_name="Dad",
                                voice="ryan", room="void", photo=None)

    def test_long_message_rejected(self):
        with self.assertRaises(video.VideoError):
            video.make_greeting(message="x" * 601, speaker_name="Dad",
                                voice="ryan", room="void", photo=None)

    def test_unknown_room_rejected(self):
        with self.assertRaises(video.VideoError):
            video.make_greeting(message="hi", speaker_name="Dad",
                                voice="ryan", room="arena", photo=None)

    def test_frame_compose_no_network(self):
        with tempfile.TemporaryDirectory() as td:
            out = video.compose_greeting_frame(
                None, "Dad", "Happy birthday", "void", watermark=True)
            self.assertTrue(out.is_file())
            self.assertGreater(out.stat().st_size, 10000)
            out.unlink()


if __name__ == "__main__":
    unittest.main()
