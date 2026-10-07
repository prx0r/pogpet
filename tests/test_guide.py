#!/usr/bin/env python3
"""Guide session unit tests — pure logic, no network, no credits.

    python3 -m unittest tests.test_guide -v

Covers ramble extraction (occasion/budget/name/interests), event countdowns,
and session persistence round-trip on a temp DB.
"""
from __future__ import annotations

import json
import sqlite3
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backend import guide  # noqa: E402


class TestExtract(unittest.TestCase):
    def test_budget(self):
        self.assertEqual(guide._extract_budget("under 25 dollars"), 2500)
        self.assertEqual(guide._extract_budget("about £30"), 3000)
        self.assertEqual(guide._extract_budget("no money talk"), 0)

    def test_occasion(self):
        self.assertEqual(guide._extract_occasion("His birthday"), "birthday")
        self.assertEqual(guide._extract_occasion("for Christmas"), "christmas")
        self.assertEqual(guide._extract_occasion("just because"), "just_because")

    def test_name(self):
        self.assertEqual(guide._extract_name("Shopping for my Dad"), "Dad")
        self.assertEqual(guide._extract_name("a gift for Sarah"), "Sarah")
        self.assertEqual(guide._extract_name("something nice"), "")

    def test_interests(self):
        self.assertIn("golf", guide._extract_interests("he likes golf and darts"))
        self.assertEqual(guide._extract_interests("nothing specific"), [])


class TestRamble(unittest.TestCase):
    def test_two_turn_flow(self):
        st = guide.blank_state()
        st, p1 = guide.ramble_turn(st, "Shopping for my Dad")
        self.assertEqual(st["recipient"]["name"], "Dad")
        self.assertIn("occasion", p1)
        st, p2 = guide.ramble_turn(st, "His birthday, under 25 dollars, he likes golf")
        self.assertEqual(st["occasion"], "birthday")
        self.assertEqual(st["budget_cents"], 2500)
        self.assertIn("golf", st["recipient"]["interests"])
        self.assertIn("photos", p2)

    def test_birthday_event_countdown(self):
        st = guide.blank_state()
        st["recipient"] = {"name": "Dad", "interests": [], "birthday": "11-14", "mesh_id": ""}
        evs = guide.compute_events(st)
        self.assertTrue(any(e["kind"] == "birthday" and e["days_left"] >= 0 for e in evs))

    def test_christmas_event(self):
        st = guide.blank_state()
        st["occasion"] = "christmas"
        evs = guide.compute_events(st)
        self.assertTrue(any(e["kind"] == "christmas" for e in evs))


class TestCorrections(unittest.TestCase):
    def test_negation_moves_to_dislikes(self):
        st = guide.blank_state()
        guide.apply_turn(st, "Dad loves golf")
        self.assertIn("golf", st["recipient"]["interests"])
        guide.apply_turn(st, "actually he hates golf")
        self.assertNotIn("golf", st["recipient"]["interests"])
        self.assertIn("golf", st["recipient"]["dislikes"])

    def test_recipient_switch_retires_facts(self):
        st = guide.blank_state()
        guide.apply_turn(st, "Shopping for Dad, he likes golf")
        guide.apply_turn(st, "now shopping for Mum")
        rec = st["recipient"]
        self.assertEqual(rec["name"], "Mum")
        self.assertEqual(rec["interests"], [])
        self.assertEqual(rec["dislikes"], [])

    def test_delivery_deadline_and_destination(self):
        st = guide.blank_state()
        guide.apply_turn(st, "need it by 2026-11-14, ship to Leeds")
        self.assertEqual(st["delivery"]["deadline"], "2026-11-14")
        self.assertEqual(st["delivery"]["destination"], "Leeds")
        kinds = [e["kind"] for e in st["events"]]
        self.assertIn("delivery", kinds)
        self.assertNotIn("birthday", [e["kind"] for e in st["events"]
                                      if e.get("destination") == "unknown"
                                      and st["recipient"]["birthday"] == ""])

    def test_iso_date_is_not_birthday(self):
        st = guide.blank_state()
        guide.apply_turn(st, "need it by 2026-11-14")
        self.assertEqual(st["recipient"]["birthday"], "")
        st2 = guide.blank_state()
        guide.apply_turn(st2, "her birthday is 11-14")
        self.assertEqual(st2["recipient"]["birthday"], "11-14")


class TestPrompts(unittest.TestCase):
    def test_one_at_a_time_with_cooldown(self):
        st = guide.blank_state()
        st["recipient"]["name"] = "Dad"
        p1 = guide.next_prompt(st, now_ts=1000.0)
        self.assertEqual(p1["key"], "occasion")
        self.assertIn("Birthday", p1["taps"])
        # same key cools down: next call moves on, never repeats occasion
        keys = {p1["key"]}
        for t in (1001.0, 1002.0, 1003.0):
            p = guide.next_prompt(st, now_ts=t)
            if p:
                self.assertNotIn(p["key"], keys)
                keys.add(p["key"])
                guide.answer_prompt(st, p["key"])
        guide.answer_prompt(st, "occasion")
        st["occasion"] = "birthday"
        p3 = guide.next_prompt(st, now_ts=2000.0)
        self.assertEqual(p3["key"], "budget")

    def test_revision_and_feed(self):
        st = guide.blank_state()
        r0 = st["revision"]
        guide.apply_turn(st, "Shopping for Dad")
        self.assertGreater(st["revision"], r0)
        self.assertTrue(any(e["type"] == "profile.updated" for e in st["feed"]))


class TestStore(unittest.TestCase):
    def test_round_trip(self):
        from backend import db
        c = sqlite3.connect(":memory:")
        c.row_factory = sqlite3.Row
        c.executescript(db.SCHEMA)
        sid = guide.new_id()
        st = guide.blank_state()
        st["recipient"]["name"] = "Mum"
        db_target = c
        guide.save_session(db_target, sid, "anon", "photos", st)
        got = guide.get_session(db_target, sid, "anon")
        self.assertEqual(got["stage"], "photos")
        self.assertEqual(got["state"]["recipient"]["name"], "Mum")
        self.assertIsNone(guide.get_session(db_target, "nope", "anon"))


if __name__ == "__main__":
    unittest.main()
