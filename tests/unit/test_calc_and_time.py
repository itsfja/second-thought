"""calculate and time_plus: the agent's sums and clock times (the page has the same rules)."""
import unittest

import support  # noqa: F401
from second_thought.core import RunError, calc_text, time_plus_text


class Calculate(unittest.TestCase):
    def test_answers(self):
        cases = {"(350 / 500) * 100": "70", "2 + 3 * 4": "14", "2 ^ 3 ^ 2": "512", "-2 ^ 2": "-4", "10 / 4": "2.5",
                 "round(2.345, 2)": "2.35", "round(2.5)": "3", "min(3, 1, 2) + max(4, 5)": "6", "sqrt(16) + abs(-1)": "5",
                 "floor(2.7) + ceil(2.1)": "5", "3 × 4 ÷ 2": "6", "0.1 + 0.2": "0.3", ".5 * 4": "2"}
        for expr, want in cases.items():
            with self.subTest(expr=expr):
                self.assertEqual(calc_text(expr), f"{expr} = {want}")

    def test_pi(self):
        self.assertEqual(calc_text("pi"), "pi = 3.14159265359")

    def test_mistakes_are_plain_run_errors(self):
        for expr, why in [("", "empty"), ("1 / 0", "divides by zero"), ("2 +", "ends too soon"), ("(1 + 2", "ends too soon"),
                          ("sqrt(-1)", "negative"), ("import os", "don't know"), ("1 2", "don't understand"),
                          ("abs(1, 2)", "takes one number")]:
            with self.subTest(expr=expr):
                with self.assertRaises(RunError) as e:
                    calc_text(expr)
                self.assertIn(why, str(e.exception))


class TimePlus(unittest.TestCase):
    def test_clock_times(self):
        cases = [("09:30", 270, "14:00"), ("9.30", "30", "10:00"), ("23:30", 60, "00:30 (next day)"),
                 ("00:15", -30, "23:45 (the day before)"), ("10:00", 3 * 1440, "10:00 (3 days later)"),
                 ("10:00", -2 * 1440, "10:00 (2 days earlier)"), ("9:00 pm", 30, "21:30"), ("12:00 am", 0, "00:00"),
                 ("12:00 pm", 0, "12:00")]
        for when, add, want in cases:
            with self.subTest(when=when, add=add):
                self.assertEqual(time_plus_text(when, add), want)

    def test_dates(self):
        self.assertEqual(time_plus_text("2026-10-10 22:00", 600), "2026-10-11 08:00 (Sunday)")
        self.assertEqual(time_plus_text("2026-02-28T23:00", 120), "2026-03-01 01:00 (Sunday)")

    def test_mistakes(self):
        for when in ("noon", "25:00", "10:61", "13:00 pm", "2026-02-30 10:00"):
            with self.subTest(when=when):
                with self.assertRaises(RunError):
                    time_plus_text(when, 10)


if __name__ == "__main__":
    unittest.main()
