"""What a program can do: the list, how it's shown, and the question before its first run."""
import builtins
import io
import json
import os
import sys
import unittest
from contextlib import redirect_stdout
from unittest import mock

import support
from second_thought.core import CAPABILITIES
from second_thought.runtime import Runtime

sys.path.insert(0, str(support.ROOT / "tools"))
import sync  # noqa: E402


class List(unittest.TestCase):
    def test_well_formed(self):
        ids = [c[0] for c in CAPABILITIES]
        self.assertEqual(len(ids), len(set(ids)))
        for cid, says, acts in CAPABILITIES:
            self.assertRegex(cid, r"^[a-z_]+$")
            self.assertTrue(says and says[0].islower() and not says.endswith("."), says)
            self.assertIsInstance(acts, bool)
        acts = [c[2] for c in CAPABILITIES]
        self.assertEqual(acts, sorted(acts, reverse=True), "the ones that act come first, so they're listed first")

    def test_page_gets_the_same_list(self):
        self.assertEqual(json.loads(sync.capabilities_json()), [list(c) for c in CAPABILITIES])


class Showing(unittest.TestCase):
    def test_lines_in_list_order_then_services(self):
        lines, tail = Runtime.can_lines({"services": ["Claude", "Gemini", "Groq"], "can": ["calendar", "email_send"]})
        self.assertEqual(lines, ["send email", "read your calendars"])
        self.assertEqual(tail, ["It sends what it reads and writes to Claude, Gemini and Groq."])

    def test_unknown_ids_are_shown_and_count_as_acting(self):
        lines, _ = Runtime.can_lines({"can": ["teleport"]})
        self.assertIn("“teleport”", lines[0])
        self.assertTrue(Runtime.can_acts({"can": ["teleport"]}))

    def test_acts(self):
        self.assertTrue(Runtime.can_acts({"can": ["memory", "ha_act"]}))
        self.assertFalse(Runtime.can_acts({"can": ["memory", "ha_read"]}))
        self.assertFalse(Runtime.can_acts(None))  # programs exported before this ask nothing


class Asking(unittest.TestCase):
    CAN = {"services": ["Claude"], "can": ["email_send"]}

    def setUp(self):
        self.prog = support.TMP / "asked.py"
        self.prog.write_text("print('hi')\n", encoding="utf-8")
        self.approved = support.TMP / ".asked.approved"
        if self.approved.exists():
            self.approved.unlink()
        self.argv = mock.patch.object(sys, "argv", [str(self.prog)])
        self.argv.start()
        os.environ.pop("RB_APPROVE", None)

    def tearDown(self):
        self.argv.stop()
        os.environ.pop("RB_APPROVE", None)

    def ask(self, answers=(), **kw):
        replies = iter(answers)

        def fake_input(prompt):
            self.assertEqual(prompt, "Approve? [y/n] > ")
            try:
                return next(replies)
            except StopIteration:
                raise EOFError from None
        out = io.StringIO()
        with mock.patch.object(builtins, "input", fake_input), redirect_stdout(out):
            ok = Runtime().approve_program(self.CAN, **kw)
        return ok, out.getvalue()

    def test_yes_is_remembered_until_the_file_changes(self):
        ok, out = self.ask(["maybe", "y"])
        self.assertTrue(ok)
        self.assertIn("  - send email", out)
        self.assertIn("Type y or n.", out)
        self.assertEqual(json.loads(self.approved.read_text())["allowed"], ["email_send"])
        self.assertEqual(self.ask([]), (True, ""))  # no question the second time
        self.prog.write_text("print('changed')\n", encoding="utf-8")
        ok, out = self.ask([])
        self.assertFalse(ok)
        self.assertIn("Nobody answered", out)

    def test_no(self):
        ok, out = self.ask(["n"])
        self.assertFalse(ok)
        self.assertIn("Not allowed", out)
        self.assertFalse(self.approved.exists())

    def test_unattended_never_asks(self):
        ok, out = self.ask([], unattended=True)
        self.assertFalse(ok)
        self.assertIn("nobody is here to ask", out)
        self.assertIn("approve = no", out)

    def test_approve_no_skips_it(self):
        os.environ["RB_APPROVE"] = "no"
        self.assertEqual(self.ask([], unattended=True), (True, ""))

    def test_a_program_that_only_reads_isnt_asked(self):
        self.CAN = {"services": ["Claude"], "can": ["web", "email_read"]}
        self.assertEqual(self.ask([]), (True, ""))


if __name__ == "__main__":
    unittest.main()
