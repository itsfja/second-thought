"""The review's exact checks (#425): exact_checks. The cases are in tests/parity/checks.json, which the page's own
tests (tests/editor/checks.test.cjs) read too, so both sides work the checks out the same way."""
import json
import pathlib
import unittest

import support  # noqa: F401
from second_thought.core import exact_checks

PARITY = pathlib.Path(__file__).resolve().parent.parent / "parity"
CHECKS = json.loads((PARITY / "checks.json").read_text(encoding="utf-8"))


class ExactChecks(unittest.TestCase):
    def test_answers(self):
        for text, checks, want in CHECKS["exact_checks"]["answers"]:
            with self.subTest(text=text, checks=checks):
                got = exact_checks(text, checks)
                self.assertEqual([{k: g[k] for k in ("rule", "met", "problem", "shows")} for g in got], want)


if __name__ == "__main__":
    unittest.main()
