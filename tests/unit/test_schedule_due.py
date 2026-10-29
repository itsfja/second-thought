"""--run-schedule: whether a 'when it's' script is due, for schedulers like GitHub Actions that start it late, or at both
the winter and summer times."""
import datetime
import unittest

import support  # noqa: F401
from second_thought.runtime import Runtime

FRI, SAT = datetime.datetime(2026, 10, 30), datetime.datetime(2026, 10, 31)  # a Friday and a Saturday


def at(day, h, m):
    return day.replace(hour=h, minute=m)


class ScheduleDue(unittest.TestCase):
    def test_runs_up_to_an_hour_late(self):
        s = ("time", 18, 0, "every", None)
        for when, due in [(at(FRI, 18, 0), True), (at(FRI, 18, 40), True), (at(FRI, 18, 59), True),
                          (at(FRI, 17, 0), False), (at(FRI, 19, 0), False), (at(FRI, 17, 59), False)]:
            with self.subTest(when=when):
                self.assertEqual(Runtime.schedule_due(s, when), due)

    def test_days(self):
        self.assertTrue(Runtime.schedule_due(("time", 9, 0, "weekdays", None), at(FRI, 9, 5)))
        self.assertFalse(Runtime.schedule_due(("time", 9, 0, "weekdays", None), at(SAT, 9, 5)))
        self.assertTrue(Runtime.schedule_due(("time", 9, 0, "weekends", None), at(SAT, 9, 5)))
        self.assertFalse(Runtime.schedule_due(("time", 9, 0, "weekends", None), at(FRI, 9, 5)))

    def test_late_past_midnight_counts_the_day_before(self):
        s = ("time", 23, 30, "weekdays", None)
        self.assertTrue(Runtime.schedule_due(s, at(SAT, 0, 10)))   # Friday's 23:30, started 40 minutes late
        self.assertFalse(Runtime.schedule_due(s, at(SAT, 0, 40)))  # more than an hour late
        self.assertFalse(Runtime.schedule_due(s, at(datetime.datetime(2026, 11, 1), 0, 10)))  # Saturday's: not a weekday


if __name__ == "__main__":
    unittest.main()
