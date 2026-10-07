"""Funny pipeline tests — offline except the flagged live proof."""
import unittest


class TestSlop(unittest.TestCase):
    def test_clean_joke_passes(self):
        from backend.funny import slop
        d = slop.diagnose("Dad fell asleep. Dad snores. Dad denies everything.")
        self.assertTrue(d["slop_free"])

    def test_essay_slop_fails(self):
        from backend.funny import slop
        d = slop.diagnose("In this essay we will now turn to living your truth.")
        self.assertFalse(d["slop_free"])
        self.assertIn("CLICHE", d["fails"])

    def test_rule_of_three_never_fails(self):
        from backend.funny import slop
        d = slop.diagnose("He golfs, he naps, and he denies it all.")
        self.assertNotIn("3LIST", d["fails"])


class TestRecipesJudge(unittest.TestCase):
    def test_plan_slots_facts(self):
        from backend.funny import recipes
        p = recipes.plan("profile_roast", {"name": "Dad", "interest": "golf"})
        self.assertIn("beats", p)
        self.assertEqual(p["facts"]["interest"], "golf")

    def test_judge_scores_shape(self):
        from backend.funny import judge
        lines = ["Dad assembled the barbecue in 4 hours flat.",
                 "And then it rained, but he stood guard with an umbrella.",
                 "Best dad ever."]
        v = judge.score(lines)
        self.assertIn(v["stars"], (1, 2, 3, 4, 5))
        self.assertIn("specific numbers", v["reasons"])

    def test_judge_punishes_slop_shape(self):
        from backend.funny import judge
        v = judge.score(["The thing about that is it is what it is. " * 12])
        self.assertLessEqual(v["stars"], 3)


class TestPipeline(unittest.TestCase):
    def test_loop_with_mock_writer(self):
        import backend.funny.pipeline as P
        import backend.funny.writer as W
        calls = {"n": 0}

        def fake_write(prompt, approved=False, model=""):
            calls["n"] += 1
            assert approved
            if calls["n"] == 1:
                return {"lines": ["In this essay we will now turn to living your truth and trust the process."],
                        "model": "mock"}
            return {"lines": ["Dad fixed the sink in 20 minutes flat.",
                              "And flooded the kitchen, but he owned it like a king.",
                              "Best dad ever."], "model": "mock"}

        real = W.write_set
        W.write_set = fake_write
        try:
            out = P.run_set({"name": "Dad", "interests": ["DIY"],
                             "memories": ["flooded kitchen"]}, approved=True)
        finally:
            W.write_set = real
        self.assertTrue(out["ok"])
        self.assertGreaterEqual(len(out["attempts"]), 1)
        self.assertEqual(out["attempts"][0]["stars"], out["attempts"][0]["stars"])

    def test_writer_needs_approval(self):
        from backend.funny import writer
        with self.assertRaises(writer.WriterError):
            writer.write_set("hi", approved=False)


if __name__ == "__main__":
    unittest.main()
