"""What a run cost: each service's prices (dated, with a source), a call's cost, and the end line."""
import datetime
import unittest

import support  # noqa: F401
from second_thought.providers import MODELS, PRICES, SERVICES, call_cost, money
from second_thought.runtime import Runtime


class Prices(unittest.TestCase):
    def test_every_price_is_dated_sourced_and_for_a_model_the_service_uses(self):
        for s in SERVICES:
            if not s.get("prices"):
                continue
            with self.subTest(service=s["name"]):
                datetime.date.fromisoformat(s["prices_checked"])
                self.assertTrue(s["prices_source"].startswith("https://"))
                models = {m for m, *_ in s["tiers"].values()}
                for model, (p_in, p_out) in s["prices"].items():
                    self.assertIn(model, models, "a price for a model none of its tiers uses")
                    self.assertTrue(0 <= p_in <= 100 and 0 <= p_out <= 400, "dollars per million tokens")

    def test_tiers_get_their_models_price(self):
        self.assertEqual(MODELS["default"], "claude-sonnet-5-5")
        self.assertEqual(PRICES["default"], (2, 10))
        self.assertNotIn("llama-default", PRICES, "a service with no prices has none")

    def test_a_calls_cost(self):
        self.assertAlmostEqual(call_cost("default", 1_000_000, 100_000), 2 + 1)
        self.assertAlmostEqual(call_cost("default", 1200, 300), (1200 * 2 + 300 * 10) / 1e6)
        self.assertIsNone(call_cost("llama-default", 1000, 1000))

    def test_money(self):
        self.assertEqual(money(0.0004), "under $0.01")
        self.assertEqual(money(0.031), "about $0.03")
        self.assertEqual(money(1.2), "about $1.20")


class EndLine(unittest.TestCase):
    def test_cost_shows_only_when_every_call_had_a_price(self):
        rt = Runtime()
        rt.usage, rt.cost = {"Claude": [1200, 300]}, [0.0054, True]
        self.assertEqual(rt.cost_text(), " · about $0.01 at list prices")
        rt.cost = [0.0054, False]
        self.assertEqual(rt.cost_text(), "", "a call with no known price means no total, rather than a wrong one")
        rt.usage, rt.cost = {}, [0.0, True]
        self.assertEqual(rt.cost_text(), "")


if __name__ == "__main__":
    unittest.main()
