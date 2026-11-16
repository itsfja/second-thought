"""Review's rules (#424): parse_rules, review_verdicts and stuck_rule. The cases are in tests/parity/review.json,
which the page's own tests (tests/editor/review.test.cjs) read too, so both sides keep the same rules."""
import json
import pathlib
import unittest

import support  # noqa: F401
from second_thought.core import parse_rules, review_verdicts, stuck_rule

PARITY = pathlib.Path(__file__).resolve().parent.parent / "parity"
REVIEW = json.loads((PARITY / "review.json").read_text(encoding="utf-8"))


class ParseRules(unittest.TestCase):
    def test_answers(self):
        for criteria, want in REVIEW["parse_rules"]["answers"]:
            with self.subTest(criteria=criteria):
                self.assertEqual(parse_rules(criteria), want)


class ReviewVerdicts(unittest.TestCase):
    def test_answers(self):
        for rules, reply, want in REVIEW["review_verdicts"]["answers"]:
            with self.subTest(rules=rules, reply=reply):
                got = review_verdicts(rules, reply)
                self.assertEqual({k: got[k] for k in ("approved", "problems", "met", "unmet", "verdicts")}, want)


class StuckRule(unittest.TestCase):
    def test_answers(self):
        for prev, unmet, want in REVIEW["stuck_rule"]["answers"]:
            with self.subTest(prev=prev, unmet=unmet):
                self.assertEqual(stuck_rule(prev, unmet), want)


if __name__ == "__main__":
    unittest.main()
