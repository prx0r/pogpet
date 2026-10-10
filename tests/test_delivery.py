"""Value/speed/balanced routing + order-by countdowns. Pure + mocked."""
import datetime as _dt
import unittest
from unittest.mock import patch
from zoneinfo import ZoneInfo

from backend import delivery as D


def _opt(supplier, total, lo=1, hi=3):
    return {"supplier": supplier, "grade": "LIVE", "total": total,
            "currency": "GBP", "dispatch": [lo, hi]}


class PicksTest(unittest.TestCase):
    def test_value_cheapest(self):
        p = D.pick([_opt("a", 10.44), _opt("b", 15.10)])
        self.assertEqual(p["value"]["supplier"], "a")

    def test_speed_quickest(self):
        p = D.pick([_opt("a", 5.0, lo=3, hi=5), _opt("b", 9.0, lo=1, hi=2)])
        self.assertEqual(p["speed"]["supplier"], "b")

    def test_balanced_best_ratio(self):
        # a: 10/5d = 2.0/day; b: 15/2d = 7.5/day → a wins on ratio
        p = D.pick([_opt("a", 10.0, lo=3, hi=5), _opt("b", 15.0, lo=1, hi=2)])
        self.assertEqual(p["balanced"]["supplier"], "a")

    def test_empty(self):
        self.assertEqual(D.pick([]), {})


class CountdownTest(unittest.TestCase):
    def test_open_mode_no_cutoff(self):
        # prodigi has no published cutoff: dispatch counted from now.
        # Mon 2026-10-12 10:00 UTC, window 1-2 bdays → Tue/Wed.
        now = _dt.datetime(2026, 10, 12, 10, 0, tzinfo=_dt.timezone.utc)
        c = D.countdown([1, 2], "prodigi", now)
        self.assertEqual(c["mode"], "open")
        self.assertEqual(c["dispatch_early"], "2026-10-13")
        self.assertEqual(c["dispatch_guaranteed"], "2026-10-14")

    def test_cutoff_before_close(self):
        # Fri 2026-10-09 15:00 London (UTC+1) → makes today's 16:00 cutoff.
        now = _dt.datetime(2026, 10, 9, 14, 0, tzinfo=_dt.timezone.utc)
        c = D.countdown([2, 5], "mixam", now)
        self.assertEqual(c["mode"], "cutoff")
        self.assertTrue(c["order_within"].startswith("1h"))
        self.assertIn("2026-10-09T16:00", c["cutoff_at"])

    def test_cutoff_after_close_rolls_to_monday(self):
        # Fri 17:00 London → next working day Monday.
        now = _dt.datetime(2026, 10, 9, 16, 0, tzinfo=_dt.timezone.utc)
        c = D.countdown([1, 2], "mixam", now)
        self.assertIn("2026-10-12T16:00", c["cutoff_at"])
        self.assertEqual(c["dispatch_early"], "2026-10-13")
        self.assertEqual(c["dispatch_guaranteed"], "2026-10-14")

    def test_weekend_skips(self):
        # Sat → Monday cutoff, dispatch Tue/Wed.
        now = _dt.datetime(2026, 10, 10, 12, 0, tzinfo=_dt.timezone.utc)
        c = D.countdown([1, 2], "moo", now)
        self.assertIn("2026-10-12T14:00", c["cutoff_at"])


class RoutesTest(unittest.TestCase):
    def test_greeting_card_lanes(self):
        def fake_quote(sku, copies=1, country="GB", attrs=None,
                       shipping_method="Standard"):
            if country == "US" and sku.startswith("CLASSIC"):
                raise Exception("NotAvailable")
            return {"currency": "GBP", "item": 1.0, "shipping": 2.0,
                    "tax": 0.0, "total": 3.0, "carrier": "RM",
                    "lab_country": country, "warnings": []}

        with patch("backend.prodigi.quote", side_effect=fake_quote):
            b = D.build("greeting_card", "US")
        live = [o for o in b["options"] if o["grade"] == "LIVE"]
        self.assertEqual([o["sku"] for o in live],
                         ["GLOBAL-GRE-MOH-7X5-BLA"])
        unav = [o for o in b["options"] if o.get("sku", "").startswith("CLASSIC")]
        self.assertEqual(unav[0]["grade"], "unavailable")
        staged = {o["supplier"] for o in b["options"]
                  if o["grade"] == "staged"}
        self.assertTrue({"mixam", "overnightprints", "moo", "gotprint"}
                        <= staged)
        self.assertIn("balanced", b["picks"])

    def test_unmapped_line_raises(self):
        with self.assertRaises(KeyError):
            D.build("mug", "GB")


if __name__ == "__main__":
    unittest.main()
