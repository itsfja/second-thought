"""Receipts (#431): every action that goes ahead writes one chained, private line, and --receipts checks the chain."""
import asyncio
import hashlib
import io
import json
import os
import pathlib
import stat
import sys
import tempfile
import unittest
from contextlib import redirect_stdout

import support
from second_thought.runtime import Runtime


class Receipts(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.prog = pathlib.Path(self.tmp.name) / "prog.py"
        self.prog.write_text("# prog\n", encoding="utf-8")
        self.saved_argv = sys.argv
        sys.argv = [str(self.prog)]
        self.rt = Runtime()
        self.rt._last_how = ""

    def tearDown(self):
        sys.argv = self.saved_argv
        self.tmp.cleanup()

    def go(self, coro):
        return asyncio.run(coro)

    def receipts_file(self):
        return pathlib.Path(self.tmp.name) / ".prog.receipts.jsonl"

    def test_each_kind_of_allow_writes_a_receipt(self):
        rt = self.rt
        self.go(rt._allowed(["messages"], "send a Telegram message: hi"))  # no asking: ask_first doesn't cover it
        rt.ask_first.add("ha")

        async def yes(text):
            return True
        rt.approve = yes
        self.go(rt._allowed(["ha"], "light.turn_off on light.kitchen"))  # yes at the keyboard
        rt.ask_first.add("messages")
        rt.nobody_here = lambda: True
        os.environ["RB_APPROVE_BY"] = "telegram"

        async def tg(what):
            rt._last_how = "yes 4821 on Telegram, by Alex"
            return True
        rt._approve_telegram = tg
        self.go(rt._allowed(["messages"], "send a Telegram message: bins"))  # yes on Telegram
        os.environ.pop("RB_APPROVE_BY", None)
        raw = [l for l in self.receipts_file().read_bytes().split(b"\n") if l.strip()]
        lines = [json.loads(l) for l in raw]
        self.assertEqual([l["how"] for l in lines], ["no asking", "yes at the keyboard", "yes 4821 on Telegram, by Alex"])
        self.assertEqual([l["what"] for l in lines],
                         ["send a Telegram message: hi", "light.turn_off on light.kitchen", "send a Telegram message: bins"])
        prev = hashlib.sha256(b"").hexdigest()  # each line carries the fingerprint of the one before
        for l, r in zip(raw, lines):
            self.assertEqual(r["prev"], prev)
            prev = hashlib.sha256(l).hexdigest()
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = rt.show_receipts()
        out = buf.getvalue()
        self.assertEqual(code, 0)
        self.assertIn("send a Telegram message: hi", out)
        self.assertIn("allowed: yes 4821 on Telegram, by Alex", out)
        self.assertIn("intact", out)

    def test_receipts_detects_an_edited_or_removed_line(self):
        rt = self.rt
        self.go(rt._allowed(["messages"], "send a Telegram message: one"))
        self.go(rt._allowed(["messages"], "send a Telegram message: two"))
        path = self.receipts_file()
        raw = path.read_bytes()
        lines = [l for l in raw.split(b"\n") if l.strip()]
        rec = json.loads(lines[0])  # an edited line: the next line's prev no longer matches
        rec["what"] = "edited"
        path.write_bytes(json.dumps(rec, ensure_ascii=False, sort_keys=True).encode() + b"\n" + lines[1] + b"\n")
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = rt.show_receipts()
        self.assertEqual(code, 1)
        self.assertIn("broken", buf.getvalue())
        path.write_bytes(lines[1] + b"\n")  # the first line removed: the second's prev no longer matches the genesis
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = rt.show_receipts()
        self.assertEqual(code, 1)
        self.assertIn("broken", buf.getvalue())
        path.write_bytes(raw)  # intact again
        with redirect_stdout(io.StringIO()):
            self.assertEqual(rt.show_receipts(), 0)

    def test_receipts_file_is_private(self):
        self.go(self.rt._allowed(["messages"], "send a Telegram message: hi"))
        if os.name == "posix":
            self.assertEqual(stat.S_IMODE(os.stat(self.receipts_file()).st_mode), 0o600)

    def test_no_receipts_file(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = self.rt.show_receipts()
        self.assertEqual(code, 0)
        self.assertIn("No receipts yet", buf.getvalue())


if __name__ == "__main__":
    unittest.main()
