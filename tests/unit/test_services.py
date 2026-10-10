"""SERVICES, the one list of model services: well formed, and enough on its own to add a service."""
import json
import os
import pathlib
import shutil
import sys
import tempfile
import unittest

import support
from second_thought.providers import MODEL_LABELS, MODELS, NO_VISION, PROVIDERS, SERVICES, VISION_MODELS

sys.path.insert(0, str(support.ROOT / "tools"))
import sync  # noqa: E402

APIS = {"anthropic", "gemini", "openai", "perplexity"}
FIELDS = {"name", "who", "key_label", "menu", "api", "prefix", "any_model", "base", "base_env", "keys", "signup", "headers",
          "tiers", "no_vision", "vision", "pip", "note", "setup", "always"}


class WellFormed(unittest.TestCase):
    def test_each_service_has_what_it_needs(self):
        for s in SERVICES:
            with self.subTest(service=s.get("name")):
                self.assertIn(s["api"], APIS)
                self.assertTrue(s["name"] and s["menu"] and s["keys"])
                self.assertIn("default", s["tiers"])
                self.assertLessEqual(set(s["tiers"]), {"quick", "default", "complex"})
                for size, t in s["tiers"].items():
                    self.assertIn(len(t), (2, 3), f"{size}: (model, label) or (model, label, menu label)")
                    self.assertTrue(all(isinstance(x, str) and x for x in t))
                if s["api"] in ("openai", "perplexity"):
                    self.assertTrue(s["base"].startswith(("http://", "https://")) and s["base_env"].endswith("_BASE_URL"))
                if s.get("vision"):
                    self.assertEqual(len(s["vision"]), 2)
                for m in s.get("no_vision", ()):
                    self.assertIn(m, [t[0] for t in s["tiers"].values()], "no_vision should name one of its own models")
                self.assertEqual(set(s) - FIELDS, set(), "fields providers.py doesn't describe")

    def test_names_and_prefixes_dont_clash(self):
        names = [s["name"] for s in SERVICES]
        self.assertEqual(len(names), len(set(names)))
        prefixes = [s["prefix"] for s in SERVICES if s["prefix"]]
        for a in prefixes:
            self.assertTrue(a.endswith("-"))
            self.assertEqual([b for b in prefixes if b.startswith(a)], [a], f"{a} would also match another service's tiers")
        self.assertEqual([s["name"] for s in SERVICES if not s["prefix"]], ["Claude"])

    def test_tables_come_from_services(self):
        self.assertEqual(MODELS["default"], "claude-sonnet-5-5")
        self.assertEqual((MODELS["xai-default"], MODEL_LABELS["xai-default"]), ("grok-4.3", "Grok 4.3"))
        self.assertEqual(len(MODELS), sum(len(s["tiers"]) for s in SERVICES))
        self.assertEqual(set(PROVIDERS), {s["name"] for s in SERVICES if s["api"] in ("openai", "perplexity")})
        self.assertEqual(PROVIDERS["Qwen"]["key_env"], "DASHSCOPE_API_KEY")
        self.assertEqual(PROVIDERS["OpenRouter"]["headers"], {"X-OpenRouter-Title": "Second Thought"})
        self.assertIsNone(PROVIDERS["Llama"]["signup"])  # a key is optional
        self.assertEqual(set(VISION_MODELS), {"Qwen", "Hugging Face", "Groq"})
        self.assertIn("deepseek-v4-pro", NO_VISION)

    def test_page_gets_the_same_list(self):
        self.assertEqual(json.loads(sync.services_json()), json.loads(json.dumps(SERVICES)))
        page = (support.ROOT / "second-thought.html").read_text(encoding="utf-8")
        self.assertIn('<script type="application/json" id="services">\n' + sync.services_json() + "</script>", page)


class AddingAService(unittest.TestCase):
    """The promise in providers.py: an OpenAI-style service added to SERVICES needs nothing else changed."""

    def test_one_entry_is_enough(self):
        acme = ('    {"name": "Acme", "menu": "Acme", "api": "openai", "prefix": "acme-", "base": "https://api.acme.test/v1",\n'
                '     "base_env": "ACME_BASE_URL", "keys": ["ACME_API_KEY"], "signup": "https://acme.test/keys",\n'
                '     "note": ["Acme calls go to Acme."], "tiers": {"default": ("acme-1", "Acme One")}},\n')
        with tempfile.TemporaryDirectory() as tmp:
            pkg = pathlib.Path(tmp) / "second_thought"
            shutil.copytree(sync.PACKAGE, pkg, ignore=shutil.ignore_patterns("__pycache__"))
            src = (pkg / "providers.py").read_text(encoding="utf-8")
            end = src.index("\n]\nTIER_NAMES")
            (pkg / "providers.py").write_text(src[:end + 1] + acme + src[end + 1:], encoding="utf-8")
            old = sync.PACKAGE, sync.SERVICES
            sync.PACKAGE, sync.SERVICES = pkg, pkg / "providers.py"
            try:
                runtime, services = sync.bundle(), json.loads(sync.services_json())
            finally:
                sync.PACKAGE, sync.SERVICES = old
        self.assertEqual(services[-1]["name"], "Acme")
        ns = {"__name__": "rt"}
        env = dict(os.environ)
        os.environ["ACME_API_KEY"] = "k"
        try:
            exec(compile(runtime, "rt", "exec"), ns)  # noqa: S102
        finally:
            os.environ.clear()
            os.environ.update(env)
        self.assertEqual(ns["MODELS"]["acme-default"], "acme-1")
        self.assertEqual(ns["model_label"]("acme-default"), "Acme One")
        self.assertEqual(ns["PROVIDERS"]["Acme"]["base"], "https://api.acme.test/v1")
        self.assertEqual(ns["PROVIDERS"]["Acme"]["key"], "k")

        calls = []

        async def fake_openai(self, provider, model, *a, **k):
            calls.append((provider, model))
            return "hi"
        R = ns["Runtime"]
        R._call_openai = fake_openai
        r = R()
        r.reset()
        import asyncio
        self.assertEqual(asyncio.run(r._call_tier("acme-default", "hello", False, None, None, False)), "hi")
        self.assertEqual(calls, [("Acme", "acme-1")])


if __name__ == "__main__":
    unittest.main()
