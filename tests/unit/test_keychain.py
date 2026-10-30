"""The optional keychain: which keys it can hold, and that it only fills in what the environment and the ini leave out."""
import os
import sys
import unittest
from unittest import mock

import support
from second_thought import settings
from second_thought.providers import SERVICES

sys.path.insert(0, str(support.ROOT / "tests" / "fakekeyring"))


class Keychain(unittest.TestCase):
    def test_every_service_key_can_live_in_the_keychain(self):
        keys = {k for s in SERVICES for k in s["keys"]}
        self.assertEqual(sorted(keys - set(settings.KEYCHAIN_NAMES)), [])

    def run_keychain(self, env, chain):
        with mock.patch.dict(os.environ, dict(env, FAKE_KEYCHAIN=chain), clear=True), mock.patch.dict(settings.KEY_SOURCES, clear=True):
            problem = settings._load_keychain()
            return problem, {k: os.environ.get(k) for k in ("ANTHROPIC_API_KEY", "GITHUB_TOKEN")}, dict(settings.KEY_SOURCES)

    def test_fills_in_only_missing_keys(self):
        problem, got, sources = self.run_keychain({"GITHUB_TOKEN": "from-env"}, '{"ANTHROPIC_API_KEY": "from-chain", "GITHUB_TOKEN": "chain"}')
        self.assertIsNone(problem)
        self.assertEqual(got, {"ANTHROPIC_API_KEY": "from-chain", "GITHUB_TOKEN": "from-env"})
        self.assertEqual(sources, {"ANTHROPIC_API_KEY": "keychain"})

    def test_a_broken_keychain_is_reported_not_raised(self):
        problem, got, _ = self.run_keychain({}, "broken")
        self.assertIn("No recommended backend", problem)
        self.assertIsNone(got["ANTHROPIC_API_KEY"])

    def test_can_be_turned_off(self):
        problem, got, _ = self.run_keychain({"RB_KEYCHAIN": "no"}, '{"ANTHROPIC_API_KEY": "from-chain"}')
        self.assertIsNone(problem)
        self.assertIsNone(got["ANTHROPIC_API_KEY"])


if __name__ == "__main__":
    unittest.main()
