"""cardgen engine: photo wants -> labels -> cast -> pipeline -> fullbleed attach.
Isolated temp DB, no network, no keys (generation and attach are injected)."""
import json
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from backend import config, db, photo_labels as PL, studio_library, subject_assets
from cardgen import engine as E, wants as W


def _photo(c, pid, owner, w=1000, h=1000):
    c.execute(
        "INSERT INTO photos (id,owner,sha256,r2_key,mime,width,height,bytes,"
        "orig_name,created_at,person,source) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
        (pid, owner, "sha" + pid, "k/" + pid, "image/jpeg", w, h, 10,
         pid + ".jpg", time.time(), "", "photo"))


def _face(c, fid, pid, box, score=0.9):
    c.execute("INSERT INTO photo_faces (id,photo_id,box,score,source) VALUES (?,?,?,?,?)",
              (fid, pid, json.dumps(box), score, "test"))


def _label(c, pid, fid, expression, framing="head_shoulders"):
    c.execute("INSERT OR REPLACE INTO photo_labels (photo_id,face_id,expression,framing,look,eyes_open,"
              "sharp,source,model,created_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
              (pid, fid, expression, framing, "frontal", 1, 0, "test", "", time.time()))


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.patches = [patch.object(config, "DATA", root), patch.object(config, "DB_PATH", root / "t.db")]
        for p in self.patches:
            p.start()
        db.init()
        studio_library.init()
        PL.ensure_schema()
        self.owner, self.sid = "pog_cardgen", "sub-dad"
        with db.connect() as c:
            c.execute("INSERT INTO studio_subjects VALUES (?,?,?,?,?)",
                      (self.sid, self.owner, "Chris", "person", time.time()))
            # happy solo close-up of Dad (tagged)
            _photo(c, "p-solo", self.owner, 1200, 1600)
            _face(c, "f-solo", "p-solo", [400, 300, 400, 500])
            _label(c, "p-solo", "f-solo", "happy")
            # shocked selfie of Dad (tagged)
            _photo(c, "p-shock", self.owner, 1536, 2048)
            _face(c, "f-shock", "p-shock", [500, 500, 600, 700])
            _label(c, "p-shock", "f-shock", "shocked")
            # couple: Dad + Cathy, both happy
            _photo(c, "p-couple", self.owner, 2048, 1536)
            _face(c, "f-c1", "p-couple", [300, 300, 300, 380])
            _face(c, "f-c2", "p-couple", [1200, 320, 300, 380])
            _label(c, "p-couple", "f-c1", "happy")
            _label(c, "p-couple", "f-c2", "laughing")
            # group of 4 with Dad
            _photo(c, "p-group", self.owner, 1600, 1200)
            for i in range(4):
                _face(c, f"f-g{i}", "p-group", [100 + 350 * i, 300, 160, 200])
                _label(c, "p-group", f"f-g{i}", "happy")
            for pid, fid in (("p-solo", "f-solo"), ("p-shock", "f-shock"),
                             ("p-couple", "f-c1"), ("p-group", "f-g1")):
                c.execute("INSERT INTO photo_subjects VALUES (?,?,?,1,?)", (pid, self.sid, fid, "user"))
            c.commit()

    def tearDown(self):
        for p in self.patches:
            p.stop()
        self.tmp.cleanup()


class WantsTest(unittest.TestCase):
    def test_describe_is_plain_words(self):
        self.assertEqual(W.describe({"shot": ["solo"], "expression": ["happy"]}), "a happy solo photo of them")

    def test_to_requires_feeds_product_selector(self):
        r = W.to_requires({"pair": {"shot": ["couple"], "expression": ["happy"]},
                           "x": {"shot": ["solo"], "optional": True}})
        self.assertEqual(r["couples"], 1)
        self.assertEqual(r["solos"], 0)
        self.assertEqual(r["emotions"], ["happy"])

    def test_implied_expressions(self):
        self.assertTrue(PL.satisfies("laughing", ["happy"]))
        self.assertTrue(PL.satisfies("shocked", ["expressive"]))
        self.assertFalse(PL.satisfies("neutral", ["happy"]))
        self.assertFalse(PL.satisfies("unknown", ["happy"]))
        self.assertTrue(PL.satisfies("unknown", []))

    def test_every_template_is_v2(self):
        for t in E.templates():
            self.assertIn("wants", t, t["id"])
            for k in t["qa"]["text_only"]:
                self.assertIn(k, t["copy"], t["id"])


class CastTest(Base):
    def test_each_template_casts_the_right_photo(self):
        idx = E.index(self.owner, self.sid, label=False)
        cast = {t["id"]: E.cast(t, idx) for t in E.templates()}
        self.assertEqual(cast["golf_lip_v1"]["roles"]["hero"], "p-solo")
        self.assertEqual(cast["comic_shock_v1"]["roles"]["hero"], "p-shock")
        self.assertEqual(cast["movie_poster_couple_v1"]["roles"]["pair"], "p-couple")
        self.assertEqual(cast["band_album_group_v1"]["roles"]["band"], "p-group")
        self.assertFalse(cast["pet_portrait_royal_v1"]["ok"])
        # group scenes get the hero's solos as extra likeness references
        self.assertIn("p-solo", cast["band_album_group_v1"]["refs"])

    def test_expression_gate_blocks_and_explains(self):
        with db.connect() as c:
            _label(c, "p-shock", "f-shock", "neutral")
            c.commit()
        rec = E.recommend(self.owner, self.sid, "birthday", {"interests": ["golf"]}, label=False)
        blocked = {b["template_id"]: b["shortfall"] for b in rec["blocked"]}
        self.assertIn("comic_shock_v1", blocked)
        self.assertIn("needs an expressive solo photo of them", blocked["comic_shock_v1"][0])
        self.assertEqual(rec["ready"][0]["template_id"], "golf_lip_v1")  # golf interest ranks first

    def test_untagged_owner_gets_tip(self):
        rec = E.recommend(self.owner, "sub-nobody", "birthday", {}, label=False)
        self.assertEqual(rec["ready"], [])
        self.assertTrue(rec["tip"])

    def test_selector_emotions_now_live(self):
        out = subject_assets.select_for_template(self.owner, {"couples": 1, "emotions": ["happy"]})
        self.assertEqual(out["slots"]["couple_1"]["photo_id"], "p-couple")
        self.assertFalse([s for s in out["shortfall"] if "reserved" in s])


class PipelineTest(Base):
    def test_job_end_to_end_with_injected_generation(self):
        from PIL import Image
        calls, attached = [], {}

        def gen(cap, prompt, refs):
            calls.append((cap, refs))
            size = (1600, 2240) if cap in ("identity_scene", "edit_fix", "upscale") else (1024, 1024)
            return Image.new("RGB", size, (240, 238, 230))

        def attach(blobs, copy, prompt):
            attached.update(blobs=blobs, copy=copy, prompt=prompt)
            return {"id": "card_test", "revision": 1}, [], []

        with E._db() as c:
            c.execute("INSERT INTO cardgen_jobs (id,owner,subject_id,template_id,status,created_at,updated_at)"
                      " VALUES ('cgj_t',?,?,?,'queued',0,0)", (self.owner, self.sid, "golf_lip_v1"))
            c.commit()
        with patch.object(E, "critic_gate", lambda img, exp: (True, "")), \
             patch.object(E, "face_gate", lambda img, v, n: (True, "")), \
             patch.object(E, "ocr_gate", lambda img, exp: (True, "")):
            E.run("cgj_t", self.owner, self.sid, "golf_lip_v1", {"recipient": "Dad", "sender": "Tom",
                                                                   "interests": ["golf"]}, {}, gen=gen, attach=attach)
        j = E.job(self.owner, "cgj_t")
        self.assertEqual(j["status"], "ready", j["error"])
        self.assertEqual(j["design_id"], "card_test")
        self.assertEqual(calls[0][0], "identity_scene")
        self.assertEqual(calls[0][1][0], "p-solo")                 # cast photo is the first reference
        self.assertEqual(attached["blobs"]["inside"].size, (2100, 1470))  # 10:7 spread art
        self.assertEqual(attached["copy"]["sender"], "Tom")
        self.assertIn("STILL ON THE LIP.", attached["prompt"])

    def test_qa_failure_triggers_fix_then_fails_closed(self):
        from PIL import Image
        calls = []

        def gen(cap, prompt, refs):
            calls.append(cap)
            return Image.new("RGB", (1600, 2240))

        with E._db() as c:
            c.execute("INSERT INTO cardgen_jobs (id,owner,subject_id,template_id,status,created_at,updated_at)"
                      " VALUES ('cgj_q',?,?,?,'queued',0,0)", (self.owner, self.sid, "golf_lip_v1"))
            c.commit()
        with patch.object(E, "critic_gate", lambda img, exp: (False, "stray tagline")), \
             patch.object(E, "face_gate", lambda img, v, n: (True, "")), \
             patch.object(E, "ocr_gate", lambda img, exp: (True, "")):
            E.run("cgj_q", self.owner, self.sid, "golf_lip_v1", {}, {}, gen=gen,
                  attach=lambda *a: self.fail("must not attach a failed card"))
        j = E.job(self.owner, "cgj_q")
        self.assertEqual(j["status"], "failed")
        self.assertEqual(calls.count("edit_fix"), 2)

    def test_start_is_fail_closed_without_key(self):
        with patch.dict("os.environ", {"FAL_KEY": ""}):
            with self.assertRaises(E.EngineError) as e:
                E.start(self.owner, self.sid, "golf_lip_v1")
        self.assertEqual(e.exception.code, 503)


if __name__ == "__main__":
    unittest.main()
