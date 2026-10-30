"""calculate and time_plus: the agent's sums and clock times. The cases are in tests/parity/, which the page's own
tests (tests/editor/) read too, so both sides keep the same rules."""
import json
import pathlib
import unittest

import support  # noqa: F401
from second_thought.core import RunError, calc_text, time_plus_text

PARITY = pathlib.Path(__file__).resolve().parent.parent / "parity"
CALC = json.loads((PARITY / "calc.json").read_text(encoding="utf-8"))
TIME_PLUS = json.loads((PARITY / "time_plus.json").read_text(encoding="utf-8"))


class Calculate(unittest.TestCase):
    def test_answers(self):
        for expr, want in CALC["answers"]:
            with self.subTest(expr=expr):
                self.assertEqual(calc_text(expr), f"{expr} = {want}")

    def test_mistakes_are_plain_run_errors(self):
        for expr, why in CALC["mistakes"]:
            with self.subTest(expr=expr):
                with self.assertRaises(RunError) as e:
                    calc_text(expr)
                self.assertIn(why, str(e.exception))


class TimePlus(unittest.TestCase):
    def test_answers(self):
        for when, add, want in TIME_PLUS["answers"]:
            with self.subTest(when=when, add=add):
                self.assertEqual(time_plus_text(when, add), want)

    def test_mistakes(self):
        for when in TIME_PLUS["mistakes"]:
            with self.subTest(when=when):
                with self.assertRaises(RunError):
                    time_plus_text(when, 10)


if __name__ == "__main__":
    unittest.main()
