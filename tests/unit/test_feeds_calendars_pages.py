"""News feeds, iCal calendars, free time and web page text."""
import datetime
import unittest

import support  # noqa: F401
from second_thought.connectors import calendar_events, event_line, free_slots, page_text, parse_day, parse_feed
from second_thought.core import RunError

D = datetime.datetime

RSS = """<?xml version="1.0"?><rss version="2.0"><channel><title>Bakery news</title>
<item><title>Older</title><link>https://example.com/1</link><pubDate>Mon, 05 Oct 2026 09:00:00 GMT</pubDate>
<description>&lt;p&gt;Rye &amp;amp; spelt&lt;/p&gt;</description></item>
<item><title>Newer</title><link>https://example.com/2</link><pubDate>Thu, 08 Oct 2026 09:00:00 GMT</pubDate></item>
</channel></rss>"""

ATOM = """<feed xmlns="http://www.w3.org/2005/Atom"><title>Atom bakes</title>
<entry><title>Only</title><link rel="alternate" href="https://example.com/a"/><updated>2026-10-01T12:00:00Z</updated>
<summary>Crumb shots</summary></entry></feed>"""


class Feeds(unittest.TestCase):
    def test_rss_newest_first(self):
        title, items = parse_feed(RSS)
        self.assertEqual(title, "Bakery news")
        self.assertEqual([i["title"] for i in items], ["Newer", "Older"])
        self.assertEqual(items[1]["link"], "https://example.com/1")
        self.assertEqual(items[1]["summary"], "Rye & spelt")
        self.assertIsInstance(items[0]["date"], D)
        self.assertIsNone(items[0]["date"].tzinfo)

    def test_atom(self):
        title, items = parse_feed(ATOM)
        self.assertEqual((title, items[0]["link"], items[0]["summary"]), ("Atom bakes", "https://example.com/a", "Crumb shots"))

    def test_not_a_feed(self):
        for raw in ("<html><body>hi</body></html>", "not xml at all"):
            with self.subTest(raw=raw):
                with self.assertRaises(RunError):
                    parse_feed(raw)


def ics(*events):
    return "BEGIN:VCALENDAR\r\n" + "".join("BEGIN:VEVENT\r\n" + e.strip().replace("\n", "\r\n") + "\r\nEND:VEVENT\r\n" for e in events) + "END:VCALENDAR\r\n"


class Calendars(unittest.TestCase):
    WEEK = (D(2026, 10, 12), D(2026, 10, 19))  # Monday to Monday

    def test_single_and_all_day(self):
        cal = ics("SUMMARY:Feed starter\nDTSTART:20261013T090000\nDTEND:20261013T091500\nLOCATION:Kitchen\\, home",
                  "SUMMARY:Bake day\nDTSTART;VALUE=DATE:20261014\nDTEND;VALUE=DATE:20261016")
        evs = calendar_events(cal, *self.WEEK)
        self.assertEqual([e["title"] for e in evs], ["Feed starter", "Bake day"])
        self.assertEqual(event_line(evs[0]), "09:00–09:15  Feed starter (Kitchen, home)")
        self.assertEqual(event_line(evs[1]), "all day (2 days)  Bake day")

    def test_long_lines_are_unfolded(self):
        cal = ics("SUMMARY:A very long\n  title\nDTSTART:20261013T090000\nDTEND:20261013T100000")
        self.assertEqual(calendar_events(cal, *self.WEEK)[0]["title"], "A very long title")

    def test_weekly_repeats_with_exceptions_and_a_moved_one(self):
        cal = ics("UID:x\nSUMMARY:Stretch and fold\nDTSTART:20261005T080000\nDURATION:PT30M\nRRULE:FREQ=WEEKLY;BYDAY=MO,WE,FR\n"
                  "EXDATE:20261014T080000",
                  "UID:x\nSUMMARY:Stretch and fold (late)\nRECURRENCE-ID:20261016T080000\nDTSTART:20261016T110000\nDTEND:20261016T113000")
        got = [(e["start"], e["title"]) for e in calendar_events(cal, *self.WEEK)]
        self.assertEqual(got, [(D(2026, 10, 12, 8), "Stretch and fold"), (D(2026, 10, 16, 11), "Stretch and fold (late)")])

    def test_count_until_and_cancelled(self):
        cal = ics("SUMMARY:Daily\nDTSTART:20261011T070000\nDTEND:20261011T071000\nRRULE:FREQ=DAILY;COUNT=3",
                  "SUMMARY:Until\nDTSTART:20261012T190000\nDTEND:20261012T193000\nRRULE:FREQ=DAILY;INTERVAL=2;UNTIL=20261016",
                  "SUMMARY:Off\nSTATUS:CANCELLED\nDTSTART:20261013T100000\nDTEND:20261013T110000")
        got = [(e["title"], e["start"].day) for e in calendar_events(cal, *self.WEEK)]
        # Daily: the 11th (before the view), 12th and 13th, then COUNT stops it. Until: every other day to the 16th.
        self.assertEqual(got, [("Daily", 12), ("Until", 12), ("Daily", 13), ("Until", 14), ("Until", 16)])

    def test_monthly_skips_short_months(self):
        cal = ics("SUMMARY:Month end\nDTSTART:20261031T120000\nDTEND:20261031T130000\nRRULE:FREQ=MONTHLY")
        got = [e["start"] for e in calendar_events(cal, D(2026, 10, 1), D(2027, 2, 1))]
        self.assertEqual(got, [D(2026, 10, 31, 12), D(2026, 12, 31, 12), D(2027, 1, 31, 12)])

    def test_free_slots(self):
        day = D(2026, 10, 13)
        evs = [{"start": day.replace(hour=10), "end": day.replace(hour=11), "all_day": False},
               {"start": day.replace(hour=10, minute=30), "end": day.replace(hour=12), "all_day": False},
               {"start": day, "end": day + datetime.timedelta(days=1), "all_day": True}]
        got = [(a.strftime("%H:%M"), b.strftime("%H:%M")) for a, b in free_slots(evs, day, "09:00", "17:00", 60)]
        self.assertEqual(got, [("09:00", "10:00"), ("12:00", "17:00")])
        self.assertEqual(len(free_slots(evs, day, "09:00", "17:00", 61)), 1)
        with self.assertRaises(RunError):
            free_slots(evs, day, "nine", "17:00", 30)

    def test_parse_day(self):
        today = D.now().replace(hour=0, minute=0, second=0, microsecond=0)
        self.assertEqual(parse_day("today"), today)
        self.assertEqual(parse_day(""), today)
        self.assertEqual(parse_day("Tomorrow"), today + datetime.timedelta(days=1))
        sat = parse_day("sat")
        self.assertEqual(sat.weekday(), 5)
        self.assertTrue(0 <= (sat - today).days < 7)
        self.assertEqual(parse_day("2026-10-10"), D(2026, 10, 10))
        with self.assertRaises(RunError):
            parse_day("someday")


class Pages(unittest.TestCase):
    def test_html_to_text(self):
        html = ("<html><head><title> My &amp; bakery </title><style>p{}</style></head><body><script>x=1</script>"
                "<h1>Loaves</h1><p>Rye&nbsp;bread</p><!-- hidden --><ul><li>one</li><li>two</li></ul></body></html>")
        title, text = page_text(html, "text/html")
        self.assertEqual(title, "My & bakery")
        self.assertEqual(text, "Loaves\nRye bread\none\ntwo")

    def test_plain_text_passes_through(self):
        self.assertEqual(page_text("just   words\n", "text/plain"), ("", "just words"))


if __name__ == "__main__":
    unittest.main()
