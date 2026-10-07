"""AI model registry tests — offline, no keys, no network."""
import unittest

from backend import ai_models as ai


class TestAiRegistry(unittest.TestCase):
    def test_three_providers(self):
        self.assertEqual(set(ai.PROVIDERS), {"openrouter", "fal", "alibaba"})
        for pid, p in ai.PROVIDERS.items():
            for k in ("label", "key_env", "auth", "billing", "docs"):
                self.assertIn(k, p, pid)
            self.assertTrue(p["key_env"].endswith("_KEY") or "KEY" in p["key_env"], pid)

    def test_every_model_option_is_shaped(self):
        for need, entry in ai.MODELS.items():
            self.assertTrue(entry.get("need"), need)
            self.assertTrue(entry.get("options"), need)
            for o in entry["options"]:
                self.assertIn(o["provider"], ai.PROVIDERS, need)
                self.assertTrue(o.get("endpoint"), need)
                self.assertIn(o.get("est"), ("live", "quote"), need)
                self.assertTrue(o.get("notes"), need)

    def test_needs_cover_the_loops(self):
        for need in ("jokescheap", "cardart", "lipsync", "voiceclone",
                     "meshgen", "photorubric", "characterswap"):
            self.assertIn(need, ai.MODELS)
            self.assertTrue(ai.options_for(need))
        self.assertEqual(ai.options_for("nope"), [])

    def test_options_carry_key_env(self):
        for o in ai.options_for("lipsync"):
            self.assertTrue(o["key_env"])
            self.assertTrue(o["provider_label"])


if __name__ == "__main__":
    unittest.main()
