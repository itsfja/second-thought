"""Each key's spending on this computer, with hourly, daily, weekly and monthly allowances (#269)."""
import asyncio
import datetime
import json
import os
import pathlib
import tempfile
import unittest

import support  # noqa: F401
from second_thought import spending
from second_thought.core import RunError
from second_thought.runtime import Runtime

NOW = datetime.datetime(2026, 11, 4, 15, 30)  # a Wednesday


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


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.saved_file = spending.spending_file
        spending.spending_file = lambda: os.path.join(self.tmp.name, ".second-thought-spending.json")
        self.env = Env(ANTHROPIC_API_KEY="sk-test-key-123")
        self.env.__enter__()
        self.rt = Runtime()
        self.rt.reset()
        self.rt.log = lambda *a, **k: None

    def tearDown(self):
        self.env.__exit__()
        spending.spending_file = self.saved_file
        self.tmp.cleanup()


class Windows(unittest.TestCase):
    def test_starts_and_ends(self):
        self.assertEqual(spending.window_start("hourly", NOW), datetime.datetime(2026, 11, 4, 15))
        self.assertEqual(spending.window_start("daily", NOW), datetime.datetime(2026, 11, 4))
        self.assertEqual(spending.window_start("weekly", NOW), datetime.datetime(2026, 11, 2), "weeks start on Monday")
        self.assertEqual(spending.window_start("monthly", NOW), datetime.datetime(2026, 11, 1))
        self.assertEqual(spending.window_end("hourly", NOW), datetime.datetime(2026, 11, 4, 16))
        self.assertEqual(spending.window_end("weekly", NOW), datetime.datetime(2026, 11, 9))
        self.assertEqual(spending.window_end("monthly", datetime.datetime(2026, 12, 31, 23)), datetime.datetime(2027, 1, 1))


class Ledger(Base):
    def test_adds_up_by_window(self):
        self.rt.spend("default", 0.10, now=NOW)
        self.rt.spend("default", 0.05, now=NOW - datetime.timedelta(hours=2))       # today
        self.rt.spend("default", 0.20, now=datetime.datetime(2026, 11, 2, 9))        # Monday: this week
        self.rt.spend("default", 0.40, now=datetime.datetime(2026, 11, 1, 9))        # Sunday: this month, last week
        self.assertAlmostEqual(self.rt.spent("default", "hourly", NOW), 0.10)
        self.assertAlmostEqual(self.rt.spent("default", "daily", NOW), 0.15)
        self.assertAlmostEqual(self.rt.spent("default", "weekly", NOW), 0.35)
        self.assertAlmostEqual(self.rt.spent("default", "monthly", NOW), 0.75)

    def test_one_key_for_every_tier_of_a_service(self):
        self.rt.spend("quick", 0.10, now=NOW)
        self.rt.spend("complex", 0.10, now=NOW)
        self.assertAlmostEqual(self.rt.spent("default", "hourly", NOW), 0.20)

    def test_never_keeps_the_key(self):
        self.rt.spend("default", 0.10, now=NOW)
        text = pathlib.Path(spending.spending_file()).read_text(encoding="utf-8")
        self.assertNotIn("sk-test-key-123", text)
        self.assertEqual(list(json.loads(text)["keys"].values())[0]["service"], "Claude")

    def test_another_key_is_counted_apart(self):
        self.rt.spend("default", 0.10, now=NOW)
        with Env(ANTHROPIC_API_KEY="sk-another"):
            self.assertEqual(self.rt.spent("default", "hourly", NOW), 0)

    def test_old_hours_are_dropped(self):
        self.rt.spend("default", 0.10, now=NOW - datetime.timedelta(days=60))
        self.rt.spend("default", 0.10, now=NOW)
        hours = list(json.loads(pathlib.Path(spending.spending_file()).read_text(encoding="utf-8"))["keys"].values())[0]["hours"]
        self.assertEqual(list(hours), ["2026-11-04T15"])

    def test_no_key_counts_nothing(self):
        with Env(ANTHROPIC_API_KEY=""):
            self.rt.spend("default", 0.10, now=NOW)
        self.assertFalse(os.path.exists(spending.spending_file()))


class Allowances(Base):
    def test_stops_when_reached_and_says_when_it_resets(self):
        with Env(RB_QUOTA_DAILY="0.20"):
            self.rt.spend("default", 0.25, now=NOW)
            with self.assertRaises(RunError) as e:
                self.rt._within_allowances(["default"], now=NOW)
        self.assertIn("daily allowance of $0.20", str(e.exception))
        self.assertIn("2026-11-05 00:00", str(e.exception))

    def test_room_left_lets_it_through(self):
        with Env(RB_QUOTA_DAILY="1.00"):
            self.rt.spend("default", 0.25, now=NOW)
            self.assertEqual(self.rt._within_allowances(["default"], now=NOW), ["default"])

    def test_a_services_own_allowance_wins(self):
        with Env(RB_QUOTA_DAILY="10", QUOTA_DAILY_CLAUDE="0.20"):
            self.rt.spend("default", 0.25, now=NOW)
            with self.assertRaises(RunError):
                self.rt._within_allowances(["default"], now=NOW)

    def test_an_unpriced_model_is_refused_under_an_allowance(self):
        with Env(RB_QUOTA_DAILY="1", MOONSHOT_API_KEY="sk-k"):
            with self.assertRaises(RunError) as e:
                self.rt._within_allowances(["kimi-default"], now=NOW)  # Kimi K2.6: no published price
        self.assertIn("no known price", str(e.exception))

    def test_backups_without_room_are_left_out(self):
        with Env(QUOTA_DAILY_CLAUDE="0.20", GEMINI_API_KEY="g-key"):
            self.rt.spend("default", 0.25, now=NOW)
            self.assertEqual(self.rt._within_allowances(["gemini-default", "default"], now=NOW), ["gemini-default"])

    def test_in_the_programs_currency(self):
        from second_thought import providers
        saved = providers.CURRENCY
        try:
            providers.CURRENCY = spending.CURRENCY = "gbp"
            with Env(RB_QUOTA_DAILY="1.00", RB_EXCHANGE_RATE="0.8"):
                self.rt.spend("default", 0.50, now=NOW)  # £0.40
                self.assertEqual(self.rt.allowance_lines(["default"], now=NOW), ["Claude key: 40% of the daily allowance of £1.00"])
        finally:
            providers.CURRENCY = spending.CURRENCY = saved

    def test_a_run_stops_at_its_allowance(self):
        async def call_tier(t, *a, **k):
            self.rt._count("Claude", 100_000, 10_000)  # $0.30
            return "ok"
        self.rt.tier = self.rt.primary = "default"
        self.rt.backups = []
        self.rt._call_tier = call_tier
        with Env(RB_QUOTA_HOURLY="0.50"):
            asyncio.run(self.rt._call_live("a"))
            asyncio.run(self.rt._call_live("b"))
            with self.assertRaises(RunError) as e:
                asyncio.run(self.rt._call_live("c"))
        self.assertIn("hourly allowance of $0.50", str(e.exception))

    def test_github_actions_says_the_tally_is_per_run(self):
        with Env(RB_QUOTA_DAILY="1", GITHUB_ACTIONS="true"):
            self.assertIn("GitHub Actions", self.rt.allowance_note())
        os.environ.pop("GITHUB_ACTIONS", None)


class AsAnExportedProgram(unittest.TestCase):
    """The joined python/runtime.py, run as a program with allowances set (see #274 for why this is its own test)."""

    def run_with(self, **env):
        import subprocess
        import sys
        runtime = (support.ROOT / "python" / "runtime.py").read_text(encoding="utf-8")
        with tempfile.TemporaryDirectory() as tmp:
            prog = os.path.join(tmp, "prog.py")
            with open(prog, "w", encoding="utf-8") as f:
                f.write(runtime + "\nR = Runtime()\nR.spend('default', 0.25)\nprint(R.allowance_lines(['default']))\nR.main([], {}, [])\n")
            full = {k: v for k, v in os.environ.items() if not k.startswith("RB_")}
            full.update(SECOND_THOUGHT_INI=os.path.join(tmp, "none.ini"), RB_MEMORY_FILE=os.path.join(tmp, "memory.json"),
                        ANTHROPIC_API_KEY="sk-test", **env)
            return subprocess.run([sys.executable, "-I", prog], capture_output=True, text=True, timeout=60, cwd=tmp, env=full)

    def test_runs_with_allowances(self):
        r = self.run_with(RB_QUOTA_DAILY="1.00", QUOTA_MONTHLY_CLAUDE="20")
        self.assertIn("Claude key: 25% of the daily allowance of $1.00, 1% of the monthly allowance of $20.00", r.stdout, r.stderr[-400:])

    def test_a_mistyped_allowance_says_which_setting(self):
        r = self.run_with(RB_QUOTA_DAILY="a pound")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("quota_daily", r.stderr)


if __name__ == "__main__":
    unittest.main()
