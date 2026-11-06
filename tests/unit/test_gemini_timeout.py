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
        with mock.patch.object(providers, "CALL_TIMEOUT", 0.05), mock.patch.object(Runtime, "GEMINI_WAITS", (0, 0)), \
                mock.patch.object(rt, "log"), self.assertRaises(Retryable) as e:
            asyncio.run(rt._call_gemini("gemini-test", "Hello", None, [], False))
        self.assertIn("Gemini", str(e.exception))

    def busy(self, failures, code=503):
        """Gemini answers `code` this many times, then replies."""
        rt = Runtime()
        asyncio.run(rt._call_gemini("gemini-test", "Hello", None, [], False))
        real, calls = rt.gemini.aio.models, []

        class Busy:
            async def generate_content(self, **kw):
                calls.append(1)
                if len(calls) <= failures:
                    raise ServerError(code)
                return await real.generate_content(**kw)
        rt.gemini.aio.models = Busy()
        with mock.patch.object(Runtime, "GEMINI_WAITS", (0, 0)), mock.patch.object(rt, "log") as log:
            try:
                reply = asyncio.run(rt._call_gemini("gemini-test", "Hello", None, [], False))
            except Exception as e:  # noqa: BLE001
                reply = e
        return reply, len(calls), log.call_count

    def test_a_busy_answer_is_tried_twice_more(self):
        # The 503 "high demand" that stopped runs at once (#329)
        reply, calls, logged = self.busy(2)
        self.assertNotIsInstance(reply, Exception)
        self.assertEqual((calls, logged), (3, 2))
        reply, calls, _ = self.busy(3)
        self.assertIsInstance(reply, Retryable)
        self.assertIn("503", str(reply))
        self.assertEqual(calls, 3)

    def test_a_refusal_is_not_tried_again(self):
        reply, calls, _ = self.busy(1, code=401)
        self.assertIsInstance(reply, ServerError)
        self.assertEqual(calls, 1)


class ServerError(Exception):
    """Like google.genai.errors.ServerError: the HTTP status is in .code."""
    def __init__(self, code):
        super().__init__(f"{code} UNAVAILABLE")
        self.code = code


if __name__ == "__main__":
    unittest.main()
