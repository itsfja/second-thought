"""Each account's plan, and the rate limits services report (#270)."""
import asyncio
import datetime
import os
import pathlib
import subprocess
import sys
import tempfile
import unittest

import support
from second_thought import providers, spending
from second_thought.core import RunError
from second_thought.providers import limits_from_headers, record_limits
from second_thought.runtime import Runtime

NOW = datetime.datetime(2026, 11, 4, 15, 30)

CLAUDE = {"anthropic-ratelimit-requests-limit": "10000", "anthropic-ratelimit-requests-remaining": "9000",
          "anthropic-ratelimit-requests-reset": "2026-11-04T15:31:00Z", "anthropic-ratelimit-output-tokens-limit": "1000000",
          "anthropic-ratelimit-output-tokens-remaining": "250000", "anthropic-ratelimit-output-tokens-reset": "2026-11-04T15:31:00Z",
          "content-type": "application/json"}
OPENAI = {"x-ratelimit-limit-requests": "5000", "x-ratelimit-remaining-requests": "4999", "x-ratelimit-reset-requests": "12ms",
          "x-ratelimit-limit-tokens": "1000000", "x-ratelimit-remaining-tokens": "999000", "x-ratelimit-reset-tokens": "1ms"}


class Env:
    def __init__(self, **env):
        self.env = env

    def __enter__(self):
        self.saved = {k: os.environ.get(k) for k in self.env}
        os.environ.update(self.env)

    def __exit__(self, *a):
        for k, v in self.saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


class Headers(unittest.TestCase):
    def tearDown(self):
        providers.REPORTED.clear()

    def test_claudes(self):
        got = limits_from_headers(CLAUDE)
        self.assertEqual(got["requests"], {"limit": 10000, "remaining": 9000, "reset": "2026-11-04T15:31:00Z"})
        self.assertEqual(got["output-tokens"]["remaining"], 250000)
        self.assertEqual(set(got), {"requests", "output-tokens"})

    def test_openais_and_groqs(self):
        got = limits_from_headers(OPENAI)
        self.assertEqual(got["requests"]["limit"], 5000)
        self.assertEqual(got["tokens"]["reset"], "1ms")

    def test_nothing_reported(self):
        self.assertEqual(limits_from_headers({"content-type": "application/json"}), {})
        record_limits("Gemini", "x", {})
        self.assertNotIn("Gemini", providers.REPORTED)

    def test_lines_are_labelled_as_the_services_own(self):
        record_limits("OpenAI", "gpt-6.1-sol", OPENAI)
        self.assertEqual(spending.reported_lines(), ["OpenAI reports 100% of its requests left, 100% of its tokens left"])
        record_limits("Claude", "claude-sonnet-5-5", CLAUDE)
        lines = spending.reported_lines(["Claude"])
        self.assertEqual(lines[0], "Claude reports 90% of its requests left, 25% of its output tokens left")

    def test_suggests_the_plan_its_limits_match(self):
        record_limits("Claude", "claude-sonnet-5-5", CLAUDE)  # 10,000 requests a minute: Build, for Sonnet
        lines = spending.reported_lines(["Claude"])
        self.assertIn("Claude's limits match its Build plan: add PLAN_CLAUDE = build", lines[1])
        with Env(PLAN_CLAUDE="build"):
            self.assertEqual(len(spending.reported_lines(["Claude"])), 1, "no hint once the plan is set")

    def test_no_hint_when_it_could_be_two_plans(self):
        record_limits("Claude", "claude-haiku-4-5-20251001", {**CLAUDE, "anthropic-ratelimit-requests-limit": "7"})
        self.assertEqual(len(spending.reported_lines(["Claude"])), 1)


class WithLedger(unittest.TestCase):
    """A ledger in a temporary folder, and a Claude key, for one test."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.saved = spending.spending_file
        spending.spending_file = lambda: os.path.join(self.tmp.name, ".second-thought-spending.json")
        self.env = Env(ANTHROPIC_API_KEY="sk-test")
        self.env.__enter__()
        self.rt = Runtime()
        self.rt.reset()
        self.rt.log = lambda *a, **k: None

    def tearDown(self):
        self.env.__exit__()
        spending.spending_file = self.saved
        self.tmp.cleanup()


class Plans(WithLedger):
    def test_every_plan_table_is_dated_and_sourced(self):
        for service, p in spending.PLANS.items():
            with self.subTest(service=service):
                datetime.date.fromisoformat(p["checked"])
                self.assertTrue(p["source"].startswith("https://"))
                self.assertTrue(all(n == n.lower() for n in p["plans"]), "plan names are kept lower case")
                for model in p.get("rpm", {}):
                    self.assertIn(model, providers.MODELS.values())

    def test_a_mistyped_plan_stops_saying_the_names(self):
        with Env(PLAN_CLAUDE="tier 2"):
            with self.assertRaises(SystemExit) as e:
                spending.check_plans()
        self.assertIn("evaluation, start, build, scale, custom", str(e.exception))

    def test_plan_names_ignore_case_and_spaces(self):
        with Env(PLAN_GEMINI="  Tier   2 "):
            spending.check_plans()
            self.assertEqual(spending.plan_of("Gemini"), "tier 2")

    def test_the_monthly_cap_stops_a_run(self):
        with Env(PLAN_CLAUDE="start"):
            self.rt.spend("default", 499.0, now=NOW)
            self.assertEqual(self.rt._within_allowances(["default"], now=NOW), ["default"])
            self.rt.spend("default", 2.0, now=NOW)
            with self.assertRaises(RunError) as e:
                self.rt._within_allowances(["default"], now=NOW)
        self.assertIn("Start plan's monthly cap of $500.00", str(e.exception))
        self.assertIn("2026-12-01", str(e.exception))

    def test_how_much_of_the_cap_has_gone(self):
        with Env(PLAN_CLAUDE="build"):
            self.rt.spend("default", 120.0, now=NOW)
            self.assertEqual(self.rt.allowance_lines(["default"], now=NOW),
                             ["Claude (Build plan): 12% of this month's $1,000.00 cap, counted on this computer"])

    def test_a_plan_without_a_cap_only_labels(self):
        with Env(PLAN_CLAUDE="custom", GEMINI_API_KEY="g"):
            self.assertIsNone(spending.plan_cap("Claude"))
            self.assertEqual(self.rt._within_allowances(["default"], now=NOW), ["default"])

    def test_claudes_month_is_in_utc(self):
        start = spending.month_start(NOW, utc=True)
        offset = datetime.datetime.now().astimezone().utcoffset() or datetime.timedelta(0)
        self.assertEqual(start - offset, datetime.datetime(2026, 11, 1))


class ClaudeReplies(unittest.TestCase):
    """The stand-in SDK sends Claude's headers through with_raw_response, as the real one does."""

    def test_a_call_records_what_claude_reports(self):
        runtime = (support.ROOT / "python" / "runtime.py").read_text(encoding="utf-8")
        fake = support.ROOT / "tests" / "fakeapi"
        with tempfile.TemporaryDirectory() as tmp:
            prog = pathlib.Path(tmp) / "prog.py"
            prog.write_text(runtime + "\nimport asyncio\nR = Runtime()\nR.reset()\nR.log = lambda *a, **k: None\n"
                            "asyncio.run(R._call_live('hello'))\nprint(reported_lines())\n", encoding="utf-8")
            env = {k: v for k, v in os.environ.items() if not k.startswith("RB_")}
            env.update(PYTHONPATH=str(fake), ANTHROPIC_API_KEY="sk-test", SECOND_THOUGHT_INI=os.path.join(tmp, "none.ini"),
                       RB_MEMORY_FILE=os.path.join(tmp, "memory.json"), RB_STREAM="no")
            r = subprocess.run([sys.executable, str(prog)], capture_output=True, text=True, timeout=60, cwd=tmp, env=env)
        self.assertIn("Claude reports 100% of its requests left, 95% of its input tokens left", r.stdout, r.stderr[-500:])
        self.assertIn("match its Start plan", r.stdout)


class EndOfRun(WithLedger):
    def tearDown(self):
        providers.REPORTED.clear()
        super().tearDown()

    def test_limits_only_when_low(self):
        record_limits("OpenAI", "gpt-6.1-sol", OPENAI)
        self.assertEqual(spending.reported_lines(low_only=True), [])
        record_limits("OpenAI", "gpt-6.1-sol", {**OPENAI, "x-ratelimit-remaining-tokens": "100000"})
        self.assertEqual(spending.reported_lines(low_only=True), ["OpenAI reports 100% of its requests left, 10% of its tokens left"])

    def test_the_plan_hint_is_given_once(self):
        record_limits("Claude", "claude-sonnet-5-5", CLAUDE)
        self.assertEqual(len(self.rt.plan_hints_once()), 1)
        self.assertEqual(self.rt.plan_hints_once(), [], "once given, the end of a run doesn't repeat it")
        self.assertEqual(len(spending.reported_lines(["Claude"])), 2, "--doctor and saved logs still give it")


if __name__ == "__main__":
    unittest.main()
