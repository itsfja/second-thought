"""SABnzbd through its API (#397), against tests/fake_sabnzbd.py: reads go without asking, pause and resume
always ask and never run unattended, and nothing else is ever sent."""
import asyncio
import importlib.util
import os
import sys
import unittest
from unittest import mock

import support
from second_thought.core import SAFETY, RunError, sabnzbd_call
from second_thought.runtime import Runtime

sys.path.insert(0, str(support.ROOT / "tests"))
import fake_sabnzbd  # noqa: E402


class AtKeyboard:
    def isatty(self):
        return True


class Calls(unittest.TestCase):
    def test_reads_pause_and_never(self):
        for mode in ("queue", "history", "diskspace"):
            self.assertEqual(sabnzbd_call("GET", mode), "free", mode)
        for mode in ("pause", "resume"):
            self.assertEqual(sabnzbd_call("GET", mode), "asks")
        for method, mode in [("GET", "config"), ("GET", "addurl"), ("GET", "addfile"), ("GET", "delete"), ("GET", "retry"),
                              ("GET", "speedlimit"), ("GET", "shutdown"), ("GET", "restart"), ("GET", "pauseinfo"),
                              ("GET", "queue/delete"), ("GET", "history/clear"), ("GET", ""), ("GET", "QUEUE"),
                              ("POST", "queue"), ("POST", "pause"), ("GET", "../queue"), ("GET", "queue/x")]:
            self.assertIsNone(sabnzbd_call(method, mode), f"{method} {mode}")
        self.assertEqual({m for m, _ in SAFETY["sabnzbd_free"]}, {"GET"})


class Queue(unittest.TestCase):
    def runtime(self, here=True, env=None, answers=()):
        self.fake = fake_sabnzbd.FakeSabnzbd()
        host = self.fake.start()
        self.addCleanup(self.fake.stop)
        patches = [mock.patch.dict(os.environ, dict({"SABNZBD_URL": host, "SABNZBD_API_KEY": "key"}, **(env or {}))),
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

    def test_queue_history_and_diskspace(self):
        r = self.runtime()
        q = asyncio.run(r.sabnzbd_queue())
        self.assertEqual([s["name"] for s in q], ["Ubuntu 24.04.1 Desktop amd64", "Debian 13.1.0 netinst amd64"])
        self.assertEqual(q[0], {"name": "Ubuntu 24.04.1 Desktop amd64", "size_mb": 4812.7, "left_mb": 1843.2,
                               "percent": 61.7, "eta": "0:03:20", "status": "Downloading"})
        self.assertEqual((q[1]["status"], q[1]["percent"]), ("Queued", 0))
        h = asyncio.run(r.sabnzbd_history(24))
        self.assertEqual([(s["name"], s["status"]) for s in h],
                         [("Old Show S01E02 1080p", "Failed"), ("Big Buck Bunny 2008 4K Remux", "Completed")], "oldest first")
        self.assertEqual((h[0]["size_mb"], h[0]["why"]), (700, "Unusable server article (age?)"))
        self.assertEqual(h[1]["why"], "")
        self.assertTrue(h[0]["when"] and h[1]["when"])
        self.assertEqual(asyncio.run(r.sabnzbd_history(1)), [], "both finished more than an hour ago")
        d = asyncio.run(r.sabnzbd_diskspace())
        self.assertEqual(d, [{"folder": "/mnt/user/downloads", "free_gb": 1234.56}, {"folder": "/mnt/user/complete", "free_gb": 1234.56}])
        self.assertEqual((self.asked, self.fake.refused), ([], []))
        self.assertEqual({c.split()[0] for c in self.fake.calls}, {"GET"})

    def test_pause_asks_every_time(self):
        r = self.runtime(answers=[True, False])
        self.assertTrue(asyncio.run(r.sabnzbd_pause("pause")))
        self.assertFalse(asyncio.run(r.sabnzbd_pause("resume")))
        self.assertEqual(self.fake.powered, ["pause"])
        self.assertIn("pause SABnzbd's queue", self.asked[0])
        self.assertEqual(len(self.asked), 2)

    def test_nobody_there_means_it_never_runs(self):
        for label, kw in (("no keyboard", {"here": False}), ("GitHub Actions", {"env": {"GITHUB_ACTIONS": "true"}})):
            with self.subTest(label):
                r = self.runtime(**kw)
                self.assertFalse(asyncio.run(r.sabnzbd_pause("pause")))
                self.assertEqual((self.asked, self.fake.powered), ([], []))

    def test_a_test_run_and_bad_requests_do_nothing(self):
        r = self.runtime()
        r.testing = True
        self.assertFalse(asyncio.run(r.sabnzbd_pause("pause")))
        r.testing = False
        for action in ("kill", "config", ""):
            with self.assertRaises(RunError, msg=action):
                asyncio.run(r.sabnzbd_pause(action))
        self.assertEqual((self.asked, self.fake.powered, self.fake.refused), ([], [], []))

    def test_a_pause_without_a_yes_never_leaves(self):
        r = self.runtime()
        with self.assertRaises(RunError):
            asyncio.run(r._sabnzbd("pause"))
        with self.assertRaises(RunError):
            asyncio.run(r._sabnzbd("config", approved=True))
        self.assertEqual(self.fake.calls, [])

    def test_without_settings_it_says_what_it_needs(self):
        with mock.patch.dict(os.environ, {"SABNZBD_URL": "", "SABNZBD_API_KEY": ""}):
            r = Runtime()
            r.reset()
            with self.assertRaises(RunError) as e:
                asyncio.run(r.sabnzbd_queue())
        self.assertIn("SABNZBD_URL", str(e.exception))

    def test_doctor_says_the_version(self):
        r = self.runtime()
        [(area, run)] = [c for c in asyncio.run(r._doctor_connections(["sabnzbd_read"], [])) if c[0] == "SABnzbd"]
        self.assertEqual(asyncio.run(run()), "SABnzbd 4.3.3, 2 in the queue")


if __name__ == "__main__":
    unittest.main()
