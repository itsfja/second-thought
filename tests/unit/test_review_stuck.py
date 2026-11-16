"""A review loop that's stuck (#424): the same rule failing in two rounds running stops it, saying why. The best
draft is the one that meets the most rules. same_problem (#331) is still tested below for older exports."""
import asyncio
import unittest

import support  # noqa: F401
from second_thought.core import same_problem
from second_thought.runtime import Runtime


class SameProblem(unittest.TestCase):
    def test_wordings_of_one_problem(self):
        self.assertTrue(same_problem("Too long", "too long "))
        self.assertTrue(same_problem("The draft is not specific to github.com/itsfja/second-thought, offering only a generic checklist instead.",
                                     "The response is not specific to github.com/itsfja/second-thought; it provides a generic checklist rather than an analysis."))
        self.assertFalse(same_problem("Too long", "Has no title"))
        self.assertFalse(same_problem("", "anything"))


def verdict(clear, short, kind, problem="too vague"):
    """A review reply in the #424 shape: one verdict per rule."""
    return {"approved": clear and short and kind,
            "rules": [{"rule": "clear", "met": clear}, {"rule": "short", "met": short, "problem": "" if short else problem},
                      {"rule": "kind", "met": kind}],
            "problems": [] if (clear and short and kind) else [problem]}


class Loop(unittest.TestCase):
    CRITERIA = "clear; short; kind"

    def run_loop(self, replies, rounds=3):
        r = Runtime()
        r.reset()
        logged = []
        r.log = lambda name, text="", pill="", **k: logged.append((name, pill))
        replies = iter(replies)

        async def fake_call(prompt, schema=None, *a, **k):
            return next(replies)
        r._call = fake_call

        async def go():
            r.set_task("t")
            r.set_draft("v1")
            n = 1
            with r.reviewing():
                for rnd in range(1, rounds + 2):
                    if await r.review(self.CRITERIA, "Review, round " + str(rnd), in_loop=True):
                        break
                    if rnd > rounds:
                        r.out_of_rounds()
                        break
                    if r.stuck():
                        break
                    n += 1
                    r.set_draft("v" + str(n))
        asyncio.run(go())
        return r, logged

    def test_stuck_when_the_same_rule_fails_twice_running(self):
        # "short" fails in rounds 1, 2 and 3: revising can't fix it, so the loop stops and keeps its best draft (#424)
        r, logged = self.run_loop([verdict(True, False, True), verdict(True, False, True), verdict(True, False, True), verdict(True, True, True)])
        self.assertIn(("Review stuck", "stuck"), logged)
        self.assertTrue(r.out_of_rounds_hit)

    def test_progress_keeps_going(self):
        # a different rule fails each round, so the loop is not stuck
        r, logged = self.run_loop([verdict(True, False, True), verdict(True, True, False), verdict(False, True, True), verdict(True, True, True)])
        self.assertNotIn("Review stuck", [n for n, _ in logged])

    def test_best_draft_is_the_one_that_meets_the_most_rules(self):
        # round 1 meets 1 rule, round 2 meets 2, round 3 meets 1: out of rounds keeps round 2's draft (#424)
        r, logged = self.run_loop([verdict(False, False, True), verdict(False, True, True), verdict(False, False, True), verdict(False, False, True)], rounds=2)
        self.assertIn(("Kept the best draft", "best draft"), logged)
        self.assertEqual(r.draft, "v2")

    def test_rules_by_round_are_logged(self):
        r = Runtime()
        r.reset()
        logged = []
        r.log = lambda name, text="", pill="", **k: logged.append((name, text))
        replies = iter([verdict(True, False, True), verdict(True, True, True)])

        async def fake_call(prompt, schema=None, *a, **k):
            return next(replies)
        r._call = fake_call

        async def go():
            r.set_task("t")
            r.set_draft("v1")
            with r.reviewing():
                for rnd in range(1, 4):
                    if await r.review(self.CRITERIA, "Review, round " + str(rnd), in_loop=True):
                        break
                    if r.stuck():
                        break
                    r.set_draft("v" + str(rnd + 1))
        asyncio.run(go())
        table = [text for name, text in logged if name == "Rules by round"]
        self.assertTrue(table and "| Rule |" in table[0] and "Round 1" in table[0] and "Round 2" in table[0]
                        and "short" in table[0] and "not met" in table[0] and "met" in table[0],
                        f"the run log has the rules-by-round table: {table[:1]}")


if __name__ == "__main__":
    unittest.main()
