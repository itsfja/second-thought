"""A Claude reply with no text says why (#251), a refusal isn't retried, and a reply shape Claude won't take is
remembered on its own, so the other shapes are still held while it writes (#250)."""
import asyncio
import io
import types
import unittest
from contextlib import redirect_stdout

import support  # noqa: F401
from second_thought.core import SCHEMAS, Retryable, RunError
from second_thought.runtime import Runtime


def reply(text="", stop="end_turn"):
    return types.SimpleNamespace(content=[types.SimpleNamespace(type="text", text=text)] if text else [], stop_reason=stop,
                                 usage=types.SimpleNamespace(input_tokens=10, output_tokens=2))


class FakeMessages:
    def __init__(self, answers, refuse_shapes=()):
        self.answers, self.refuse, self.sent = list(answers), list(refuse_shapes), []

    async def create(self, **args):
        self.sent.append(args)
        shape = args.get("output_config", {}).get("format", {}).get("schema")
        if shape is not None and shape in self.refuse:
            e = Exception("output_config.format.schema: objects must set additionalProperties to false")
            e.status_code = 400
            raise e
        return self.answers.pop(0)


def runtime(messages):
    rt = Runtime()
    rt.client = types.SimpleNamespace(messages=messages)
    rt._streaming = lambda: False
    return rt


def call(rt, schema=None):
    with redirect_stdout(io.StringIO()):
        return asyncio.run(rt._call_claude("claude-test", "hello", None, None, False, schema))


class EmptyReplies(unittest.TestCase):
    def test_a_refusal_says_so_and_is_not_retried(self):
        with self.assertRaises(RunError) as e:
            call(runtime(FakeMessages([reply("", "refusal")])))
        self.assertNotIsInstance(e.exception, Retryable)
        self.assertIn("declined to answer", str(e.exception))

    def test_nothing_else_says_why_and_can_be_retried(self):
        with self.assertRaises(Retryable) as e:
            call(runtime(FakeMessages([reply("", "max_tokens")])))
        self.assertIn("“max_tokens”", str(e.exception))

    def test_text_is_fine(self):
        self.assertEqual(call(runtime(FakeMessages([reply("hi")]))), "hi")


class RefusedShapes(unittest.TestCase):
    def test_one_refused_shape_leaves_the_others_held(self):
        m = FakeMessages([reply('{"tool": "x"}'), reply('{"answer": true}')], refuse_shapes=[SCHEMAS["agent"]])
        rt = runtime(m)
        call(rt, SCHEMAS["agent"])
        call(rt, SCHEMAS["yesno"])
        self.assertNotIn("output_config", m.sent[1], "the refused shape is asked again without it")
        self.assertEqual(m.sent[2]["output_config"]["format"]["schema"], SCHEMAS["yesno"], "another shape is still sent")
        self.assertIn("additionalProperties", rt.no_schema_why)


class StoppedLine(unittest.TestCase):
    def test_a_stopped_run_says_what_it_used(self):
        rt = Runtime()
        rt.calls, rt.usage = 2, {"Claude": [1200, 30]}
        out = io.StringIO()
        with redirect_stdout(out):
            rt.report_stop("Something went wrong.")
        self.assertIn("Stopped · 2 model calls · Claude: 1,200 tokens in, 30 out", out.getvalue())


if __name__ == "__main__":
    unittest.main()
