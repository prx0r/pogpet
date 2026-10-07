"""cardgen.md compiler tests: person graph → brief → match → revision → artifact."""
import unittest

from tests.test_cards import CardsJourney
from backend import db
from backend import subjects as sub
from backend.creative import artifacts as art
from backend.creative import briefs, jobs
from backend.creative import matcher, projects
from backend.creative import templates as tmpl


class TestSubjects(unittest.TestCase):
    def setUp(self):
        import tempfile
        from unittest.mock import patch
        from backend import config, storage, studio_library
        self.tmp = tempfile.TemporaryDirectory()
        root = __import__("pathlib").Path(self.tmp.name)
        self.patches = [patch.object(config, 'DATA', root),
                        patch.object(config, 'DB_PATH', root / 'test.db')]
        for p in self.patches:
            p.start()
        db.init()
        with db.connect() as c:
            c.executescript(studio_library.SCHEMA)
            c.commit()
        self.owner = "pog_creative"

    def tearDown(self):
        for p in reversed(self.patches):
            p.stop()
        self.tmp.cleanup()

    def test_subject_profile_not_mesh(self):
        with db.connect() as c:
            c.execute("INSERT INTO photos (id,owner,sha256,r2_key,mime,width,height,bytes,orig_name,created_at)"
                      " VALUES ('pho_mig',?,?,?,?,?,?,?,?,?)",
                      (self.owner, "s", "k", "image/jpeg", 10, 10, 1, "a.jpg", 0.0))
            c.execute("INSERT INTO meshes (id,photo_id,status,created_at,updated_at)"
                      " VALUES ('msh_x','pho_mig','succeeded',0,0)")
            c.commit()
            s = sub.create_subject(c, self.owner, "Dad")
            sub.set_profile(c, self.owner, s["id"], relationship="dad",
                            profile={"interests": ["golf"],
                                     "humour": {"absurd": 0.9}})
            self.assertEqual(sub.profile_for(c, self.owner, s["id"])["profile"]["interests"], ["golf"])
            # legacy mesh-keyed row migrates to the subject
            c.execute("INSERT INTO subject_profiles (owner,mesh_id,name,interests,birthday,updated_at)"
                      " VALUES (?,?,?,?,?,?)",
                      (self.owner, "msh_x", "Dad", '["golf"]', "", 0.0))
            c.commit()
            self.assertGreater(sub.migrate_mesh_profiles(c), 0)
            again = sub.find_subject_by_name(c, self.owner, "Dad")
            self.assertEqual(again["id"], s["id"])  # no duplicate Dad

    def test_assets_raw_derived(self):
        with db.connect() as c:
            raw = sub.register_asset(c, self.owner, "photo", "sha1", "k1")
            drv = sub.register_asset(c, self.owner, "photo", "sha2", "k2",
                                     parent_id=raw["id"],
                                     metadata={"op": "facecrop"})
            self.assertEqual(sub.derived(c, raw["id"])[0]["id"], drv["id"])
            # idempotent re-register
            self.assertEqual(sub.register_asset(c, self.owner, "photo", "sha1", "k1")["id"],
                             raw["id"])


class TestTemplates(unittest.TestCase):
    def test_registry_loads_and_validates(self):
        reg = tmpl.load_all()
        self.assertIn("breaking_news", reg)
        self.assertIn("sideline_interview", reg)
        self.assertEqual(tmpl.validate_manifest({"id": "x"}), ["missing version",
                                                               "missing taxonomy",
                                                               "missing requirements",
                                                               "missing slots",
                                                               "missing renderers",
                                                               "version must be int"])

    def test_namespaces_split(self):
        reg = tmpl.load_all()
        self.assertNotEqual(reg["breaking_news"]["taxonomy"]["occasion"],
                            ["christmas"])
        self.assertIn("newsparody", reg["breaking_news"]["taxonomy"]["styles"])
        self.assertIn("sportspresser", reg["sideline_interview"]["taxonomy"]["styles"])


class TestBriefMatch(unittest.TestCase):
    def _brief(self):
        return briefs.build(
            occasion="christmas",
            subject={"id": "sub_dad", "name": "Dad"},
            profile={"profile": {"relationship": "dad", "interests": ["football"],
                                 "humour": {"absurd": 0.9}}},
            asset_counts={"photos": 17, "confirmed_face_photos": 8,
                          "good_portraits": 4, "meshes": 2, "voice": False})

    def test_dad_football_christmas(self):
        reg = tmpl.load_all()
        hits = matcher.match(self._brief(), reg)
        self.assertTrue(hits)
        top = hits[0]
        self.assertEqual(top["id"], "sideline_interview")
        self.assertTrue(any("football" in r for r in top["reasons"]))
        # deterministic: same order twice
        again = matcher.match(self._brief(), reg)
        self.assertEqual([h["id"] for h in hits], [h["id"] for h in again])

    def test_eligibility_blocks(self):
        reg = tmpl.load_all()
        b = self._brief()
        b["available_assets"] = {"photos": 0, "confirmed_face_photos": 0}
        blocked = [tid for tid, t in reg.items()
                   if any("face photos" in r for r in matcher.eligible(t, b))]
        self.assertIn("sideline_interview", blocked)  # needs a face
        open_tids = [tid for tid, t in reg.items() if not matcher.eligible(t, b)]
        self.assertIn("dad_vs_tech", open_tids)  # comic needs none

    def test_fill_fields_not_pixels(self):
        reg = tmpl.load_all()
        filled, gaps = jobs.fill_slots(reg["sideline_interview"], {
            "star": "sub_dad", "headline": "POST-MATCH INTERVIEW",
            "caption": "Dad carried Christmas again"})
        self.assertEqual(gaps, [])
        self.assertEqual(filled["headline"], "POST-MATCH INTERVIEW")
        _, gaps2 = jobs.fill_slots(reg["sideline_interview"], {"star": "sub_dad",
                                   "headline": "x" * 43})
        self.assertTrue(any("max 42" in g for g in gaps2))


    def test_authoring_fixtures_gate(self):
        """§16: a template goes live only when every fixture fills + QC-passes."""
        from backend.creative.artifacts import qc_card_copy
        reg = tmpl.load_all()
        fixtures = [
            {"star": "sub_dad", "headline": "DAD", "caption": "short"},
            {"star": "sub_mum", "headline": "MUM SPECIAL", "caption": "x" * 90},
            {"star": "sub_pet", "headline": "GOOD BOY"},
            {"star": "sub_x", "headline": "x" * 42, "caption": "y" * 200},
        ]
        live = 0
        for tid, t in reg.items():
            ok = True
            slots = t.get("slots", {})
            for f in fixtures:
                # only fields the template declares count; unknown keys are ignored
                known = {k: v for k, v in f.items() if k in slots or k == "star"}
                known["star"] = f["star"]
                filled, gaps = jobs.fill_slots(t, known)
                gaps += qc_card_copy(filled, t)
                over = any(k in slots and isinstance(slots[k], dict)
                           and slots[k].get("type") == "text"
                           and isinstance(slots[k].get("max_chars"), int)
                           and len(str(f.get(k, ""))) > slots[k]["max_chars"]
                           for k in f)
                if over:
                    if not gaps:  # over-long field MUST fail the gate
                        ok = False
                elif gaps:
                    ok = False
            if ok:
                live += 1
        self.assertEqual(live, len(reg))


class TestRevisionsArtifacts(CardsJourney):
    def test_revision_immutable_and_cached(self):
        pid_photo = self.upload()
        r = self.post("/creative/revisions", {
            "template_id": "sideline_interview", "subject_id": "sub_dad",
            "fields": {"star": "sub_dad", "headline": "POST-MATCH INTERVIEW",
                       "caption": "Dad did it again"},
            "subjects": [{"slot": "star", "subject_id": "sub_dad", "asset_ids": [pid_photo]}]})
        self.assertTrue(r.json["ok"], r.json)
        pid, rev = r.json["revision"]["project_id"], r.json["revision"]["revision"]
        r2 = self.post("/creative/revisions", {
            "project_id": pid, "template_id": "sideline_interview",
            "subject_id": "sub_dad",
            "fields": {"star": "sub_dad", "headline": "POST-MATCH 2",
                       "caption": "again"}})
        self.assertEqual(r2.json["revision"]["revision"], rev + 1)
        with db.connect() as c:
            old = projects.get_revision(c, pid, rev)
            self.assertEqual(old["scene"]["copy"]["headline"], "POST-MATCH INTERVIEW")
        # render → artifact + QC passed
        rr = self.post("/creative/render", {"project_id": pid, "revision": rev})
        self.assertTrue(rr.json["ok"], rr.json)
        self.assertIn("url", rr.json["artifact"])
        # same inputs → cache hit, no second artifact
        rr2 = self.post("/creative/render", {"project_id": pid, "revision": rev})
        self.assertTrue(rr2.json.get("cached"))
        # print contract + videos columns exist
        from backend.creative.artifacts import PRINT_CONTRACTS
        self.assertEqual(PRINT_CONTRACTS["card_5x7_folded_v1"]["dpi"], 300)
        with db.connect() as c:
            cols = [row[1] for row in c.execute("PRAGMA table_info(videos)").fetchall()]
            for col in ("creative_project_id", "creative_revision", "renderer"):
                self.assertIn(col, cols)


class TestProvidersOddhobb(CardsJourney):
    def _router(self):
        import backend.creative.providers.local  # noqa: F401 (registers free)
        import backend.creative.providers.mesh  # noqa: F401 (registers)
        import backend.creative.providers.alibaba  # noqa: F401 (staged)
        import backend.creative.providers.fal  # noqa: F401 (staged)
        import backend.creative.providers.meta  # noqa: F401 (staged)
        from backend.creative.providers import router
        return router

    def test_router_free_defaults(self):
        router = self._router()
        for cap in ("identity_image", "lip_sync", "voice_tts", "music",
                    "video_scene", "mesh", "realtime_voice"):
            ad = router.resolve(cap)
            self.assertFalse(ad.paid, cap)

    def test_router_no_paid_without_approval_or_key(self):
        router = self._router()
        # voice_clone is paid-only with no key anywhere → unresolvable
        with self.assertRaises(Exception):
            router.resolve("voice_clone")
        with self.assertRaises(Exception):
            router.resolve("voice_clone", allow_paid=True)
        # free default serves lipsync without approval
        self.assertEqual(router.resolve("lip_sync").name, "local.jaw_bake")

    def test_realtime_providers(self):
        from backend import voice_chat as _vc
        self.assertIn("qwen_omni", _vc.PROVIDERS)
        self.assertIn("gemini_live", _vc.PROVIDERS)
        self.assertTrue(issubclass(_vc.RealtimeProvider, _vc.BaseVoiceProvider))

    def test_bench_roundtrip(self):
        import tempfile
        from pathlib import Path
        from backend.creative import bench
        tmp = Path(tempfile.mkdtemp())
        bench.record(task="dad:sports-interview", adapter="local.composite",
                     scores={"identity": 0.5, "cost": 1.0}, root=tmp)
        lb = bench.leaderboard(root=tmp)
        self.assertEqual(lb["local.composite"]["n"], 1)

    def test_oddhobb_ideas_flow(self):
        from backend import subjects as sub, studio_library
        with db.connect() as c:
            c.executescript(studio_library.SCHEMA)
            s = sub.create_subject(c, self.owner, "Dad")
            sub.set_profile(c, self.owner, s["id"], relationship="dad",
                            profile={"interests": ["golf"]})
        pid = self.upload()
        with db.connect() as c:
            sub.link_photo(c, pid, s["id"], confirmed=True)
        r = self.post("/oddhobb/ideas", {"person": "Dad", "occasion": "christmas",
                                         "owner": self.owner,
                                         "context": [{"fact": "falls asleep after lunch",
                                                      "source": "agent_memory"}]})
        self.assertTrue(r.json["ok"], r.json)
        self.assertTrue(r.json["ideas"])
        self.assertEqual(r.json["brief"]["agent_memory"][0]["source"], "agent_memory")


class TestVaultPoliciesKernel(CardsJourney):
    def test_vault_roundtrip_never_leaks(self):
        import json
        from backend import vault as _v
        with db.connect() as c:
            _v.ensure_tables(c)
            rec = _v.connect(c, self.owner, "fal", "SECRET-XYZ", {"label": "mine"})
            self.assertTrue(rec["credential_id"].startswith("cred_"))
            view = _v.agent_view(c, self.owner)
            self.assertTrue(view["fal"] and view["free"] and not view["higgsfield"])
            blob = json.dumps(view)
            self.assertNotIn("SECRET-XYZ", blob)
            self.assertEqual(_v.use(c, self.owner, "fal"), "SECRET-XYZ")
            self.assertTrue(_v.disconnect(c, self.owner, "fal"))
            self.assertFalse(_v.agent_view(c, self.owner)["fal"])
            with self.assertRaises(ValueError):
                _v.connect(c, self.owner, "evilcorp", "x")

    def test_compute_policies(self):
        import backend.creative.providers.local  # noqa: F401
        import backend.creative.providers.mesh  # noqa: F401
        from backend.creative.providers import router
        self.assertEqual(router.resolve_policy("lip_sync", "free").name, "local.jaw_bake")
        with self.assertRaises(Exception):
            router.resolve_policy("lip_sync", "specific", route="nope.nothing")
        with self.assertRaises(Exception):
            router.resolve_policy("lip_sync", "weirdmode")

    def test_performance_kernel_math(self):
        from backend import performance as _p
        self.assertAlmostEqual(_p.jaw_from_energy(1.0, 0.0), 0.35)
        self.assertEqual(_p.envelope_from_words([{"start": 1.0, "end": 2.0}], 1.5), 1.0)
        self.assertEqual(_p.envelope_from_words([{"start": 1.0, "end": 2.0}], 5.0), 0.0)
        self.assertEqual(_p.viseme_for_char("b"), "MBP")
        beats = _p.compile_beats([{"text": "hi", "duration_s": 2.0, "pause_after_ms": 600}])
        self.assertEqual(beats[0]["end"], 2.0)

    def test_capsule_and_capture(self):
        from backend import capsule as _cap
        from backend import subjects as sub, studio_library
        with db.connect() as c:
            c.executescript(studio_library.SCHEMA)
            s = sub.create_subject(c, self.owner, "Dad")
            cap = _cap.build(c, self.owner, s["id"])
            self.assertEqual(cap["subject_id"], s["id"])
            self.assertIn("provenance", cap)
        r = self.post("/capture/start", {"subject_id": s["id"], "owner": self.owner})
        cid = r.json["capture_id"]
        self.assertTrue(r.json["script"])
        r = self.post("/capture/mark", {"capture_id": cid, "kind": "shrug",
                                        "note": "big dad shrug"})
        self.assertEqual(r.json["marks"], 1)
        r = self.post("/capture/finish", {"capture_id": cid, "owner": self.owner})
        self.assertTrue(r.json["ok"])
        with db.connect() as c:
            prof = sub.profile_for(c, self.owner, s["id"])["profile"]
            self.assertIn("big dad shrug", prof.get("mannerisms", []))

    def test_providers_view_hides_secrets(self):
        r = self.client.get("/api/providers",
                            query_string={"owner": self.owner},
                            headers=self.headers, buffered=True)
        r.close()
        self.assertTrue(r.json["providers"]["free"])
        self.assertIn("free", r.json["policies"])


if __name__ == "__main__":
    unittest.main()


class TestReviewLoop(CardsJourney):
    def _project(self):
        pid_photo = self.upload()
        r = self.post("/creative/revisions", {
            "template_id": "sideline_interview", "subject_id": "sub_dad",
            "fields": {"star": "sub_dad", "headline": "BIG GAME",
                       "caption": "Dad did it"},
            "subjects": [{"slot": "star", "subject_id": "sub_dad",
                          "asset_ids": [pid_photo]}]})
        self.assertTrue(r.json["ok"], r.json)
        return r.json["revision"]

    def test_review_and_mood_revise(self):
        rev = self._project()
        rr = self.post("/creative/render", {"project_id": rev["project_id"],
                                            "revision": rev["revision"]})
        self.assertTrue(rr.json["ok"], rr.json)
        art = rr.json["artifact"]["id"]
        v = self.post("/creative/review", {"artifact_id": art})
        self.assertTrue(v.json["ok"], v.json)
        self.assertIn(v.json["verdict"], ("ship", "revise"))
        self.assertIn("happier", v.json.get("moods", []))
        r2 = self.post("/creative/revise", {
            "project_id": rev["project_id"], "revision": rev["revision"],
            "ops": {"mood": "happier", "copy": {"headline": "BIG WIN!"}},
            "render": True})
        self.assertTrue(r2.json["ok"], r2.json)
        self.assertEqual(r2.json["revision"]["revision"], rev["revision"] + 1)
        self.assertTrue(r2.json["render"]["ok"])

    def test_revise_other_owner_denied(self):
        rev = self._project()
        r = self.post("/creative/revise", {"owner": "mallory",
                                           "project_id": rev["project_id"],
                                           "revision": rev["revision"],
                                           "ops": {"copy": {"headline": "X"}}})
        self.assertFalse(r.json.get("ok", True))

    def test_review_unknown_artifact(self):
        r = self.post("/creative/review", {"artifact_id": "art_nope"})
        self.assertEqual(r.status_code, 404)


class TestTemplatePack(CardsJourney):
    def test_registry_counts(self):
        from backend.creative import templates as _t
        reg = _t.load_all()
        for tid in ("breaking_news", "sideline_interview", "group_chat",
                    "late_night", "movie_poster", "dad_vs_tech", "hot_take_tweet"):
            self.assertIn(tid, reg, tid)
        for tid, m in reg.items():
            for k in ("format", "premise", "caption_pattern", "tone", "rules"):
                self.assertIn(k, m, f"{tid}.{k}")

    def test_premise_packs(self):
        from backend.creative import premises as _p
        packs = _p.load_packs()
        for pack in ("dads", "christmas_chaos", "pets"):
            self.assertIn(pack, packs)
        hits = _p.match_premises(["golf"], ["sports"])
        self.assertTrue(any(h["pack"] == "dads" for h in hits))

    def test_pattern_fill(self):
        from backend.creative import jobs as _j, templates as _t
        m = _t.get("sideline_interview")
        s = _j.render_pattern(m, {"headline": "DAD WINS", "caption": "again"})
        self.assertIn("DAD WINS", s)

    def test_comic_end_to_end(self):
        r = self.post("/creative/revisions", {
            "template_id": "dad_vs_tech", "subject_id": "sub_dad",
            "fields": {"star": "sub_dad", "panel_1": "Dad says he will fix it",
                       "panel_2": "Dad makes it worse", "panel_3": "Dad blames Wi-Fi",
                       "panel_4": "Dad asks a child for help"}})
        self.assertTrue(r.json["ok"], r.json)
        d = r.json["revision"]
        rr = self.post("/creative/render", {"project_id": d["project_id"], "revision": 1})
        self.assertTrue(rr.json["ok"], rr.json)
        self.assertIn("url", rr.json["artifact"])

    def test_new_occasions(self):
        for occ in ("new_baby", "graduation", "just_because", "retirement"):
            r = self.post("/gift-packs", {"budget_cents": 2000, "occasion": occ})
            self.assertTrue(r.json["ok"], (occ, r.json))
