"""Value/speed/balanced routing + order-by countdowns. Pure + mocked."""
import datetime as _dt
import json as _json
import unittest
from unittest.mock import patch
from zoneinfo import ZoneInfo

from backend import delivery as D
from backend import config as _config
from backend.server import app as _app


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


def _quote_for(sku):
    def fake(sku_arg, copies=1, country="GB", attrs=None, shipping_method="Standard"):
        assert sku_arg == sku
        ship = 8.60 if shipping_method == "Express" else 0.95
        carrier = "Royal Mail Signed For" if shipping_method == "Express" else "Guernsey Post"
        return {"currency": "GBP", "item": 1.10, "shipping": ship, "tax": 0.0,
                "total": 1.10 + ship, "carrier": carrier,
                "lab_country": country, "warnings": []}
    return fake


class CardDeliveryTest(unittest.TestCase):
    def setUp(self):
        import tempfile
        from pathlib import Path
        from unittest.mock import patch as _p
        from backend import config, db
        from backend import cards as _cards
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.patches = [patch.object(config, "DATA", root),
                        patch.object(config, "DB_PATH", root / "test.db")]
        for p in self.patches:
            p.start()
        db.init()
        _cards.init()
        self.owner = "pog_deliverytests"
        self.headers = {"X-API-Token": config.API_TOKEN,
                        "X-Owner-Sig": config.sign_owner(self.owner)}
        self.client = _app.test_client()
        with db.connect() as c:
            c.execute("INSERT INTO card_designs (id,owner,latest,created_at,updated_at,storage_owner,via) VALUES (?,?,?,?,?,?,?)",
                      ("card_t1", self.owner, 1, 1.0, 1.0, self.owner, "ui"))
            c.execute("INSERT INTO card_revisions VALUES (?,?,?,?)",
                      ("card_t1", 1, _cards.json_dump(
                          {"template": "typography", "format": "5x7",
                           "headline": "Hi", "recipient": "", "sender": "",
                           "inside_message": "x", "photos": []}), 1.0))

    def tearDown(self):
        for p in reversed(self.patches):
            p.stop()
        self.tmp.cleanup()

    def test_charge_policy(self):
        self.assertEqual(D.shipping_charge(0.95), 149)
        self.assertEqual(D.shipping_charge(8.60), 949)

    def test_endpoint_value_speedy_opaque(self):
        with patch("backend.prodigi.quote",
                   side_effect=_quote_for("CLASSIC-GRE-FEDR-7X5-BLA")):
            r = self.client.get("/api/cards/card_t1/delivery?revision=1&country=GB&token=" + _config.API_TOKEN + "&owner=" + self.owner,
                                headers=self.headers)
        self.assertEqual(r.status_code, 200, r.json)
        d = r.json
        self.assertEqual(d["value"]["price_cents"], 149)
        self.assertEqual(d["speedy"]["price_cents"], 949)
        self.assertTrue(d["value"]["arrival_from"] <= d["value"]["arrival_to"])
        self.assertTrue(d["speedy"]["arrival_to"] <= d["value"]["arrival_to"])
        body = _json.dumps(d["value"]) + _json.dumps(d["speedy"])
        self.assertNotIn("prodigi", body.lower())
        self.assertNotIn("CLASSIC", body)
        self.assertNotEqual(d["value"]["id"], d["speedy"]["id"])
        self.assertTrue(d["value"]["id"].startswith("do_"))

    def test_fulfil_route_precedence(self):
        from backend.server import _fulfil_route
        self.assertEqual(_fulfil_route({"shipping_method": "Standard"})[0], "Standard")
        self.assertEqual(_fulfil_route({"shipping_method": "Express"})[0], "Express")
        self.assertEqual(
            _fulfil_route({"shipping_method": "Standard"},
                          {"shipping_method": "Express"})[0], "Express")

    def test_checkout_persists_option(self):
        from backend import cards as _cards
        route = {"supplier": "prodigi", "sku": "S", "shipping_method": "Express",
                 "supplier_ship": 8.6, "carrier": "RM"}
        with patch("backend.prodigi.quote",
                   side_effect=_quote_for("CLASSIC-GRE-FEDR-7X5-BLA")):
            saved = _cards.save_delivery_option(
                self.owner, "card_t1", 1, "GB", route, 949,
                "2026-10-13", "2026-10-14")
            r = self.client.post("/api/cards/card_t1/checkout?token=" + _config.API_TOKEN,
                                 json={"owner": self.owner, "revision": 1, "qty": 1,
                                       "idempotency_key": "test-dopt-12345678",
                                       "delivery_option_id": saved["id"]},
                                 headers=self.headers)
        # Shopify not configured in tests → 502, but the frozen row must carry the route
        self.assertEqual(r.status_code, 502, r.json)
        from backend import db
        with db.connect() as c:
            row = dict(c.execute("SELECT shipping_method, delivery_option_id FROM card_orders WHERE idempotency_key=?",
                                 ("test-dopt-12345678",)).fetchone())
        self.assertEqual(row["shipping_method"], "Express")
        self.assertEqual(row["delivery_option_id"], saved["id"])
        # unknown option id → hard 400, never silent Standard
        r = self.client.post("/api/cards/card_t1/checkout?token=" + _config.API_TOKEN,
                             json={"owner": self.owner, "revision": 1, "qty": 1,
                                   "idempotency_key": "test-dopt2-12345678",
                                   "delivery_option_id": "do_nope"},
                             headers=self.headers)
        self.assertEqual(r.status_code, 400)


if __name__ == "__main__":
    unittest.main()
