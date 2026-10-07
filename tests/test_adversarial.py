"""Adversarial tests: cross-owner isolation, collisions, consent, leakage."""
import unittest

from tests.test_cards import CardsJourney
from backend import db


class TestAdversarial(CardsJourney):
    def _other(self):
        return "pog_adversary"

    def test_cross_owner_people_denied(self):
        r = self.client.get("/api/oddhobb/people", query_string={"owner": "someone_else"},
                            headers=self.headers, buffered=True)
        r.close()
        self.assertEqual(r.status_code, 403)

    def test_cross_owner_capsule_denied(self):
        r = self.client.get("/api/capsule/sub_x?owner=someone_else",
                            headers=self.headers, buffered=True)
        r.close()
        self.assertEqual(r.status_code, 403)

    def test_cross_owner_status_denied(self):
        r = self.client.get("/api/oddhobb/status/crp_nope?owner=someone_else",
                            headers=self.headers, buffered=True)
        r.close()
        self.assertEqual(r.status_code, 403)

    def test_cross_owner_providers_denied(self):
        r = self.client.get("/api/providers",
                            query_string={"owner": "someone_else"},
                            headers=self.headers, buffered=True)
        r.close()
        self.assertEqual(r.status_code, 403)

    def test_cache_collision_across_owners(self):
        from backend.creative import artifacts as _art
        scene = {"template": {"id": "sideline_interview", "version": 1},
                 "copy": {"headline": "SAME JOKE"}}
        k1 = _art.content_key(scene=scene, renderer="composite2d",
                              renderer_version=1, output_contract="print_master",
                              provider_params={})
        k2 = _art.content_key(scene={**scene, "copy": {"headline": "OTHER JOKE"}},
                              renderer="composite2d", renderer_version=1,
                              output_contract="print_master", provider_params={})
        self.assertNotEqual(k1, k2)  # different scenes never share keys
        with db.connect() as c:
            _art.ensure_tables(c)
            a = _art.record(c, "alice", "p1", 1, "composite2d", "print_master",
                            k1, "k", mime="image/png")
            _art.mark_qc(c, a["id"], True)
            # same content, other owner: lookup is owner-scoped
            self.assertEqual(_art.by_cache(c, k1, "bob"), {})
            self.assertTrue(_art.by_cache(c, k1, "alice"))

    def test_bogus_consent_rejected(self):
        from backend import voice_chat as _vc
        with db.connect() as c:
            _vc.ensure_consent_tables(c)
            for bad in ("lol", "", "vcs_nope"):
                with self.assertRaises(_vc.VoiceError):
                    _vc.check_consent(c, bad, owner="x", subject_id="y", op="tts")

    def test_consent_scope_and_revoke(self):
        from backend import voice_chat as _vc
        import time
        with db.connect() as c:
            _vc.ensure_consent_tables(c)
            c.execute("INSERT INTO voice_consents (id,owner,subject_id,audio_sha,scopes,revoked_at,created_at)"
                      " VALUES (?,?,?,?,?,?,?)",
                      ("vcs_t1", self.owner, "sub_d", "sha", "clone", 0, time.time()))
            c.commit()
            _vc.check_consent(c, "vcs_t1", owner=self.owner, subject_id="sub_d",
                              op="clone")
            with self.assertRaises(_vc.VoiceError):
                _vc.check_consent(c, "vcs_t1", owner=self.owner, subject_id="sub_d",
                                  op="tts")
            with self.assertRaises(_vc.VoiceError):
                _vc.check_consent(c, "vcs_t1", owner="mallory", subject_id="sub_d",
                                  op="clone")
            self.assertTrue(_vc.revoke_consent(c, "vcs_t1", self.owner))
            with self.assertRaises(_vc.VoiceError):
                _vc.check_consent(c, "vcs_t1", owner=self.owner, subject_id="sub_d",
                                  op="clone")

    def test_provider_key_never_leaks(self):
        from backend import vault as _v
        with db.connect() as c:
            _v.ensure_tables(c)
            _v.connect(c, self.owner, "fal", "SUPERSECRET-1")
            view = _v.agent_view(c, self.owner)
            import json
            blob = json.dumps(view) + json.dumps(
                _v.connected(c, self.owner))
            self.assertNotIn("SUPERSECRET-1", blob)

    def test_two_people_same_template_stay_split(self):
        from backend.creative import projects as _p
        with db.connect() as c:
            _p.ensure_tables(c)
            a = _p.create_project(c, self.owner, "sub_dad", "sideline_interview")
            b = _p.create_project(c, self.owner, "sub_mum", "sideline_interview")
            self.assertNotEqual(a["id"], b["id"])
            self.assertEqual(_p.find_project(c, self.owner, "sub_dad",
                                             "sideline_interview")["id"], a["id"])
            with self.assertRaises(ValueError):
                _p.save_revision(c, a["id"], "breaking_news", 1, {}, {})

    def test_concurrent_revision_conflict(self):
        from backend.creative import projects as _p
        with db.connect() as c:
            _p.ensure_tables(c)
            p = _p.create_project(c, self.owner, "s", "sideline_interview")
            _p.save_revision(c, p["id"], "sideline_interview", 1, {}, {})
            with self.assertRaises(ValueError):
                _p.save_revision(c, p["id"], "sideline_interview", 1, {}, {},
                                 expected_revision=0)

    def test_missing_template_files_skipped(self):
        import tempfile
        from pathlib import Path
        from backend.creative import templates as _t
        tmp = Path(tempfile.mkdtemp())
        d = tmp / "x" / "y"
        d.mkdir(parents=True)
        (d / "manifest.json").write_text('{"id": "broken"}')
        self.assertEqual(_t.load_all(tmp), {})


if __name__ == "__main__":
    unittest.main()
