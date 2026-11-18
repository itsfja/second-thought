"""Must-fail test cases and --test --times N's flaky rules (#427), with a stand-in model: a must-fail case is a
saved bad result and the rule it must break — it passes only if the review fails the result on that rule; --times
runs each case several times and lists the rules that pass on some runs and fail on others."""
import asyncio
import contextlib
import io
import json
import pathlib
import tempfile
import unittest
from unittest.mock import patch

import support  # noqa: F401
from second_thought.runtime import Runtime


def verdict(rule, met, problem=""):
    """A review reply in the #424 shape: one verdict for the one rule."""
    return {"approved": met, "rules": [{"rule": rule, "met": met, "problem": problem, "shows": ""}],
            "problems": [] if met else [problem or rule]}


class RunTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.tests_file = pathlib.Path(self.tmp.name) / "prog.tests.json"
        patcher = patch.object(Runtime, "tests_path", staticmethod(lambda: str(self.tests_file)))
        patcher.start()
        self.addCleanup(patcher.stop)
        self.r = Runtime()
        self.r.reset()
        self.r.log = lambda *a, **k: None

        async def fake_run(scripts, label=None):  # the program "runs" and leaves a result, no blocks involved
            self.r.reset()
            self.r.result = ["the saved result"]
            return 0
        self.r.run = fake_run

    def run_tests(self, cases, replies, times=1):
        self.tests_file.write_text(json.dumps(cases), encoding="utf-8")
        it = iter(replies)

        async def fake_call(prompt, schema=None, *a, **k):
            return next(it)
        self.r._call = fake_call
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = asyncio.run(self.r.run_tests([("prog", "")], times))
        return code, out.getvalue()

    def test_a_must_fail_case_passes_only_when_the_review_breaks_that_rule(self):
        case = {"name": "bad draft", "criteria": "clear; titled", "must_fail": "titled"}
        # the review fails, and on the rule the case says it must break: PASS
        code, out = self.run_tests([case], [{"approved": False,
                                              "rules": [{"rule": "clear", "met": True}, {"rule": "titled", "met": False, "problem": "no title", "shows": ""}],
                                              "problems": ["no title"]}])
        self.assertEqual(code, 0)
        self.assertIn("PASS  bad draft  [must fail]", out)
        # the review approves (the rule passes everything): FAIL, saying to rewrite it
        code, out = self.run_tests([case], [{"approved": True, "rules": [{"rule": "clear", "met": True}, {"rule": "titled", "met": True}], "problems": []}])
        self.assertEqual(code, 1)
        self.assertIn("FAIL  bad draft  [must fail]", out)
        self.assertIn("The rule was met: a must-fail case must break it", out)
        # the review fails, but not on the must-break rule: FAIL, saying so
        code, out = self.run_tests([case], [{"approved": False, "rules": [{"rule": "clear", "met": False, "problem": "vague"}, {"rule": "titled", "met": True}],
                                              "problems": ["vague"]}])
        self.assertEqual(code, 1)
        self.assertIn("not on the rule it must break (titled)", out)

    def test_times_reports_flaky_rules(self):
        case = {"name": "flaky", "criteria": "clear"}
        # the rule is met on runs 1 and 3, not on run 2: the case fails and the rule is listed as flaky
        code, out = self.run_tests([case], [verdict("clear", True), verdict("clear", False, "too vague"), verdict("clear", True)], times=3)
        self.assertEqual(code, 1)
        self.assertIn("FAIL  flaky", out)
        self.assertIn("2 of 3 runs passed.", out)
        self.assertIn("Flaky rules: these pass on some runs and fail on others", out)
        self.assertIn("flaky · clear — 2 of 3 runs met the rule.", out)
        # stable across runs: no flaky section, exit 0
        code, out = self.run_tests([case], [verdict("clear", True)] * 3, times=3)
        self.assertEqual(code, 0)
        self.assertIn("PASS  flaky", out)
        self.assertNotIn("Flaky rules", out)

    def test_times_one_is_the_same_as_before(self):
        code, out = self.run_tests([{"name": "good", "criteria": "clear"}], [verdict("clear", True)])
        self.assertEqual(code, 0)
        self.assertIn("1 of 1 passed.", out)
        code, out = self.run_tests([{"name": "good", "criteria": "clear"}], [verdict("clear", False, "vague")])
        self.assertEqual(code, 1)
        self.assertIn("clear: vague", out)


if __name__ == "__main__":
    unittest.main()
