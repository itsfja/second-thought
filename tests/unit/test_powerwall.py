"""Tesla's Powerwall through the gateway's local API (#362), against tests/fake_powerwall.py: the figures in readable
shape (battery charge, solar, grid, house, reserve, mode, grid status), one login kept for the run, a wrong password
said plainly, the reserve change always asks (a no means nothing is sent, and with nobody there to say yes it never
runs), and only the calls in SAFETY are ever made."""
import asyncio
import contextlib
import os
import unittest
from unittest import mock

import support
import fake_powerwall
from second_thought.core import RunError
from second_thought.runtime import Runtime


class AtKeyboard:
    def isatty(self):
        return True


class Powerwall(unittest.TestCase):
    def setUp(self):
        self.fake = fake_powerwall.FakePowerwall()
        self.url = self.fake.start()
        self.addCleanup(self.fake.stop)

    @contextlib.contextmanager
    def runtime(self, env=None, here=True):
        r = Runtime()
        r.reset()
        r.log = lambda *a, **k: None
        with mock.patch.dict(os.environ, dict({"POWERWALL_URL": self.url, "POWERWALL_PASSWORD": fake_powerwall.PASSWORD},
                                              **(env or {}))), \
                mock.patch.object(Runtime, "nobody_here", return_value=not here), \
                mock.patch.object(__import__("sys").stdin, "isatty", return_value=here):
            yield r

    def test_the_figures(self):
        with self.runtime() as r:
            got = asyncio.run(r.powerwall_now())
        self.assertEqual(got, {"battery_soc_pct": 76.5, "solar_power_w": 2450, "battery_power_w": 1200,
                              "grid_power_w": -450, "load_power_w": 800, "reserve_pct": 20,
                              "mode": "self_consumption", "grid": "connected"})
        self.assertEqual(sorted(str(c[:2]) for c in self.fake.calls), sorted(str(c) for c in
                         [("POST", "/api/login/Basic")] + [("GET", p) for p in
                          ("/api/meters/aggregates", "/api/operation", "/api/system_status/grid_status", "/api/system_status/soe")]),
                         "the four reads happen together, so their order is whatever finished first")
        self.assertIn(("POST", "/api/login/Basic", "login"), self.fake.calls, "one login, and it worked")

    def test_one_login_is_kept(self):
        with self.runtime() as r:
            asyncio.run(r.powerwall_now())
            asyncio.run(r.powerwall_now())
        self.assertEqual([c for c in self.fake.calls if c[2] == "login"], [("POST", "/api/login/Basic", "login")],
                         "the token is kept, so the second read needs no new login")

    def test_a_wrong_password_is_said_plainly(self):
        with self.runtime({"POWERWALL_PASSWORD": "wrong"}) as r:
            with self.assertRaises(RunError) as e:
                asyncio.run(r.powerwall_now())
        self.assertIn("refused POWERWALL_PASSWORD", str(e.exception))

    def test_both_settings_are_needed(self):
        for env in ({"POWERWALL_URL": ""}, {"POWERWALL_PASSWORD": ""}):
            with self.subTest(env):
                with self.runtime(env) as r:
                    with self.assertRaises(RunError) as e:
                        asyncio.run(r.powerwall_now())
                self.assertIn("POWERWALL_URL and POWERWALL_PASSWORD", str(e.exception))

    def test_the_reserve_change_asks_and_a_yes_sets_it(self):
        with self.runtime() as r:
            asked = []

            async def yes(what):
                asked.append(what)
                return True
            r._approve_live = yes
            self.assertTrue(asyncio.run(r.powerwall_reserve(100)))
        self.assertEqual(len(asked), 1)
        self.assertIn("100%", asked[0])
        self.assertIn("20%", asked[0], "what it asks says what the reserve is now")
        self.assertEqual(self.fake.reserve, 100)
        self.assertIn(("POST", "/api/operation", "write"), self.fake.calls)

    def test_a_no_means_nothing_is_sent(self):
        with self.runtime() as r:

            async def no(what):
                return False
            r._approve_live = no
            self.assertFalse(asyncio.run(r.powerwall_reserve(100)))
        self.assertNotIn(("POST", "/api/operation", "write"), self.fake.calls)
        self.assertEqual(self.fake.reserve, 20)

    def test_nobody_there_means_it_never_runs(self):
        with self.runtime(here=False) as r:
            asked = []

            async def never(what):
                asked.append(what)
                return True
            r._approve_live = never
            self.assertFalse(asyncio.run(r.powerwall_reserve(100)))
        self.assertEqual(asked, [], "not even asked: there's nobody to answer")
        self.assertNotIn(("POST", "/api/operation", "write"), self.fake.calls)

    def test_the_reserve_is_clamped_and_a_test_run_skips_it(self):
        with self.runtime() as r:
            r.testing = True
            self.assertFalse(asyncio.run(r.powerwall_reserve(150)))
        self.assertNotIn(("POST", "/api/operation", "write"), self.fake.calls)

    def doctor(self, env=None):
        with self.runtime(env) as r:
            [(_, run)] = [c for c in asyncio.run(r._doctor_connections(["powerwall_read"], [])) if c[0] == "Powerwall"]
            return asyncio.run(run())

    def test_doctor_reports_the_battery(self):
        text = self.doctor()
        self.assertIn("battery at 76.5%", text)
        self.assertIn("reserve 20%", text)
        self.assertIn("connected", text)

    def test_doctor_needs_the_settings(self):
        with self.assertRaises(RunError) as e:
            self.doctor(env={"POWERWALL_PASSWORD": ""})
        self.assertIn("POWERWALL_URL and POWERWALL_PASSWORD", str(e.exception))



if __name__ == "__main__":
    unittest.main()
