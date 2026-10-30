"""What a real run on GitHub Actions showed (#226): keys made for a whole Console organisation, a failure's reason on
the run's page, and model replies' Markdown in Telegram and Slack."""
import io
import os
import sys
import unittest
from contextlib import redirect_stdout
from unittest import mock

import support  # noqa: F401
from second_thought import providers
from second_thought.connectors import markdown_to_slack, markdown_to_telegram
from second_thought.core import RunError
from second_thought.runtime import Runtime

WORKSPACE_ERROR = ("BadRequestError: Error code: 400 - {'type': 'error', 'error': {'type': 'invalid_request_error', 'message': "
                   "'This API key is not scoped to a workspace, so this request must include the anthropic-workspace-id header'}}")


class Hints(unittest.TestCase):
    def test_refusals_get_a_plain_line(self):
        self.assertIn("ANTHROPIC_WORKSPACE_ID", Runtime.error_hint(WORKSPACE_ERROR))
        self.assertIn("Workspaces page", Runtime.error_hint(WORKSPACE_ERROR))
        self.assertIn("out of credit", Runtime.error_hint("Your credit balance is too low to access the Anthropic API."))
        self.assertIn("refused the key", Runtime.error_hint("AuthenticationError: invalid x-api-key"))
        self.assertEqual(Runtime.error_hint("Telegram: chat not found."), "")


class Workspace(unittest.TestCase):
    def test_the_workspace_goes_with_every_call(self):
        seen = {}

        class Fake:
            def __init__(self, **kw):
                seen.update(kw)
        fake_sdk = mock.MagicMock(AsyncAnthropic=Fake)
        with mock.patch.dict(sys.modules, {"anthropic": fake_sdk}):
            with mock.patch.dict(os.environ, {"ANTHROPIC_WORKSPACE_ID": " wrkspc_123 "}):
                providers._anthropic_client(timeout=5)
            self.assertEqual(seen["default_headers"], {"anthropic-workspace-id": "wrkspc_123"})
            seen.clear()
            with mock.patch.dict(os.environ, {"ANTHROPIC_WORKSPACE_ID": ""}):
                providers._anthropic_client(timeout=5)
            self.assertNotIn("default_headers", seen, "an empty secret (GitHub passes one when it isn't set) is no workspace")


class Stopping(unittest.TestCase):
    def test_on_actions_the_reason_is_an_annotation(self):
        rt = Runtime()
        out = io.StringIO()
        with mock.patch.dict(os.environ, {"GITHUB_ACTIONS": "true"}), redirect_stdout(out):
            rt.report_stop(WORKSPACE_ERROR)
        lines = out.getvalue().splitlines()
        notes = [line for line in lines if line.startswith("::error::")]
        self.assertEqual(len(notes), 1)
        self.assertIn("Run stopped: BadRequestError", notes[0])
        self.assertIn("%0AYour Claude key belongs to a whole Console organisation", notes[0], "the hint, on its own line")
        self.assertNotIn("\n", notes[0])

    def test_elsewhere_there_is_no_annotation(self):
        out = io.StringIO()
        with mock.patch.dict(os.environ, {"GITHUB_ACTIONS": ""}), redirect_stdout(out):
            Runtime().report_stop("Telegram: chat not found.")
        self.assertIn("✖ Run stopped: Telegram: chat not found.", out.getvalue())
        self.assertNotIn("::error::", out.getvalue())


class Markdown(unittest.TestCase):
    REPLY = "🧺 **Best window:** Saturday, 12:00-14:00. Use *care* with a<b & 5*3*2.\n# Heading\n[Met Office](https://example.com/a?b=1) and `code` snake_case"

    def test_telegram(self):
        self.assertEqual(markdown_to_telegram(self.REPLY),
                         "🧺 <b>Best window:</b> Saturday, 12:00-14:00. Use <i>care</i> with a&lt;b &amp; 5*3*2.\n<b>Heading</b>\n"
                         '<a href="https://example.com/a?b=1">Met Office</a> and <code>code</code> snake_case')

    def test_slack(self):
        self.assertEqual(markdown_to_slack(self.REPLY),
                         "🧺 *Best window:* Saturday, 12:00-14:00. Use _care_ with a&lt;b &amp; 5*3*2.\n*Heading*\n"
                         "<https://example.com/a?b=1|Met Office> and `code` snake_case")

    def test_plain_text_is_left_alone(self):
        for text in ("Nothing special here.", "2 * 3 = 6", "file_name_here.txt"):
            self.assertEqual(markdown_to_telegram(text), text)
            self.assertEqual(markdown_to_slack(text), text)


if __name__ == "__main__":
    unittest.main()
