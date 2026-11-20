"""NZBGeek through its Newznab API (#400), against tests/fake_nzbgeek.py: the search goes without asking,
the one fetch always asks and never runs unattended, and nothing else is ever sent."""
import asyncio
import os
import sys
import unittest
from unittest import mock

import support
from second_thought.core import RunError, nzbgeek_call
from second_thought.runtime import Runtime

sys.path.insert(0, str(support.ROOT / "tests"))
import fake_nzbgeek  # noqa: E402


class AtKeyboard:
    def isatty(self):
        return True


class Calls(unittest.TestCase):
    def test_search_ask_and_never(self):
        self.assertEqual(nzbgeek_call("GET", "t=search&q=film&o=json"), "free")
        self.assertEqual(nzbgeek_call("GET", "t=tvsearch&q=show&season=1&o=json"), "free")
        self.assertEqual(nzbgeek_call("GET", "t=movie&imdbid=671234&o=json"), "free")
        self.assertEqual(nzbgeek_call("GET", "t=caps&o=json"), "free")
        self.assertEqual(nzbgeek_call("GET", "t=get&id=e9c515e02346086e3a477a5436d7bc8c"), "asks")
        for query in ("t=search&t=get&id=x", "t=get&id=x&t=search", "t=get", "t=get&id=", "t=get&id=x&id=y",
                      "t=register&email=x@y.z", "t=details&id=x", "t=rss", "t=search&q=f&t=get",
                      "t=get&id=x&t=get", "q=film", "", "t=search&q=film&t=get&id=x"):
            self.assertIsNone(nzbgeek_call("GET", query), query)
        for method in ("POST", "PUT", "DELETE"):
            self.assertIsNone(nzbgeek_call(method, "t=search&q=film"), method)


class Stack(unittest.TestCase):
    def runtime(self, here=True, env=None, answers=()):
        self.fake = fake_nzbgeek.FakeNzbgeek()
        host = self.fake.start()
        self.addCleanup(self.fake.stop)
        self.saved = mock.AsyncMock()
        save_patch = mock.patch.object(Runtime, "save_file", self.saved)
        save_patch.start()
        self.addCleanup(save_patch.stop)
        patches = [mock.patch.dict(os.environ, dict({"NZBGEEK_URL": host, "NZBGEEK_API_KEY": "key"}, **(env or {}))),
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

    def test_search_reads(self):
        r = self.runtime()
        out = asyncio.run(r.nzbgeek_search("Everything Everywhere All at Once"))
        self.assertEqual([x["title"] for x in out],
                         ["Everything.Everywhere.All.at.Once.2022.1080p.BluRay.x264-NzbGeek",
                          "Everything.Everywhere.All.at.Once.2022.2160p.WEB-DL.DDP5.7.HDR-NzbGeek"])
        self.assertEqual(out[0], {"title": "Everything.Everywhere.All.at.Once.2022.1080p.BluRay.x264-NzbGeek",
                                  "id": "e9c515e02346086e3a477a5436d7bc8c", "size_mb": 8192, "grabs": 412,
                                  "posted": "Wed, 12 Nov 2026", "group": "alt.binaries.movies"})
        self.assertEqual((out[1]["size_mb"], out[1]["grabs"]), (32768, 63))
        self.assertEqual((self.fake.refused, self.fake.fetched, self.asked, self.saved.call_count), ([], [], [], 0))

    def test_fetch_asks_every_time_and_saves(self):
        r = self.runtime(answers=[True, False])
        self.assertTrue(asyncio.run(r.nzbgeek_fetch("e9c515e02346086e3a477a5436d7bc8c")))
        self.assertFalse(asyncio.run(r.nzbgeek_fetch("https://api.nzbgeek.info/api/28e1d0c9c34a7c8d3b6f0a1924e5f7c1")))
        self.assertEqual(self.fake.fetched, ["e9c515e02346086e3a477a5436d7bc8c"])
        self.assertIn("fetch the NZB for e9c515e02346086e3a477a5436d7bc8c", self.asked[0])
        self.assertEqual(len(self.asked), 2)
        args, kwargs = self.saved.call_args
        self.assertEqual((args[1], args[2]), ("e9c515e02346086e3a477a5436d7bc8c", "nzb"))

    def test_nobody_there_means_it_never_runs(self):
        for label, kw in (("no keyboard", {"here": False}), ("GitHub Actions", {"env": {"GITHUB_ACTIONS": "true"}})):
            with self.subTest(label):
                r = self.runtime(**kw)
                self.assertFalse(asyncio.run(r.nzbgeek_fetch("e9c515e02346086e3a477a5436d7bc8c")))
                self.assertEqual((self.asked, self.fake.fetched), ([], []))

    def test_a_test_run_and_a_bad_id_do_nothing(self):
        r = self.runtime()
        r.testing = True
        self.assertFalse(asyncio.run(r.nzbgeek_fetch("e9c515e02346086e3a477a5436d7bc8c")))
        r.testing = False
        with self.assertRaises(RunError):
            asyncio.run(r.nzbgeek_fetch("   /  "))
        self.assertEqual((self.asked, self.fake.fetched, self.fake.calls), ([], [], []))

    def test_a_fetch_without_a_yes_never_leaves(self):
        r = self.runtime()
        with self.assertRaises(RunError):
            asyncio.run(r._nzbgeek({"t": "get", "id": "x"}))
        with self.assertRaises(RunError):
            asyncio.run(r._nzbgeek({"t": "register", "email": "x@y.z"}, approved=True))
        self.assertEqual(self.fake.calls, [])

    def test_without_settings_it_says_what_it_needs(self):
        with mock.patch.dict(os.environ, {"NZBGEEK_API_KEY": ""}):
            r = Runtime()
            r.reset()
            with self.assertRaises(RunError) as e:
                asyncio.run(r.nzbgeek_search("film"))
        self.assertIn("NZBGEEK_API_KEY", str(e.exception))

    def test_doctor_says_the_retention(self):
        r = self.runtime()
        [(area, run)] = [c for c in asyncio.run(r._doctor_connections(["nzbgeek_read"], [])) if c[0] == "NZBGeek"]
        self.assertEqual(asyncio.run(run()), "NZBGeek 1.0, 4000 days of retention")


if __name__ == "__main__":
    unittest.main()
