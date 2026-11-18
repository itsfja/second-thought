"""--report and --status (#435): the weekly account, read from the saved logs, the receipts and the spending record."""
import datetime
import hashlib
import io
import json
import pathlib
import sys
import tempfile
import time
import unittest
from contextlib import redirect_stdout

import support  # noqa: F401
import second_thought.spending as spending_mod
from second_thought.runtime import Runtime


def receipt_line(prev, what, when=None):
    rec = {"t": when if when is not None else time.time(), "what": what, "where": "", "how": "no asking", "prev": prev}
    raw = json.dumps(rec, sort_keys=True)
    return raw, hashlib.sha256(raw.encode()).hexdigest()


LOG_FIRST = """# demo: run log

- Started: 2026-11-18 09:00:00 (Run)
- Model calls: 2

## 1. Review [approved]

~~~~
Meets every criterion.
~~~~
"""

LOG_REVISED = """# demo: run log

- Started: 2026-11-18 10:00:00 (Run)
- Model calls: 5

## 1. Review, round 1 [needs work]

~~~~
- under 200 words
~~~~

## 2. Rules by round [table]

~~~~
| Rule | Round 1 | Round 2 |
|---|---|---|
| under 200 words | not met: too long | met |
| friendly tone | met | met |
~~~~

## 3. Review, round 2 [approved]

## 4. Not done [refused]

~~~~
send a Telegram message: no
~~~~
"""

LOG_FAILED = """# demo: run log

- Started: 2026-11-18 11:00:00 (Run)
- Stopped with an error: the model call failed

## 1. Review [failed]

~~~~
Out of rounds. Keeping the best effort.
~~~~
"""


class Report(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = pathlib.Path(self.tmp.name)
        self.prog = self.dir / "demo.py"
        self.prog.write_text("# demo\n", encoding="utf-8")
        self.saved_argv = sys.argv
        sys.argv = [str(self.prog)]
        self.saved_mem = spending_mod.MEMORY_FILE
        spending_mod.MEMORY_FILE = str(self.dir / "memory.json")
        self.rt = Runtime()

    def tearDown(self):
        sys.argv = self.saved_argv
        spending_mod.MEMORY_FILE = self.saved_mem
        self.tmp.cleanup()

    def log(self, text, when=None):
        logs = self.dir / "logs"
        logs.mkdir(exist_ok=True)
        when = when or datetime.datetime.now()
        (logs / f"demo-{when:%Y%m%d-%H%M%S}.md").write_text(text, encoding="utf-8")

    def receipts(self, whats, break_chain=False, when=None):
        prev = hashlib.sha256(b"").hexdigest()
        lines = []
        for w in whats:
            raw, prev = receipt_line(prev, w, when)
            lines.append(raw)
        if break_chain and len(lines) > 1:
            lines = lines[1:]  # a missing line: the next one's fingerprint no longer matches
        # bytes, not text: on Windows write_text would turn \n into \r\n and break the chain's fingerprints
        (self.dir / ".demo.receipts.jsonl").write_bytes(("\n".join(lines) + "\n").encode("utf-8"))

    def spend(self, usd):
        hour = datetime.datetime.now().strftime("%Y-%m-%dT%H")
        (self.dir / ".second-thought-spending.json").write_text(
            json.dumps({"keys": {"abc123": {"service": "Claude", "hours": {hour: usd}}}}), encoding="utf-8")

    def capture(self, fn, *a):
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = fn(*a)
        return rc, buf.getvalue()

    def test_report_counts_runs_reviews_refused_rules_receipts_and_cost(self):
        now = datetime.datetime.now()
        self.log(LOG_FIRST, when=now)
        self.log(LOG_REVISED, when=now + datetime.timedelta(minutes=1))
        self.log(LOG_FAILED, when=now + datetime.timedelta(minutes=2))
        self.receipts(["send a Telegram message: hi", "light.turn_on on light.kitchen"])
        self.spend(0.01)
        rc, out = self.capture(self.rt.show_report)
        self.assertEqual(rc, 0)
        self.assertIn("Report for demo, last 7 days:", out)
        self.assertIn("Runs: 3 saved logs — 1 passed review first time, 1 after revising, 1 as a best effort, 1 with an error, 0 without a review.", out)
        self.assertIn("Refused, in those logs: 1.", out)
        self.assertIn("under 200 words: met 1 of 2 rounds", out)
        self.assertIn("1 of 2 rules were met in every round.", out)
        self.assertIn("Actions done, from the receipts of the last 7 days: 2.", out)
        self.assertIn("The chain is intact", out)
        self.assertIn("Claude", out)  # the spending record's service line

    def test_status_is_one_line(self):
        now = datetime.datetime.now()
        self.log(LOG_FIRST, when=now)
        self.log(LOG_REVISED, when=now + datetime.timedelta(minutes=1))
        self.log(LOG_FAILED, when=now + datetime.timedelta(minutes=2))
        self.receipts(["send a Telegram message: hi", "light.turn_on on light.kitchen"])
        self.spend(0.01)
        rc, out = self.capture(self.rt.show_status)
        self.assertEqual(rc, 0)
        self.assertEqual(len(out.strip().splitlines()), 1)
        self.assertIn("demo: 3 runs (2 passed, 1 with an error), 2 actions done, 1 refused, $0.01 spent.", out)

    def test_a_broken_receipts_chain_says_so_and_gives_exit_1(self):
        self.receipts(["send a Telegram message: hi", "send a Telegram message: again"], break_chain=True)
        rc, out = self.capture(self.rt.show_report)
        self.assertEqual(rc, 1)
        self.assertIn("The chain is broken", out)
        rc, out = self.capture(self.rt.show_status)
        self.assertEqual(rc, 1)

    def test_nothing_recorded_yet(self):
        for fn in (self.rt.show_report, self.rt.show_status):
            rc, out = self.capture(fn)
            self.assertEqual(rc, 0)
            self.assertIn("No runs, receipts or spending recorded for demo yet.", out)

    def test_logs_and_receipts_older_than_the_week_are_left_out(self):
        old = datetime.datetime.now() - datetime.timedelta(days=8)
        self.log(LOG_FIRST, when=old)
        self.receipts(["send a Telegram message: hi"], when=time.time() - 8 * 86400)
        rc, out = self.capture(self.rt.show_report)
        self.assertEqual(rc, 0)
        self.assertIn("No saved logs in the last 7 days", out)
        self.assertIn("Actions done, from the receipts of the last 7 days: 0.", out)

    def test_a_run_without_a_review_counts_as_plain(self):
        self.log("# demo: run log\n\n- Started: 2026-11-18 09:00:00 (Run)\n")
        rc, out = self.capture(self.rt.show_report)
        self.assertIn("0 passed review first time, 0 after revising, 0 as a best effort, 0 with an error, 1 without a review.", out)
        self.assertIn("No rules were checked in those logs.", out)


if __name__ == "__main__":
    unittest.main()
