"""A review loop that's stuck (#331): the same problems after two revisions in a row stop it, saying why."""
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


class Loop(unittest.TestCase):
    def run_loop(self, reviews, rounds=3):
        r = Runtime()
        r.reset()
        logged = []
        r.log = lambda name, text="", pill="", **k: logged.append((name, pill))
        replies = iter(reviews)

        async def fake_call(prompt, schema=None, *a, **k):
            return {"approved": False, "problems": next(replies)}
        r._call = fake_call

        async def go():
            r.set_task("t")
            r.set_draft("v1")
            n = 1
            with r.reviewing():
                for rnd in range(1, rounds + 2):
                    if await r.review("clear", "Review, round " + str(rnd), in_loop=True):
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

    def test_stuck_after_two_unchanged_rounds(self):
        r, logged = self.run_loop([["a", "b"], ["a", "b"], ["b", "a"], ["a", "b"]])
        self.assertIn(("Review stuck", "stuck"), logged)
        self.assertEqual(r.draft, "v3")
        self.assertTrue(r.out_of_rounds_hit)

    def test_progress_keeps_going(self):
        r, logged = self.run_loop([["a", "b"], ["a"], ["a"], ["c"]])
        self.assertNotIn("Review stuck", [n for n, _ in logged])


if __name__ == "__main__":
    unittest.main()
