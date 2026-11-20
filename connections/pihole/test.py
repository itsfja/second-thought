"""Pi-hole through its REST API (#401), against tests/fake_pihole.py: the stats and the blocking status go
without asking, blocking and the allow and deny lists always ask and never run unattended, and nothing else is
ever sent."""
import asyncio
import os
import sys
import unittest
from unittest import mock

import support
from second_thought.core import RunError, pihole_call
from second_thought.runtime import Runtime

sys.path.insert(0, str(support.ROOT / "tests"))
import fake_pihole  # noqa: E402


class AtKeyboard:
    def isatty(self):
        return True


class Calls(unittest.TestCase):
    def test_reads_ask_and_never(self):
        for path in ("/api/stats/summary", "/api/stats/top_domains", "/api/stats/top_clients", "/api/dns/blocking"):
            self.assertEqual(pihole_call("GET", path), "free", path)
        self.assertEqual(pihole_call("POST", "/api/auth"), "free")
        self.assertEqual(pihole_call("POST", "/api/dns/blocking"), "asks")
        self.assertEqual(pihole_call("POST", "/api/domains/allowlist/exact"), "asks")
        self.assertEqual(pihole_call("POST", "/api/domains/denylist/exact"), "asks")
        self.assertEqual(pihole_call("DELETE", "/api/domains/allowlist/exact"), "asks")
        for method, path in [("GET", "/api/config/dns"), ("POST", "/api/config/dns"), ("POST", "/api/dhcp"),
                            ("PUT", "/api/config/webserver"), ("POST", "/api/auth/x"), ("GET", "/api/queries"),
                            ("POST", "/api/domains/allowlist/regex"), ("POST", "/api/groups"),
                            ("GET", "/api/stats/summary?x=1"), ("DELETE", "/api/dns/blocking"), ("GET", "")]:
            self.assertIsNone(pihole_call(method, path), f"{method} {path}")


class Stack(unittest.TestCase):
    def runtime(self, here=True, env=None, answers=()):
        self.fake = fake_pihole.FakePihole()
        host = self.fake.start()
        self.addCleanup(self.fake.stop)
        patches = [mock.patch.dict(os.environ, dict({"PIHOLE_URL": host, "PIHOLE_PASSWORD": "pw"}, **(env or {}))),
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

    def test_summary_and_tops_read(self):
        r = self.runtime()
        s = asyncio.run(r.pihole_summary())
        self.assertEqual(s, {"queries": 85000, "blocked": 12000, "blocked_pct": 14.1, "gravity": 1200000,
                             "clients": 12, "blocking": True})
        d = asyncio.run(r.pihole_top_domains(2))
        self.assertEqual(d, [{"domain": "ads.example.com", "count": 3210}, {"domain": "tracker.example.net", "count": 1842}])
        c = asyncio.run(r.pihole_top_clients(2))
        self.assertEqual(c, [{"name": "livingroom-tv", "ip": "192.168.1.42", "count": 5400},
                             {"name": "fridge", "ip": "192.168.1.51", "count": 2210}])
        self.assertEqual((self.fake.refused, self.fake.changed, self.asked), ([], [], []))
        self.assertEqual(self.fake.signins, 1)  # one session for the whole run

    def test_blocking_and_lists_ask_every_time(self):
        r = self.runtime(answers=[True, False, True, True])
        self.assertTrue(asyncio.run(r.pihole_blocking(60)))
        self.assertFalse(asyncio.run(r.pihole_blocking(120)))
        self.assertTrue(asyncio.run(r.pihole_enable()))
        self.assertTrue(asyncio.run(r.pihole_list("allow", "add", "ads.example.com")))
        self.assertEqual(self.fake.changed, ['POST /api/dns/blocking {"blocking": false, "timer": 60}',
                                              'POST /api/dns/blocking {"blocking": true}',
                                              'POST /api/domains/allowlist/exact {"domain": "ads.example.com", "comment": "added by Second Thought"}'])
        self.assertIn("disable Pi-hole's blocking for 60 seconds", self.asked[0])
        self.assertIn("enable Pi-hole's blocking", self.asked[2])
        self.assertIn("add ads.example.com on Pi-hole's allow list", self.asked[3])
        self.assertEqual(len(self.asked), 4)

    def test_removing_a_domain_sends_delete(self):
        r = self.runtime()
        self.assertTrue(asyncio.run(r.pihole_list("deny", "remove", "BAD.Example.com")))
        self.assertEqual(self.fake.changed, ['DELETE /api/domains/denylist/exact {"domain": ["bad.example.com"]}'])

    def test_nobody_there_means_it_never_runs(self):
        for label, kw in (("no keyboard", {"here": False}), ("GitHub Actions", {"env": {"GITHUB_ACTIONS": "true"}})):
            with self.subTest(label):
                r = self.runtime(**kw)
                self.assertFalse(asyncio.run(r.pihole_blocking(60)))
                self.assertFalse(asyncio.run(r.pihole_enable()))
                self.assertFalse(asyncio.run(r.pihole_list("deny", "add", "bad.example.com")))
                self.assertEqual((self.asked, self.fake.changed), ([], []))

    def test_a_test_run_and_bad_requests_do_nothing(self):
        r = self.runtime()
        r.testing = True
        self.assertFalse(asyncio.run(r.pihole_blocking(60)))
        self.assertFalse(asyncio.run(r.pihole_enable()))
        self.assertFalse(asyncio.run(r.pihole_list("allow", "add", "ads.example.com")))
        r.testing = False
        for args in ((0,), (-5,), ("x",)):
            with self.assertRaises(RunError, msg=str(args)):
                asyncio.run(r.pihole_blocking(*args))
        for which, action, domain in (("block", "add", "x.com"), ("allow", "toggle", "x.com"), ("allow", "add", "")):
            with self.assertRaises(RunError, msg=f"{which} {action}"):
                asyncio.run(r.pihole_list(which, action, domain))
        self.assertEqual((self.asked, self.fake.changed, self.fake.calls), ([], [], []))

    def test_a_change_without_a_yes_never_leaves(self):
        r = self.runtime()
        with self.assertRaises(RunError):
            asyncio.run(r._pihole("POST", "/api/dns/blocking", {"blocking": False}))
        with self.assertRaises(RunError):
            asyncio.run(r._pihole("POST", "/api/config/dns", {"upstream": "8.8.8.8"}, approved=True))
        self.assertEqual(self.fake.calls, [])

    def test_a_session_that_ran_out_signs_in_again(self):
        r = self.runtime()
        asyncio.run(r.pihole_summary())
        self.fake.expire_sid = True
        s = asyncio.run(r.pihole_summary())
        self.assertEqual(s["queries"], 85000)
        self.assertEqual(self.fake.signins, 2)

    def test_a_wrong_password_is_refused(self):
        r = self.runtime(env={"PIHOLE_PASSWORD": "nope"})
        with self.assertRaises(RunError) as e:
            asyncio.run(r.pihole_summary())
        self.assertIn("refused its password", str(e.exception))

    def test_without_settings_it_says_what_it_needs(self):
        with mock.patch.dict(os.environ, {"PIHOLE_URL": "", "PIHOLE_PASSWORD": ""}):
            r = Runtime()
            r.reset()
            with self.assertRaises(RunError) as e:
                asyncio.run(r.pihole_summary())
        self.assertIn("PIHOLE_URL", str(e.exception))

    def test_doctor_says_the_queries(self):
        r = self.runtime()
        [(area, run)] = [c for c in asyncio.run(r._doctor_connections(["pihole_read"], [])) if c[0] == "Pi-hole"]
        self.assertEqual(asyncio.run(run()), "85000 queries, 12000 blocked")


if __name__ == "__main__":
    unittest.main()
