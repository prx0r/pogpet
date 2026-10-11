"""Template library rules: solo floor per occasion, interest gating, pet casting."""
import unittest
from unittest import mock

from cardgen import engine as E


def _face(h=300, expr="neutral"):
    return {"id": "f", "box": (100, 100, h, h), "h_px": h, "score": 0.9, "hero": True,
            "labels": {"expression": expr, "framing": "head_shoulders", "look": "front"}}


SOLO = {"photos": [{"id": "p1", "w": 1200, "h": 1600, "created_at": 1, "faces": [_face()], "tagged": True}],
        "hero_vecs": [], "hero_faces": 1}
PET = {"photos": [{"id": "d1", "w": 1000, "h": 1300, "created_at": 1, "faces": [], "tagged": True},
                  {"id": "d2", "w": 300, "h": 300, "created_at": 2, "faces": [], "tagged": True}],
       "hero_vecs": [], "hero_faces": 0}


def _ready(idx, occ, prof):
    with mock.patch.object(E, "index", return_value=idx):
        return [r["template_id"] for r in E.recommend("o", "s", occ, prof)["ready"]]


class TemplateLibrary(unittest.TestCase):
    def test_all_templates_valid(self):
        for t in E.templates():
            for k in ("id", "occasions", "interests", "tones", "style", "scene", "copy", "qa", "wants", "format"):
                self.assertIn(k, t, t.get("id"))
            for key in t["qa"]["text_only"]:
                self.assertIn(key, t["copy"], t["id"])
            for k, v in t["copy"].items():
                for e in v["examples"]:
                    e = e.replace("{recipient}", "Dad").replace("{pet_name}", "Rex").replace("{NAME}", "CHRIS").replace("{SURNAME}", "PRIOR")
                    self.assertLessEqual(len(e), v["max"], (t["id"], k, e))

    def test_one_neutral_solo_photo_covers_the_solo_occasions(self):
        for occ in ("birthday", "christmas", "fathers_day", "mothers_day", "retirement"):
            self.assertTrue(_ready(SOLO, occ, {}), occ)

    def test_interest_led_templates_need_the_interest(self):
        plain = _ready(SOLO, "birthday", {})
        self.assertNotIn("solo_fishing_tall_tale_v1", plain)
        self.assertNotIn("golf_lip_v1", plain)
        fisher = _ready(SOLO, "birthday", {"interests": ["Carp fishing"]})
        self.assertEqual(fisher[0], "solo_fishing_tall_tale_v1")
        self.assertNotIn("solo_bbq_inferno_v1", fisher)

    def test_pet_subject_gets_pet_templates_only(self):
        got = _ready(PET, "birthday", {"kind": "pet"})
        self.assertIn("pet_party_hat_v1", got)
        self.assertTrue(all(E.is_pet_template(E.template(t)) for t in got))
        self.assertTrue(all(not E.is_pet_template(E.template(t)) for t in _ready(SOLO, "birthday", {})))

    def test_pet_cast_picks_biggest_tagged_faceless_photo(self):
        c = E.cast(E.template("pet_party_hat_v1"), PET)
        self.assertTrue(c["ok"])
        self.assertEqual(c["roles"]["pet"], "d1")
        self.assertNotIn("d2", c["refs"])  # below PET_MIN_SIDE

    def test_pet_with_no_photo_says_what_it_needs(self):
        c = E.cast(E.template("pet_party_hat_v1"), {"photos": [], "hero_vecs": [], "hero_faces": 0})
        self.assertFalse(c["ok"])
        self.assertIn("pet", c["shortfall"][0])


class Gates(unittest.TestCase):
    def test_bleed_gate_flags_a_card_mockup_frame(self):
        from PIL import Image, ImageDraw
        art = Image.new("RGB", (700, 980), (40, 90, 60))
        self.assertTrue(E.bleed_gate(art)[0])
        framed = Image.new("RGB", (700, 980), (250, 250, 250))
        ImageDraw.Draw(framed).rectangle((30, 40, 670, 950), fill=(40, 90, 60))
        ok, why = E.bleed_gate(framed)
        self.assertFalse(ok)
        self.assertIn("top", why)

    def test_surname_never_falls_back_to_a_first_name(self):
        self.assertEqual(E.write_copy(E.template("xmas_family_v1"), {"name": "Chris"})["sub"], "from all of us")
        self.assertEqual(E.write_copy(E.template("band_album_group_v1"), {"name": "Chris Prior"})["title"], "THE PRIORS")


if __name__ == "__main__":
    unittest.main()
