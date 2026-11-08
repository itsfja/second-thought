"""Fuzz tests for the parsers that read outside input (#313), with the standard library only.

Each parser gets a few thousand random and mutated inputs, from a fixed seed so a failure repeats. The only allowed
outcomes are a result or a RunError (second-thought.ini: a clear exit), never another exception or a hang.
FUZZ_ROUNDS=20000 python -m unittest test_fuzz  runs more."""
import asyncio
import datetime
import faulthandler
import os
import random
import tempfile
import unittest

import support
from second_thought.connectors import calendar_events, parse_day, parse_feed
from second_thought.core import RunError, _WebSocket, _parse_json, seen_addresses
from second_thought.mcp import mcp_result_text
from second_thought.settings import _read_ini, _settings_value

ROUNDS = int(os.environ.get("FUZZ_ROUNDS", "2000"))

RSS = """<?xml version="1.0"?><rss version="2.0"><channel><title>Baking</title><item><title>Rye</title>
<link>https://example.com/rye</link><pubDate>Tue, 10 Nov 2026 09:00:00 GMT</pubDate><description>Long proof &amp; more</description></item>
</channel></rss>"""
ATOM = """<feed xmlns="http://www.w3.org/2005/Atom"><title>Tech</title><entry><title>New</title><link href="https://example.com/x"/>
<updated>2026-11-10T09:00:00Z</updated><summary type="html">&lt;b&gt;bold&lt;/b&gt;</summary></entry></feed>"""
ICS = """BEGIN:VCALENDAR\r\nBEGIN:VEVENT\r\nDTSTART;TZID=Europe/London:20261110T090000\r\nDTEND;TZID=Europe/London:20261110T100000\r
SUMMARY:Bake\\, rye\r\nRRULE:FREQ=WEEKLY;BYDAY=MO,TU;COUNT=5\r\nEXDATE:20261117T090000Z\r\nLOCATION:Kitchen\r\nEND:VEVENT\r
BEGIN:VEVENT\r\nDTSTART;VALUE=DATE:20261111\r\nSUMMARY:All day\r\nRECURRENCE-ID:20261111\r\nEND:VEVENT\r\nEND:VCALENDAR\r\n"""
INI = "[keys]\nANTHROPIC_API_KEY = sk-x\n[run]\ncurrency = gbp      show costs in…\n; budget = 1000\nsave_log = yes\n"
JSON = '{"done": true, "answer": "Rye [https://example.com] ```json\\n{\\"a\\": [1, 2]}```"}'
TOKENS = ["<item>", "</item>", "<entry>", "<![CDATA[", "&amp;", "&#x0;", "BEGIN:VEVENT", "END:VEVENT", "RRULE:FREQ=DAILY;COUNT=999999",
          "RRULE:FREQ=MONTHLY;INTERVAL=0", "RRULE:FREQ=YEARLY;UNTIL=99991231", "DTSTART:", "DTSTART;TZID=Nowhere/Land:", ";VALUE=DATE:",
          "99999999T999999Z", "00000000", "\r\n ", "\\n", "[", "]", "=", ";", "#", "{", "}", "\"", "```", "\x00", "﻿", "é", "𒀭",
          "-1", "1e999", "NaN", "9" * 40, "https://", "http://[", "%(x)s", "\n"]


def mutate(rng, text):
    s = list(text)
    for _ in range(rng.randint(1, 8)):
        op, i = rng.random(), rng.randint(0, len(s))
        if op < 0.25 and s:
            del s[i - 1:i - 1 + rng.randint(1, 20)]
        elif op < 0.5:
            s[i:i] = list(rng.choice(TOKENS))
        elif op < 0.7 and s:
            j = rng.randint(0, len(s))
            s[i:i] = s[min(i, j):max(i, j)][:200]  # a chunk repeated
        elif op < 0.85 and s:
            s[i - 1] = chr(rng.randint(0, 0x2FFF))
        else:
            s[i:i] = [chr(rng.randint(32, 126)) for _ in range(rng.randint(1, 10))]
    return "".join(s)


def inputs(seeds, seed):
    rng = random.Random(seed)
    for n in range(ROUNDS):
        if n % 10 == 0:
            yield "".join(chr(rng.randint(0, 0x2FFF)) for _ in range(rng.randint(0, 300)))  # noise
        else:
            yield mutate(rng, rng.choice(seeds))


class Fuzz(unittest.TestCase):
    def setUp(self):
        faulthandler.dump_traceback_later(120, exit=True)  # a hang shows where it is, instead of stopping CI for hours

    def tearDown(self):
        faulthandler.cancel_dump_traceback_later()

    def survive(self, parse, seeds, seed, allowed=(RunError,)):
        for text in inputs(seeds, seed):
            try:
                parse(text)
            except allowed:
                pass
            except Exception as e:  # noqa: BLE001 - this is what the test is looking for
                self.fail(f"{type(e).__name__}: {e} from {text[:400]!r}")

    def test_feeds(self):
        self.survive(parse_feed, [RSS, ATOM], 1)
        self.survive(lambda t: parse_feed(t.encode("utf-8", "surrogatepass")), [RSS, ATOM], 2)

    def test_calendars(self):
        start = datetime.datetime(2026, 11, 1)
        self.survive(lambda t: calendar_events(t, start, start + datetime.timedelta(days=60)), [ICS], 3)

    def test_days(self):
        self.survive(parse_day, ["today", "tomorrow", "monday", "2026-11-10"], 4)

    def test_model_replies(self):
        self.survive(_parse_json, [JSON], 5)
        self.survive(seen_addresses, [JSON, RSS], 6)

    def test_settings_files(self):
        with tempfile.TemporaryDirectory(dir=support.TMP) as tmp:
            path = os.path.join(tmp, "second-thought.ini")

            def read(text):
                with open(path, "w", encoding="utf-8", errors="surrogatepass") as f:
                    f.write(text)
                for name, value in _read_ini(path):
                    _settings_value(name, value)
            self.survive(read, [INI], 7, allowed=(SystemExit,))  # a broken file: a clear message, and stop

    def test_mcp_results(self):
        import json
        seeds = [json.dumps({"content": [{"type": "text", "text": "ok"}, {"type": "image", "mimeType": "image/png"},
                                         {"type": "resource", "resource": {"uri": "file:///x", "text": "hi"}}, {"type": "resource_link", "uri": "u"}],
                             "structuredContent": {"a": 1}, "isError": False})]

        def parse(text):
            try:
                result = json.loads(text)
            except ValueError:
                return
            if isinstance(result, dict):  # what tools/call gives back; anything else is refused before this
                mcp_result_text(result)
        self.survive(parse, seeds, 8)

    def test_websocket_frames(self):
        def frame(payload, op=1, fin=True):
            n = len(payload)
            head = bytes([(0x80 if fin else 0) | op]) + (bytes([n]) if n < 126 else bytes([126]) + n.to_bytes(2, "big"))
            return head + payload

        class Writer:
            def write(self, data):
                pass

            async def drain(self):
                pass
        good = frame(b'{"type": "auth_required"}')
        seeds = [(good + frame(b"", op=9) + frame(b'{"a":', fin=False) + frame(b"1}", op=0)).decode("latin-1")]

        async def read(data):
            reader = asyncio.StreamReader()
            reader.feed_data(data)
            reader.feed_eof()
            ws = _WebSocket(reader, Writer())
            for _ in range(5):
                await ws.recv_json()
        self.survive(lambda t: asyncio.run(read(t.encode("latin-1", "replace"))), seeds, 9)


if __name__ == "__main__":
    unittest.main()
