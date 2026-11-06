"""A Gemini call that never answers gives up after RB_CALL_TIMEOUT, like every other service (#329).

google-genai waits forever by default, so one dropped connection used to stall the whole program with nothing on
screen and no network traffic.
"""
import asyncio
import os
import sys
import unittest
from unittest import mock

import support
from second_thought import providers
from second_thought.core import Retryable
from second_thought.runtime import Runtime

sys.path.insert(0, str(support.ROOT / "tests" / "fakeapi"))


class Hangs:
    async def generate_content(self, **kw):
        await asyncio.sleep(3600)


class GeminiTimeout(unittest.TestCase):
    def setUp(self):
        os.environ["GEMINI_API_KEY"] = "test"
        self.addCleanup(os.environ.pop, "GEMINI_API_KEY", None)

    def test_the_client_is_given_the_call_timeout(self):
        rt = Runtime()
        asyncio.run(rt._call_gemini("gemini-test", "Hello", None, [], False))
        self.assertEqual(rt.gemini.http_options.timeout, int(providers.CALL_TIMEOUT * 1000))

    def test_a_call_that_never_answers_gives_up(self):
        rt = Runtime()
        asyncio.run(rt._call_gemini("gemini-test", "Hello", None, [], False))  # makes the client
        rt.gemini.aio.models = Hangs()
        with mock.patch.object(providers, "CALL_TIMEOUT", 0.05), self.assertRaises(Retryable) as e:
            asyncio.run(rt._call_gemini("gemini-test", "Hello", None, [], False))
        self.assertIn("Gemini", str(e.exception))


if __name__ == "__main__":
    unittest.main()
