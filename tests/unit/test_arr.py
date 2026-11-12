"""Radarr and Sonarr through their Servarr API (#398), against tests/fake_arr.py: reads go without asking,
the one search command always asks and never runs unattended, and nothing else is ever sent."""
import asyncio
import os
import sys
import unittest
from unittest import mock

import support
from second_thought.core import RunError, arr_call, ARR_SEARCH
from second_thought.runtime import Runtime

sys.path.insert(0, str(support.ROOT / "tests"))
import fake_arr  # noqa: E402


class AtKeyboard:
    def isatty(self):
        return True


class Calls(unittest.TestCase):
    def test_reads_search_and_never(self):
        for path in ("/api/v3/queue", "/api/v3/wanted/missing", "/api/v3/diskspace", "/api/v3/system/status"):
            self.assertEqual(arr_call("GET", path), "free", path)
        self.assertEqual(arr_call("POST", "/api/v3/command"), "asks")
        for method, path in [("GET", "/api/v3/movie"), ("GET", "/api/v3/series"), ("GET", "/api/v3/config"), ("POST", "/api/v3/movie"),
                             ("DELETE", "/api/v3/movie/67"), ("POST", "/api/v3/rootFolder"), ("GET", "/api/v3/indexer"),
                             ("POST", "/api/v3/downloadclient"), ("PUT", "/api/v3/qualityprofile"), ("POST", "/api/v3/command/x"),
                             ("GET", ""), ("GET", "/api/v3/queue/../config"), ("GET", "/API/V3/QUEUE")]:
            self.assertIsNone(arr_call(method, path), f"{method} {path}")
        self.assertEqual(sorted(ARR_SEARCH.values()), ["MissingEpisodeSearch", "MissingMovieSearch"])


class Stack(unittest.TestCase):
    def runtime(self, here=True, env=None, answers=()):
        self.fakes = {w: fake_arr.FakeArr(w) for w in ("radarr", "sonarr")}
        hosts = {w: f.start() for w, f in self.fakes.items()}
        self.addCleanup(lambda: [f.stop() for f in self.fakes.values()])
        patches = [mock.patch.dict(os.environ, dict({"RADARR_URL": hosts["radarr"], "RADARR_API_KEY": "key",
                                                     "SONARR_URL": hosts["sonarr"], "SONARR_API_KEY": "key"}, **(env or {}))),
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

    def test_queue_missing_and_diskspace(self):
        r = self.runtime()
        q = asyncio.run(r.arr_queue("Radarr"))
        self.assertEqual([x["title"] for x in q], ["The Big Lebowski (1998)", "Arrival (2016)"])
        self.assertEqual(q[0], {"title": "The Big Lebowski (1998)", "status": "Importing", "size_mb": 25600, "left_mb": 0,
                                "quality": "WEBDL-1080p", "eta": "00:00:00"})
        self.assertEqual((q[1]["left_mb"], q[1]["quality"], q[1]["eta"]), (10240, "Bluray-1080p", "00:12:34"))
        m = asyncio.run(r.arr_missing("sonarr"))
        self.assertEqual([(x["title"], x["added"], x["id"]) for x in m], [("Slow Horses - S04E04", "2026-11-09", 320)])
        d = asyncio.run(r.arr_diskspace("radarr"))
        self.assertEqual(d, [{"path": "/mnt/user/media/movies", "label": "movies", "free_gb": 500, "total_gb": 1863.02}])
        for f in self.fakes.values():
            self.assertEqual((f.refused, f.searched), ([], []))
        self.assertEqual(self.asked, [])

    def test_search_asks_every_time(self):
        r = self.runtime(answers=[True, False])
        self.assertTrue(asyncio.run(r.arr_search("radarr")))
        self.assertFalse(asyncio.run(r.arr_search("sonarr")))
        self.assertEqual(self.fakes["radarr"].searched, ["radarr MissingMovieSearch"])
        self.assertIn("search Radarr's wanted list", self.asked[0])
        self.assertEqual(len(self.asked), 2)

    def test_nobody_there_means_it_never_runs(self):
        for label, kw in (("no keyboard", {"here": False}), ("GitHub Actions", {"env": {"GITHUB_ACTIONS": "true"}})):
            with self.subTest(label):
                r = self.runtime(**kw)
                self.assertFalse(asyncio.run(r.arr_search("radarr")))
                self.assertEqual((self.asked, self.fakes["radarr"].searched), ([], []))

    def test_a_test_run_and_bad_requests_do_nothing(self):
        r = self.runtime()
        r.testing = True
        self.assertFalse(asyncio.run(r.arr_search("radarr")))
        r.testing = False
        for which in ("lidarr", "", "PROXMOX"):
            with self.assertRaises(RunError, msg=which):
                asyncio.run(r.arr_queue(which))
        self.assertEqual((self.asked, [f.searched for f in self.fakes.values()]), ([], [[], []]))

    def test_a_search_without_a_yes_never_leaves(self):
        r = self.runtime()
        with self.assertRaises(RunError):
            asyncio.run(r._arr("radarr", "POST", "/api/v3/command"))
        with self.assertRaises(RunError):
            asyncio.run(r._arr("radarr", "GET", "/api/v3/config", approved=True))
        self.assertEqual(self.fakes["radarr"].calls, [])

    def test_without_settings_it_says_what_it_needs(self):
        with mock.patch.dict(os.environ, {"RADARR_URL": "", "RADARR_API_KEY": ""}):
            r = Runtime()
            r.reset()
            with self.assertRaises(RunError) as e:
                asyncio.run(r.arr_queue("radarr"))
        self.assertIn("RADARR_URL", str(e.exception))

    def test_doctor_says_the_version(self):
        r = self.runtime()
        [(area, run)] = [c for c in asyncio.run(r._doctor_connections(["arr_read"], [])) if c[0] == "Radarr"]
        self.assertEqual(asyncio.run(run()), "Radarr 4.7.5.8805, 2 in the queue")


if __name__ == "__main__":
    unittest.main()
