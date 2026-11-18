"""Action allowances (#432): messages, home actions and money moves counted across runs on this computer, from the
receipts, stopping a run at an allowance (allow_<kind>_hourly/_daily, on by default) with one message per run."""
import asyncio
import json
import os
import pathlib
import sys
import tempfile
import unittest

import support
from second_thought.runtime import Runtime


class Allowances(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.prog = pathlib.Path(self.tmp.name) / "prog.py"
        self.prog.write_text("# prog\n", encoding="utf-8")
        self.saved_argv = sys.argv
        sys.argv = [str(self.prog)]
        self.counts = pathlib.Path(self.tmp.name) / "counts.json"
        self.saved_env = {k: os.environ.get(k) for k in list(os.environ) if k.startswith("RB_ALLOW_")}
        for k in list(os.environ):
            if k.startswith("RB_ALLOW_"):
                del os.environ[k]
        os.environ["RB_COUNTS_FILE"] = str(self.counts)
        self.rt = Runtime()
        self.rt._last_how = ""

    def tearDown(self):
        sys.argv = self.saved_argv
        for k in list(os.environ):
            if k.startswith("RB_ALLOW_"):
                del os.environ[k]
        os.environ.update({k: v for k, v in self.saved_env.items() if v is not None})
        os.environ.pop("RB_COUNTS_FILE", None)
        self.tmp.cleanup()

    def go(self, coro):
        return asyncio.run(coro)

    def said(self):
        return [t for t in self.rt.trace if len(t) > 1 and t[1] == "Allowance reached"]

    def counts_data(self):
        if not self.counts.is_file():
            return {}
        return json.loads(self.counts.read_text(encoding="utf-8"))["hours"]

    def test_a_loop_that_sends_stops_at_the_allowance_and_says_so_once(self):
        os.environ["RB_ALLOW_MESSAGES_DAILY"] = "2"
        got = [self.go(self.rt._allowed(["messages"], f"send {i}")) for i in range(4)]
        self.assertEqual(got, [True, True, False, False])
        self.assertEqual(len(self.said()), 1, "the stop is said once, not for every blocked send")
        self.assertIn("daily allowance of 2", self.said()[0][2])
        self.assertEqual(self.said()[0][3], "stopped")

    def test_counts_are_across_runs_on_this_computer(self):
        os.environ["RB_ALLOW_MESSAGES_DAILY"] = "2"
        self.assertTrue(self.go(self.rt._allowed(["messages"], "send 1")))
        self.assertTrue(self.go(self.rt._allowed(["messages"], "send 2")))
        rt2 = Runtime()  # another run, same computer: the counts are shared
        self.assertFalse(self.go(rt2._allowed(["messages"], "send 3")))
        self.assertEqual(len([t for t in rt2.trace if len(t) > 1 and t[1] == "Allowance reached"]), 1)

    def test_zero_turns_an_allowance_off(self):
        os.environ["RB_ALLOW_MESSAGES_DAILY"] = "0"
        os.environ["RB_ALLOW_MESSAGES_HOURLY"] = "0"
        got = [self.go(self.rt._allowed(["messages"], f"send {i}")) for i in range(15)]
        self.assertEqual(got, [True] * 15)

    def test_the_hourly_window_counts_too(self):
        os.environ["RB_ALLOW_MESSAGES_HOURLY"] = "1"
        os.environ["RB_ALLOW_MESSAGES_DAILY"] = "0"
        self.assertTrue(self.go(self.rt._allowed(["messages"], "send 1")))
        self.assertFalse(self.go(self.rt._allowed(["messages"], "send 2")))
        self.assertIn("hourly allowance of 1", self.said()[0][2])

    def test_home_actions_and_money_have_their_own_allowances(self):
        os.environ["RB_ALLOW_HA_DAILY"] = "1"
        os.environ["RB_ALLOW_MONEY_DAILY"] = "1"
        self.assertTrue(self.go(self.rt._allowed(["ha"], "light.turn_on on light.kitchen")))
        self.assertFalse(self.go(self.rt._allowed(["ha"], "light.turn_off on light.kitchen")))
        self.assertFalse(self.go(self.rt._allowed(["ha", "messages"], "notify")))  # ha is at its cap, so this is blocked too
        self.assertTrue(self.go(self.rt._allowed(["money"], "buy 0.01 BTC")))   # money has its own allowance: the first goes ahead
        self.assertFalse(self.go(self.rt._allowed(["money"], "buy 0.02 BTC")))
        self.assertEqual(self.rt._action_allowance_problem(["ha"])[0], "ha")
        self.assertEqual(self.rt._action_allowance_problem(["money"])[0], "money")
        problem = self.rt._action_allowance_problem(["money"])
        self.assertEqual(problem[0], "money")
        self.assertIn("money moves", problem[1])

    def test_money_allowance_stops_confirm_money_before_any_asking(self):
        os.environ["RB_ALLOW_MONEY_DAILY"] = "1"
        self.go(self.rt._allowed(["money"], "a trade went ahead"))
        self.rt.nobody_here = lambda: True
        ok = self.go(self.rt.confirm_money("let the agent spend on Kraken"))
        self.assertFalse(ok)
        self.assertEqual(len(self.said()), 1)
        self.assertIn("Allowance reached", self.said()[0][1])
        self.assertFalse(any("could move real money" in (t[2] if len(t) > 2 else "") for t in self.rt.trace),
                         "the allowance stop comes before the nobody-here refusal")

    def test_a_test_or_rehearsal_never_counts_and_never_blocks_on_allowances(self):
        os.environ["RB_ALLOW_MESSAGES_DAILY"] = "1"
        self.rt.testing = True
        self.assertFalse(self.go(self.rt._allowed(["messages"], "send 1")))  # skipped, as tests always are
        self.assertFalse(self.counts_data(), "nothing is counted in a test")
        self.rt.testing = False
        self.rt.rehearsing = True
        self.assertFalse(self.go(self.rt._allowed(["messages"], "send 2")))
        self.assertFalse(self.counts_data(), "nothing is counted in a rehearsal")
        self.assertEqual(self.said(), [])

    def test_the_receipt_carries_the_kinds_and_the_count_comes_from_it(self):
        self.go(self.rt._allowed(["ha", "messages"], "send a notification to the TV"))
        rec = json.loads((pathlib.Path(self.tmp.name) / ".prog.receipts.jsonl").read_text(encoding="utf-8").strip())
        self.assertEqual(rec["kinds"], ["ha", "messages"])
        hours = self.counts_data()
        self.assertEqual(sum(e.get("ha", 0) for e in hours.values()), 1)
        self.assertEqual(sum(e.get("messages", 0) for e in hours.values()), 1)

    def test_kinds_outside_the_allowances_are_not_counted(self):
        self.assertTrue(self.go(self.rt._allowed(["files"], "save a file")))
        self.assertFalse(self.counts_data())
        self.assertIsNone(self.rt._action_allowance_problem(["files"]))

    def test_ask_first_actions_are_blocked_by_the_allowance_before_asking(self):
        os.environ["RB_ALLOW_MESSAGES_DAILY"] = "1"
        self.go(self.rt._allowed(["messages"], "send 1"))
        self.rt.ask_first.add("messages")
        asked = []

        async def approve(text):
            asked.append(text)
            return True
        self.rt.approve = approve
        self.assertFalse(self.go(self.rt._allowed(["messages"], "send 2")))
        self.assertEqual(asked, [], "no asking once the allowance is reached")

    def test_doctor_lines_say_each_kind_s_allowance_and_count(self):
        os.environ["RB_ALLOW_MESSAGES_DAILY"] = "2"
        lines = self.rt.action_allowance_lines()
        self.assertEqual(lines[0], "messages: 0 of 10 hourly, 0 of 2 daily, counted on this computer")
        self.go(self.rt._allowed(["messages"], "send 1"))
        self.assertIn("1 of 2 daily", self.rt.action_allowance_lines()[0])
        self.assertEqual(lines[1], "home actions: 0 of 30 hourly, 0 of 200 daily, counted on this computer")
        self.assertEqual(lines[2], "money moves: 0 of 1 hourly, 0 of 5 daily, counted on this computer")


if __name__ == "__main__":
    unittest.main()
