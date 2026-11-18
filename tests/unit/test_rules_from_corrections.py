"""Rules from corrections (#428), with a stand-in keyboard: saying no at an approve step asks why in a sentence and
offers the reason as a new rule — saved beside the program (.<prog>.rules.json) so reviews check it without the
program file changing, with the line to add on the page shown. On the page the same rule is added to the review
block's rules (tested in tests/editor)."""
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


class OfferRule(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.rules_file = pathlib.Path(self.tmp.name) / ".prog.rules.json"
        patcher = patch.object(Runtime, "_rules_path", staticmethod(lambda: str(self.rules_file)))
        patcher.start()
        self.addCleanup(patcher.stop)
        self.r = Runtime()
        self.r.reset()
        self.r.testing = False
        self.logs = []
        self.r.log = lambda *a, **k: self.logs.append(a)

    def drive(self, answers, coro):
        it = iter(answers)

        async def fake_input(prompt):
            return next(it)
        self.r._input = fake_input
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            result = asyncio.run(coro)
        return result, out.getvalue()

    def test_a_no_offers_the_reason_as_a_rule_and_saves_it_beside_the_program(self):
        result, out = self.drive(["n", "prices in pounds, not dollars", "y"], self.r._approve_live("the draft", offer=True))
        self.assertIs(result, False)
        self.assertEqual(json.loads(self.rules_file.read_text(encoding="utf-8")), ["prices in pounds, not dollars"])
        self.assertIn("Line to add to the review block's rules on the page: prices in pounds, not dollars", out)
        self.assertTrue(any(a[0] == "New rule" for a in self.logs), self.logs)

    def test_declining_the_offer_saves_nothing(self):
        result, out = self.drive(["n", "too long", "n"], self.r._approve_live("the draft", offer=True))
        self.assertIs(result, False)
        self.assertFalse(self.rules_file.exists())
        self.assertNotIn("Line to add", out)

    def test_an_empty_why_asks_nothing_more(self):
        result, out = self.drive(["n", ""], self.r._approve_live("the draft", offer=True))
        self.assertIs(result, False)
        self.assertFalse(self.rules_file.exists())

    def test_the_same_rule_is_not_saved_twice(self):
        self.rules_file.write_text(json.dumps(["clear"]), encoding="utf-8")
        self.drive(["n", "clear", "yes"], self.r._approve_live("the draft", offer=True))
        self.assertEqual(json.loads(self.rules_file.read_text(encoding="utf-8")), ["clear"])

    def test_reviews_check_the_rules_saved_beside_the_program(self):
        self.rules_file.write_text(json.dumps(["prices in pounds, not dollars"]), encoding="utf-8")
        self.r.draft = "The price is $5."
        prompts = []

        async def fake_call(prompt, schema=None, *a, **k):
            prompts.append(prompt)
            return {"approved": True, "problems": []}
        self.r._call = fake_call
        asyncio.run(self.r.review("clear"))
        asyncio.run(self.r.review("clear"))
        self.assertTrue(all("clear" in p and "prices in pounds, not dollars" in p for p in prompts), prompts)
        notes = [a for a in self.logs if a[0] == "New rule"]
        self.assertEqual(len(notes), 1, f"the saved-rules note is logged once per run: {self.logs}")
        self.assertIn("1 rules saved beside the program are checked too.", notes[0][1])

    def test_a_review_without_saved_rules_says_nothing(self):
        self.r.draft = "fine."
        self.r._call = lambda *a, **k: asyncio.sleep(0, {"approved": True, "problems": []})

        async def call(prompt, schema=None, *a, **k):
            return {"approved": True, "problems": []}
        self.r._call = call
        asyncio.run(self.r.review("clear"))
        self.assertFalse([a for a in self.logs if a[0] == "New rule"], self.logs)


if __name__ == "__main__":
    unittest.main()
