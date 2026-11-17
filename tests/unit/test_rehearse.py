"""--rehearse (#430): a rehearsed run acts on nothing, and a test fails if an action path doesn't honour it."""
import ast
import io
import unittest
from contextlib import redirect_stdout

import support
from second_thought import settings
from second_thought.runtime import Runtime

PACKAGE = support.ROOT / "python" / "second_thought"

# The only functions that may read `testing` directly: the dry-run helpers themselves, the test runner's input
# plumbing (a rehearsal asks live; it has no recorded answers), and the agent's choice of wording. Every action
# path goes through dry_run()/_skip_action(), so one that checks only `testing` fails the test below.
TEST_ONLY = {"dry_run", "_skip_action", "_from_test", "_choose_file_live", "choose_picture",
             "_ask_me_live", "_approve_live", "_choose_live", "pause", "_agent_loop"}


class ActionPaths(unittest.TestCase):
    def test_every_testing_check_is_rehearsal_aware(self):
        for path in sorted(PACKAGE.glob("*.py")):
            text = path.read_text(encoding="utf-8")
            for node in ast.walk(ast.parse(text)):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    src = ast.get_source_segment(text, node) or ""
                    if 'getattr(self, "testing"' in src:
                        self.assertIn(node.name, TEST_ONLY,
                                      f"{path.name}: {node.name}() reads `testing` directly; use dry_run()/_skip_action() so --rehearse is honoured too")

    def test_every_skip_log_goes_through_the_helper(self):
        # "Not done, because this is a test" is logged only by _skip_action, which logs the rehearsal line too.
        for path in sorted(PACKAGE.glob("*.py")):
            text = path.read_text(encoding="utf-8")
            self.assertLessEqual(text.count('Not done, because this is a test: {what}'), 1,
                                 f"{path.name} logs a test skip somewhere besides _skip_action")


class Rehearsal(unittest.TestCase):
    def test_dry_run_and_skip_action(self):
        r = Runtime()
        self.assertFalse(r.dry_run())
        r.rehearsing = True
        self.assertTrue(r.dry_run())
        buf = io.StringIO()
        with redirect_stdout(buf):
            self.assertTrue(r._skip_action("send a Telegram message"))
        self.assertIn("Rehearsal", buf.getvalue())
        self.assertIn("Not done, because this is a rehearsal: send a Telegram message", buf.getvalue())
        t = Runtime()
        t.testing = True
        self.assertTrue(t.dry_run())
        buf = io.StringIO()
        with redirect_stdout(buf):
            self.assertTrue(t._skip_action("send a Telegram message"))
        self.assertIn("Not done, because this is a test: send a Telegram message", buf.getvalue())
        live = Runtime()
        self.assertFalse(live._skip_action("send a Telegram message"))

    def test_rehearse_is_a_setting(self):
        # rehearse = yes in second-thought.ini lands in RB_REHEARSE, like update_check.
        self.assertEqual(settings.SETTING_NAMES.get("rehearse"), "RB_REHEARSE")
        self.assertIn("rehearse", settings.ONE_WORD_SETTINGS)


if __name__ == "__main__":
    unittest.main()
