"""A budget in money (#241): 'limit this run to … US dollars' and budget_dollars stop a run once it has spent that much at
list prices, and refuse a model with no known price rather than run with no limit."""
import asyncio
import unittest

import support  # noqa: F401
from second_thought.core import RunError
from second_thought.providers import call_cost, dollars
from second_thought.runtime import Runtime


def runtime(tier="default", backups=()):
    rt = Runtime()
    rt.reset()
    rt.log = lambda *a, **k: None
    rt.tier = rt.primary = tier
    rt.backups = list(backups)
    rt.answered = []

    async def call_tier(t, prompt, want_json=False, picture=None, history=None, web=False):
        rt.answered.append(t)
        if t in rt.__dict__.get("failing", ()):
            raise RuntimeError("down")
        rt._count("Claude" if not t.startswith("llama") else "Llama", 100_000, 10_000)
        return "ok"
    rt._call_tier = call_tier
    return rt


def call(rt):
    return asyncio.run(rt._call_live("hello"))


class MoneyBudget(unittest.TestCase):
    def test_stops_once_spent(self):
        rt = runtime()
        rt.set_budget(0.5, "dollars")
        per_call = call_cost("default", 100_000, 10_000)  # $0.30 at Sonnet's list price
        self.assertAlmostEqual(per_call, 0.3)
        call(rt)
        call(rt)  # $0.30 spent, under $0.50: this call runs
        with self.assertRaises(RunError) as e:
            call(rt)  # $0.60 spent
        self.assertIn("$0.50", str(e.exception))
        self.assertIn("about $0.60", str(e.exception))
        self.assertEqual(len(rt.answered), 2)

    def test_tokens_stay_the_default(self):
        rt = runtime()
        rt.set_budget(1000)
        self.assertEqual((rt.budget, rt.budget_dollars), (1000, 0))
        call(rt)
        with self.assertRaises(RunError):
            call(rt)

    def test_a_model_with_no_price_is_refused(self):
        rt = runtime("llama-default")
        rt.set_budget(1, "dollars")
        with self.assertRaises(RunError) as e:
            call(rt)
        self.assertIn("no known price", str(e.exception))
        self.assertEqual(rt.answered, [], "refused before calling it, rather than running unlimited")

    def test_an_unpriced_backup_is_left_out(self):
        rt = runtime("default", ["llama-default", "quick"])
        rt.failing = {"default"}
        rt.set_budget(1, "dollars")
        call(rt)
        self.assertEqual(rt.answered, ["default", "quick"])

    def test_an_unpriced_call_before_the_budget_stops_the_run(self):
        rt = runtime("llama-default")
        call(rt)  # no budget yet, so it runs, and the run's cost is no longer known
        rt.tier = rt.primary = "default"
        rt.set_budget(1, "dollars")
        with self.assertRaises(RunError) as e:
            call(rt)
        self.assertIn("already used has no known price", str(e.exception))
        self.assertEqual(rt.answered, ["llama-default"])

    def test_zero_means_no_limit(self):
        rt = runtime()
        rt.set_budget(0, "dollars")
        for _ in range(4):
            call(rt)
        self.assertEqual(len(rt.answered), 4)

    def test_amounts(self):
        self.assertEqual(dollars(2), "$2.00")
        self.assertEqual(dollars(1234.5), "$1,234.50")
        self.assertEqual(dollars(0.0004), "$0.0004", "under a cent shows its digits, not $0.00")


if __name__ == "__main__":
    unittest.main()
