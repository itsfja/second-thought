"""How expensive each model is, and who makes it (#264): price bands from list prices, free for a model run on this
computer, 'price unknown' without a price, and bylines for routers' models."""
import os
import unittest

import support  # noqa: F401
from second_thought.providers import BANDS, PRICES, SERVICES, _tier, band_text, maker_of, model_byline, price_band


class Bands(unittest.TestCase):
    def test_claude_from_its_prices(self):
        self.assertEqual([price_band(t) for t in ("quick", "default", "complex")], ["budget", "standard", "premium"])

    def test_every_priced_tier_has_a_band_and_unpriced_ones_none(self):
        for s in SERVICES:
            for k in s["tiers"]:
                tier = _tier(s, k)
                with self.subTest(tier=tier):
                    if tier in PRICES:
                        self.assertIn(price_band(tier), ("free", "budget", "standard", "premium"))
                    elif s["name"] != "Llama":
                        self.assertIsNone(price_band(tier))
                        self.assertEqual(band_text(tier), "price unknown")

    def test_newly_priced_services_have_bands(self):
        # #243: the services' own price pages
        self.assertEqual(price_band("openai-complex"), "premium")
        self.assertEqual(price_band("xai-complex"), "standard")
        self.assertEqual([price_band(f"mistral-{k}") for k in ("quick", "default", "complex")], ["budget", "standard", "budget"])
        self.assertEqual(price_band("kimi-complex"), "standard")
        self.assertIsNone(price_band("kimi-default"), "Kimi K2.6 has no published price")

    def test_prices_come_from_the_services_own_pages(self):
        third_party = ("computeprices.com", "morphllm.com", "computingforgeeks.com")
        for s in SERVICES:
            if s.get("prices"):
                with self.subTest(service=s["name"]):
                    self.assertFalse(any(t in s["prices_source"] for t in third_party), s["prices_source"])

    def test_bands_are_in_order(self):
        tops = [top for top, _ in BANDS]
        self.assertEqual(tops, sorted(tops))
        self.assertEqual([name for _, name in BANDS], ["free", "budget", "standard"])

    def test_llama_is_free_only_on_this_computer(self):
        saved = os.environ.get("LLAMA_BASE_URL")
        try:
            os.environ.pop("LLAMA_BASE_URL", None)
            self.assertEqual(price_band("llama-default"), "free")
            os.environ["LLAMA_BASE_URL"] = "https://llama.example.com/v1"
            self.assertIsNone(price_band("llama-default"), "someone else's server may charge")
        finally:
            if saved is None:
                os.environ.pop("LLAMA_BASE_URL", None)
            else:
                os.environ["LLAMA_BASE_URL"] = saved


class Makers(unittest.TestCase):
    def test_every_service_says_who_makes_its_models(self):
        for s in SERVICES:
            with self.subTest(service=s["name"]):
                self.assertTrue(s.get("maker") or "makers" in s)

    def test_routers_name_the_maker_and_the_service(self):
        self.assertEqual(maker_of("hf-quick"), "Google")
        self.assertEqual(model_byline("hf-complex"), "GPT-OSS 120B, by OpenAI, through Hugging Face")
        self.assertEqual(model_byline("groq-default").split(", by ")[1], "Meta, through Groq")

    def test_a_makers_own_service_is_just_the_model(self):
        self.assertEqual(model_byline("default"), "Claude, balanced")
        self.assertEqual(model_byline("gemini-default"), "Gemini Flash")

    def test_llama_here(self):
        self.assertTrue(model_byline("llama-default").endswith("by Meta, on this computer"))


if __name__ == "__main__":
    unittest.main()
