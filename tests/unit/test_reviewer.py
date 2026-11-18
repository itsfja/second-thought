"""A second opinion on the review blocks (#426): the blocks' 'checked by' choice and the reviewer setting —
same model, another maker's model when a key for one is set, or a named one — and the run log saying who
wrote and who checked."""
import asyncio
import os
import unittest
from unittest.mock import patch

import support  # noqa: F401
from second_thought import settings
from second_thought.providers import SERVICES, key_set, maker_of, other_maker_tiers
from second_thought.runtime import Runtime


def svc(name):
    return next(s for s in SERVICES if s["name"] == name)


class KeySet(unittest.TestCase):
    def test_a_service_key(self):
        with patch.dict(os.environ, {"GEMINI_API_KEY": "test"}):
            self.assertTrue(key_set(svc("Gemini")))
        with patch.dict(os.environ, {}, clear=True):
            self.assertFalse(key_set(svc("Gemini")))

    def test_local_llama_needs_no_key(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertTrue(key_set(svc("Llama")))  # its default base is Ollama on this computer
        with patch.dict(os.environ, {"LLAMA_BASE_URL": "https://llama.example.com/v1"}, clear=True):
            self.assertFalse(key_set(svc("Llama")))


class OtherMakerTiers(unittest.TestCase):
    def test_another_maker_with_a_key_in_service_order(self):
        with patch.dict(os.environ, {"GEMINI_API_KEY": "t", "OPENAI_API_KEY": "t"}, clear=True):
            others = other_maker_tiers("default")  # Claude's tier
            self.assertEqual(others[0], "gemini-default")  # Gemini is the first other-maker service with a key
            self.assertNotEqual(maker_of(others[0]), "Anthropic")
            self.assertIn("openai-default", others)

    def test_the_same_maker_is_not_another(self):
        with patch.dict(os.environ, {"GEMINI_API_KEY": "t"}, clear=True):
            others = other_maker_tiers("gemini-default")
            self.assertNotIn("gemini-quick", others)
            self.assertNotIn("gemini-complex", others)
            self.assertNotIn("default", others)

    def test_without_a_key_there_is_no_candidate(self):
        with patch.dict(os.environ, {"LLAMA_BASE_URL": "https://x.example/v1"}, clear=True):
            self.assertEqual(other_maker_tiers("default"), [])


class ReviewerTier(unittest.TestCase):
    def setUp(self):
        self.r = Runtime()
        self.r.reset()
        self.r.tier = self.r.primary = "default"

    def test_same_and_unset(self):
        self.assertEqual(self.r.reviewer_tier("same"), ("default", None))
        self.assertEqual(self.r.reviewer_tier(""), ("default", None))
        self.assertEqual(self.r.reviewer_tier(None), ("default", None))

    def test_a_named_model(self):
        self.assertEqual(self.r.reviewer_tier("openai-default"), ("openai-default", None))
        self.assertEqual(self.r.reviewer_tier("openrouter:mistralai/mistral-small"), ("openrouter:mistralai/mistral-small", None))

    def test_the_setting_is_the_default_and_the_block_wins(self):
        with patch.dict(os.environ, {"RB_REVIEWER": "another", "GEMINI_API_KEY": "t"}):
            r = Runtime()
            r.reset()
            r.tier = r.primary = "default"
            self.assertEqual(r.reviewer_tier(""), ("gemini-default", None))  # no choice on the block: the setting decides
            self.assertEqual(r.reviewer_tier("same"), ("default", None))     # the block's own choice wins
            self.assertEqual(r.reviewer_tier("openai-default"), ("openai-default", None))

    def test_another_without_a_key_says_so_instead_of_failing(self):
        with patch.dict(os.environ, {"LLAMA_BASE_URL": "https://x.example/v1"}, clear=True):
            tier, note = self.r.reviewer_tier("another")
            self.assertEqual(tier, "default")
            self.assertIn("No other maker's model has a key", note)


def approved():
    return {"approved": True, "rules": [{"rule": "clear", "met": True}], "problems": []}


class ReviewUsesTheReviewer(unittest.TestCase):
    def run_review(self, r, reviewer=None):
        seen = []

        async def fake_call(prompt, schema=None, *a, **k):
            seen.append(r.current_tier)
            return approved()
        r._call = fake_call
        logged = []
        r.log = lambda name, text="", status="", **k: logged.append((name, text, status))

        async def go():
            r.set_task("t")
            r.set_draft("a draft")  # written by the primary model
            return await r.review("clear", reviewer=reviewer)
        ok = asyncio.run(go())
        return ok, seen, logged

    def test_the_call_goes_to_the_reviewer_and_the_log_names_both(self):
        r = Runtime()
        r.reset()
        ok, seen, logged = self.run_review(r, reviewer="gemini-default")
        self.assertTrue(ok)
        self.assertEqual(seen, ["gemini-default"])  # the review call ran on the reviewer, not the writer
        rev = next(l for l in logged if l[0] == "Review")
        self.assertIn("Meets every criterion.", rev[1])
        self.assertIn("Written by Claude, balanced; checked by Gemini Flash.", rev[1])

    def test_the_reviewer_setting_applies_when_the_block_says_nothing(self):
        with patch.dict(os.environ, {"RB_REVIEWER": "gemini-default"}):
            r = Runtime()
            r.reset()
            ok, seen, logged = self.run_review(r)  # no reviewer= argument
            self.assertTrue(ok)
            self.assertEqual(seen, ["gemini-default"])

    def test_same_model_by_default(self):
        r = Runtime()
        r.reset()
        ok, seen, logged = self.run_review(r, reviewer="same")
        self.assertEqual(seen, ["default"])
        rev = next(l for l in logged if l[0] == "Review")
        self.assertIn("checked by Claude, balanced", rev[1])


class Setting(unittest.TestCase):
    def test_reviewer_is_a_known_one_word_setting(self):
        self.assertEqual(settings.SETTING_NAMES["reviewer"], "RB_REVIEWER")
        self.assertIn("reviewer", settings.ONE_WORD_SETTINGS)


if __name__ == "__main__":
    unittest.main()
