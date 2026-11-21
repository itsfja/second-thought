"""Plex and Tautulli through their APIs (#402), against tests/fake_plex.py: the server, the libraries, the
sessions, the newest items and Tautulli's history go without asking, a library scan and stopping a stream
always ask and never run unattended, and nothing else is ever sent."""
import asyncio
import os
import sys
import unittest
from unittest import mock

import support
from second_thought.core import RunError, plex_call, tautulli_call
from second_thought.runtime import Runtime

sys.path.insert(0, str(support.ROOT / "tests"))
import fake_plex  # noqa: E402


class AtKeyboard:
    def isatty(self):
        return True


class Calls(unittest.TestCase):
    def test_reads_ask_and_never(self):
        for path in ("/", "/library/sections", "/library/sections/1/all", "/library/recentlyAdded", "/status/sessions"):
            self.assertEqual(plex_call("GET", path), "free", path)
        self.assertEqual(plex_call("GET", "/library/sections/2/refresh"), "asks")
        self.assertEqual(tautulli_call("GET", "cmd=get_history&after=2026-01-01&length=100"), "free")
        self.assertEqual(tautulli_call("GET", "cmd=terminate_session&session_key=abc123"), "asks")
        for method, path in [("GET", "/library/sections/1/refresh?x=1"), ("GET", "/library/sections/x/refresh"),
                            ("POST", "/library/sections/1/refresh"), ("GET", "/library/sections/1/partial"),
                            ("DELETE", "/library/sections/1"), ("GET", "/media/metadata"), ("POST", "/"),
                            ("GET", ""), ("GET", "/library/sections/1/all/x")]:
            self.assertIsNone(plex_call(method, path), f"{method} {path}")
        for query in ["cmd=terminate_session", "cmd=get_history&cmd=terminate_session", "cmd=get_metadata",
                      "cmd=update_metadata&id=1", "cmd=delete_history", "cmd=", ""]:
            self.assertIsNone(tautulli_call("GET", query), query)

    def test_a_smuggled_terminate_is_refused(self):
        self.assertIsNone(tautulli_call("GET", "cmd=get_history&cmd=terminate_session&session_key=abc123"))


class Stack(unittest.TestCase):
    def runtime(self, here=True, env=None, answers=()):
        self.fake = fake_plex.FakePlex()
        host = self.fake.start()
        self.addCleanup(self.fake.stop)
        base = {"PLEX_URL": host, "PLEX_TOKEN": "tok", "TAUTULLI_URL": host, "TAUTULLI_API_KEY": "key"}
        patches = [mock.patch.dict(os.environ, dict(base, **(env or {}))),
                   mock.patch.object(sys, "stdin", AtKeyboard() if here else sys.stdin)]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)
        if "GITHUB_ACTIONS" not in (env or {}):
            os.environ.pop("GITHUB_ACTIONS", None)
        r = Runtime()
        r.reset()
        self.logged, self.asked = [], []
        r.log = lambda *a, **k: self.logged.append(a)

        async def approve(what):
            self.asked.append(what)
            return answers[len(self.asked) - 1] if len(self.asked) <= len(answers) else True
        r._approve_live = approve
        return r

    def test_the_reads_read(self):
        r = self.runtime()
        s = asyncio.run(r.plex_server())
        self.assertEqual(s, {"name": "livingroom", "version": "1.41.3.9662", "up": True})
        libs = asyncio.run(r.plex_libraries())
        self.assertEqual(libs, [{"name": "Films", "type": "movie", "count": 312},
                                {"name": "TV", "type": "show", "count": 1204},
                                {"name": "Music", "type": "artist", "count": 89}])
        sess = asyncio.run(r.plex_sessions())
        self.assertEqual(sess, [{"id": "abc123", "user": "alice", "title": "The Matrix", "player": "livingroom-tv",
                                  "state": "playing", "transcode": False},
                                 {"id": "def456", "user": "bob", "title": "Doctor Who - s01e01", "player": "bob-phone",
                                  "state": "paused", "transcode": True}])
        self.assertEqual((self.fake.refused, self.fake.changed, self.asked), ([], [], []))

    def test_recent_and_history_filter_by_days(self):
        r = self.runtime()
        recent = asyncio.run(r.plex_recent(7))
        self.assertEqual([x["title"] for x in recent], ["Arrival", "Doctor Who - s01e02"])  # this week only
        history = asyncio.run(r.tautulli_history(7))
        self.assertEqual([(x["user"], x["title"]) for x in history],
                         [("alice", "The Matrix"), ("bob", "Doctor Who - s01e01"),
                          ("alice", "Blade Runner 2049")])
        self.assertTrue(all(x["transcode"] is (x["title"] == "Doctor Who - s01e01") for x in history))
        watch = asyncio.run(r.tautulli_watchtime(7))
        self.assertEqual(watch, [{"user": "alice", "hours": 4.67}, {"user": "bob", "hours": 0.75}])
        self.assertEqual((self.fake.refused, self.fake.changed, self.asked), ([], [], []))

    def test_a_scan_and_a_stop_ask_every_time(self):
        r = self.runtime(answers=[True, False, True])
        self.assertTrue(asyncio.run(r.plex_scan("films")))  # the name matches, whatever its case
        self.assertFalse(asyncio.run(r.plex_stop("abc123")))
        self.assertTrue(asyncio.run(r.plex_stop("def456")))
        self.assertEqual(self.fake.changed, ["scan 1", "terminate def456"])
        self.assertIn("scan the Films library on Plex", self.asked[0])
        self.assertIn("stop the abc123 stream on Plex", self.asked[1])
        self.assertEqual(len(self.asked), 3)

    def test_nobody_there_means_it_never_runs(self):
        for label, kw in (("no keyboard", {"here": False}), ("GitHub Actions", {"env": {"GITHUB_ACTIONS": "true"}})):
            with self.subTest(label):
                r = self.runtime(**kw)
                self.assertFalse(asyncio.run(r.plex_scan("Films")))
                self.assertFalse(asyncio.run(r.plex_stop("abc123")))
                self.assertEqual((self.asked, self.fake.changed), ([], []))

    def test_a_test_run_and_bad_requests_do_nothing(self):
        r = self.runtime()
        r.testing = True
        self.assertFalse(asyncio.run(r.plex_scan("Films")))
        self.assertFalse(asyncio.run(r.plex_stop("abc123")))
        r.testing = False
        for args in (("Nope",), ("",)):
            with self.assertRaises(RunError, msg=str(args)):
                asyncio.run(r.plex_scan(*args))
        with self.assertRaises(RunError):
            asyncio.run(r.plex_stop(""))
        self.assertEqual((self.asked, self.fake.changed), ([], []))

    def test_a_change_without_a_yes_never_leaves(self):
        r = self.runtime()
        with self.assertRaises(RunError):
            asyncio.run(r._plex("GET", "/library/sections/1/refresh"))
        with self.assertRaises(RunError):
            asyncio.run(r._plex("GET", "/library/sections/1/partial", approved=True))
        with self.assertRaises(RunError):
            asyncio.run(r._tautulli("terminate_session", {"session_key": "abc123"}))
        with self.assertRaises(RunError):
            asyncio.run(r._tautulli("delete_history", approved=True))
        self.assertEqual(self.fake.calls, [])

    def test_a_wrong_token_or_key_is_refused(self):
        r = self.runtime(env={"PLEX_TOKEN": "nope"})
        with self.assertRaises(RunError) as e:
            asyncio.run(r.plex_server())
        self.assertIn("refused its token", str(e.exception))
        r = self.runtime(env={"TAUTULLI_API_KEY": "nope"})
        with self.assertRaises(RunError) as e:
            asyncio.run(r.tautulli_history(7))
        self.assertIn("refused its key", str(e.exception))

    def test_without_settings_it_says_what_it_needs(self):
        with mock.patch.dict(os.environ, {"PLEX_URL": "", "PLEX_TOKEN": ""}):
            r = Runtime()
            r.reset()
            with self.assertRaises(RunError) as e:
                asyncio.run(r.plex_server())
            self.assertIn("PLEX_URL", str(e.exception))
        with mock.patch.dict(os.environ, {"TAUTULLI_URL": "", "TAUTULLI_API_KEY": ""}):
            r = Runtime()
            r.reset()
            with self.assertRaises(RunError) as e:
                asyncio.run(r.tautulli_history(7))
            self.assertIn("TAUTULLI_URL", str(e.exception))

    def test_doctor_says_the_version_and_the_plays(self):
        r = self.runtime()
        checks = {c[0]: c[1] for c in asyncio.run(r._doctor_connections(["plex_read"], []))}
        self.assertEqual(asyncio.run(checks["Plex"]()), "Plex 1.41.3.9662, 3 libraries")
        self.assertTrue(asyncio.run(checks["Tautulli"]()).startswith("Tautulli, "))


if __name__ == "__main__":
    unittest.main()
