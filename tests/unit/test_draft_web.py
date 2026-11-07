"""'using the web' on write a first draft and revise (#332)."""
import asyncio
import unittest

import support  # noqa: F401
from second_thought.runtime import Runtime


class DraftWeb(unittest.TestCase):
    """'using the web' on write a first draft and revise (#332)."""
    def run_draft(self, task, web):
        r = Runtime()
        r.reset()
        logged, calls = [], []
        r.log = lambda name, text="", pill="", **k: logged.append(name)

        async def fake_call(prompt, want_json=False, picture=None, history=None, web=False):
            calls.append(web)
            return "draft"
        r._call = fake_call
        r.set_task(task)
        asyncio.run(r.generate(web=web))
        return logged, calls

    def test_web_reaches_the_model_call(self):
        self.assertEqual(self.run_draft("Sum up https://example.com/page", True)[1], [True])
        self.assertEqual(self.run_draft("Write a poem", False)[1], [False])

    def test_an_address_without_the_web_is_noted(self):
        self.assertIn("Web address in the task", self.run_draft("Sum up github.com/itsfja/second-thought", False)[0])
        self.assertNotIn("Web address in the task", self.run_draft("Sum up github.com/itsfja/second-thought", True)[0])
        self.assertNotIn("Web address in the task", self.run_draft("Write about e.g. sourdough", False)[0])


if __name__ == "__main__":
    unittest.main()
