"""Scheduled-run notices (#433): notify_on_failure sends one message when a scheduled run stops with an error, and
heartbeat_url is fetched after each scheduled run that finishes. A heartbeat failure is only a note, never an error."""
import asyncio
import io
import os
import pathlib
import sys
import tempfile
import threading
import unittest
from contextlib import redirect_stdout
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import support  # noqa: F401
from second_thought.core import RunError
from second_thought.runtime import Runtime

ENV_KEYS = ("RB_NOTIFY_ON_FAILURE", "RB_HEARTBEAT_URL", "TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID")


class Ping(BaseHTTPRequestHandler):
    hits = []

    def log_message(self, *a):
        pass

    def do_GET(self):
        Ping.hits.append(self.path)
        body = b"OK"
        self.send_response(200)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


class ScheduledNotices(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.srv = ThreadingHTTPServer(("127.0.0.1", 0), Ping)
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()
        cls.ping_url = f"http://127.0.0.1:{cls.srv.server_address[1]}/ping/uuid-1"

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.prog = pathlib.Path(self.tmp.name) / "prog.py"
        self.prog.write_text("# prog\n", encoding="utf-8")
        self.saved_argv = sys.argv
        sys.argv = [str(self.prog)]
        self.saved_env = {k: os.environ.get(k) for k in ENV_KEYS}
        for k in ENV_KEYS:
            os.environ.pop(k, None)
        self.rt = Runtime()
        self.sent = []  # the stand-in Telegram's sendMessage calls

        async def fake_tg(method, params=None, wait=0):
            self.sent.append((method, params))
            return {"message_id": len(self.sent)}
        self.rt._tg = fake_tg
        Ping.hits.clear()

    def tearDown(self):
        sys.argv = self.saved_argv
        for k, v in self.saved_env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        self.tmp.cleanup()

    def go(self, coro):
        out = io.StringIO()
        with redirect_stdout(out):
            asyncio.run(coro)
        return out.getvalue()

    def test_finished_run_fetches_heartbeat_and_sends_nothing(self):
        os.environ["RB_HEARTBEAT_URL"] = self.ping_url
        os.environ["RB_NOTIFY_ON_FAILURE"] = "telegram"
        os.environ["TELEGRAM_BOT_TOKEN"] = "t"
        os.environ["TELEGRAM_CHAT_ID"] = "42"
        self.rt.error = None
        out = self.go(self.rt._scheduled_end("every half hour", 0))
        self.assertEqual(Ping.hits, ["/ping/uuid-1"])
        self.assertEqual(self.sent, [])
        self.assertIn("Heartbeat sent", out)

    def test_failing_run_sends_one_message_with_the_reason_and_still_heartbeats(self):
        os.environ["RB_HEARTBEAT_URL"] = self.ping_url
        os.environ["RB_NOTIFY_ON_FAILURE"] = "telegram"
        os.environ["TELEGRAM_BOT_TOKEN"] = "t"
        os.environ["TELEGRAM_CHAT_ID"] = "42"
        self.rt.error = RunError("the oven door is open")
        out = self.go(self.rt._scheduled_end("Scheduled 03:00", 1))
        self.assertEqual(len(self.sent), 1, "one message, not one per line of the error")
        method, params = self.sent[0]
        self.assertEqual(method, "sendMessage")
        self.assertEqual(params["chat_id"], "42")
        self.assertIn("the oven door is open", params["text"])
        self.assertIn("prog.py", params["text"])
        self.assertEqual(Ping.hits, ["/ping/uuid-1"], "the heartbeat is fetched even when the run failed")
        self.assertIn("Sent a failure notice", out)

    def test_message_goes_without_asking(self):
        os.environ["RB_NOTIFY_ON_FAILURE"] = "telegram"
        os.environ["TELEGRAM_BOT_TOKEN"] = "t"
        os.environ["TELEGRAM_CHAT_ID"] = "42"
        self.rt.error = RunError("boom")

        async def no_asking(*a, **k):
            raise AssertionError("an unattended failure notice must not ask first")
        self.rt._allowed = no_asking
        self.go(self.rt._scheduled_end("x", 1))
        self.assertEqual(len(self.sent), 1)

    def test_heartbeat_failure_is_only_a_note(self):
        os.environ["RB_HEARTBEAT_URL"] = "http://127.0.0.1:9/dead"
        self.rt.error = None
        out = self.go(self.rt._scheduled_end("x", 0))  # must not raise
        self.assertIn("only a note", out)
        self.assertEqual(Ping.hits, [])

    def test_unknown_channel_is_a_note(self):
        os.environ["RB_NOTIFY_ON_FAILURE"] = "sms"
        self.rt.error = RunError("boom")
        out = self.go(self.rt._scheduled_end("x", 1))
        self.assertIn("isn't a channel", out)
        self.assertEqual(self.sent, [])

    def test_nothing_set_means_silence(self):
        self.rt.error = RunError("boom")
        out = self.go(self.rt._scheduled_end("x", 1))
        self.assertEqual(out, "")
        self.assertEqual(self.sent, [])
        self.assertEqual(Ping.hits, [])

    def test_rehearsal_sends_nothing(self):
        os.environ["RB_HEARTBEAT_URL"] = self.ping_url
        os.environ["RB_NOTIFY_ON_FAILURE"] = "telegram"
        os.environ["TELEGRAM_BOT_TOKEN"] = "t"
        os.environ["TELEGRAM_CHAT_ID"] = "42"
        self.rt.rehearsing = True
        self.rt.error = RunError("boom")
        out = self.go(self.rt._scheduled_end("x", 1))
        self.assertEqual(out, "")
        self.assertEqual(self.sent, [])
        self.assertEqual(Ping.hits, [])

    def test_task_result_from_the_schedule_loop(self):
        os.environ["RB_NOTIFY_ON_FAILURE"] = "telegram"
        os.environ["TELEGRAM_BOT_TOKEN"] = "t"
        os.environ["TELEGRAM_CHAT_ID"] = "42"

        async def main():
            async def boom():
                raise RunError("task boom")
            t = asyncio.ensure_future(self.rt.run([boom], "every bit"))
            await asyncio.wait([t])
            self.assertEqual(t.result(), 1)
            await self.rt._scheduled_end("every bit", t)
        self.go(main())
        self.assertEqual(len(self.sent), 1)
        self.assertIn("task boom", self.sent[0][1]["text"])

    def test_run_one_schedule_sends_the_notice(self):
        """--run-schedule N --now on a script that raises: one Telegram message, the heartbeat, exit 1."""
        os.environ["RB_NOTIFY_ON_FAILURE"] = "telegram"
        os.environ["RB_HEARTBEAT_URL"] = self.ping_url
        os.environ["TELEGRAM_BOT_TOKEN"] = "t"
        os.environ["TELEGRAM_CHAT_ID"] = "42"
        sys.argv = [str(self.prog), "--run-schedule", "1", "--now"]

        async def bad():
            raise RunError("no flour left")
        schedules = [("every", 3600, "every hour", bad)]
        out = io.StringIO()
        with redirect_stdout(out):
            code = self.rt.run_one_schedule(schedules, {})
        self.assertEqual(code, 1)
        self.assertEqual(len(self.sent), 1)
        self.assertIn("no flour left", self.sent[0][1]["text"])
        self.assertEqual(Ping.hits, ["/ping/uuid-1"])
        self.assertIn("Run stopped", out.getvalue())

    def test_run_one_schedule_success_only_heartbeats(self):
        os.environ["RB_NOTIFY_ON_FAILURE"] = "telegram"
        os.environ["RB_HEARTBEAT_URL"] = self.ping_url
        os.environ["TELEGRAM_BOT_TOKEN"] = "t"
        os.environ["TELEGRAM_CHAT_ID"] = "42"
        sys.argv = [str(self.prog), "--run-schedule", "1", "--now"]

        async def fine():
            self.rt.result.append("done")
        code = self.rt.run_one_schedule([("every", 3600, "every hour", fine)], {})
        self.assertEqual(code, 0)
        self.assertEqual(self.sent, [])
        self.assertEqual(Ping.hits, ["/ping/uuid-1"])

    def test_run_schedules_loop_sends_the_notice(self):
        """The long-running schedule loop's done callback fires the notice too."""
        os.environ["RB_NOTIFY_ON_FAILURE"] = "telegram"
        os.environ["TELEGRAM_BOT_TOKEN"] = "t"
        os.environ["TELEGRAM_CHAT_ID"] = "42"

        async def fn():
            pass

        async def fake_run(scripts, label=None):
            self.rt.error = RunError("loop boom")
            return 1
        self.rt.run = fake_run

        async def main():
            loop = asyncio.ensure_future(self.rt.run_schedules([("every", 0.05, "every bit", fn)]))
            for _ in range(140):  # the loop wakes every 5 s; the first 'every' fires on the first wake after its interval
                await asyncio.sleep(0.05)
                if self.sent:
                    break
            for t in list(getattr(self.rt, "_background_tasks", set())):
                await asyncio.wait([t], timeout=5)
            loop.cancel()
            try:
                await loop
            except asyncio.CancelledError:
                pass
        self.go(main())
        self.assertEqual(len(self.sent), 1)
        self.assertIn("loop boom", self.sent[0][1]["text"])


if __name__ == "__main__":
    unittest.main()
