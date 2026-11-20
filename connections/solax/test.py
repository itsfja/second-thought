"""Solax through SolaxCloud's end-user API (#361), against tests/fake_solax.py: the figures in readable units (the
API gives yieldtoday in 0.1 kWh and feedinenergy in 0.01 kWh), one call kept for five minutes because the cloud
allows only ten a minute, a refused token or Registration No. said plainly, and --doctor checks both settings and
reaches the cloud."""
import asyncio
import contextlib
import os
import unittest
from unittest import mock

import support
from second_thought.core import RunError
from second_thought.runtime import Runtime
import fake_solax


class Solax(unittest.TestCase):
    def setUp(self):
        self.fake = fake_solax.FakeSolax()
        self.url = self.fake.start()
        self.addCleanup(self.fake.stop)

    @contextlib.contextmanager
    def runtime(self, env=None):
        r = Runtime()
        r.reset()
        r.log = lambda *a, **k: None
        with mock.patch.dict(os.environ, dict({"SOLAX_API_URL": self.url,
                                               "SOLAX_TOKEN_ID": fake_solax.TOKEN, "SOLAX_SN": fake_solax.SN},
                                              **(env or {}))):
            yield r

    def run_now(self, env=None):
        with self.runtime(env) as r:
            return r, asyncio.run(r.solax_now())

    def test_the_figures_in_readable_units(self):
        r, got = self.run_now()
        self.assertEqual(got, {"ac_power_w": 2450, "yield_today_kwh": 8.4, "yield_total_kwh": 412.5,
                              "feedin_power_w": 900, "feedin_energy_kwh": 32.1, "import_energy_kwh": 18.9,
                              "battery_soc_pct": 62, "status": "Normal Mode", "upload_time": "2026-11-11 14:05:00"})

    def test_one_call_is_kept_for_five_minutes(self):
        with self.runtime() as r:
            got = asyncio.run(r.solax_now())
            self.assertEqual(len(self.fake.calls), 1)
            self.fake.data = dict(self.fake.data, result=dict(self.fake.data["result"], acpower="3000"))
            again = asyncio.run(r.solax_now())
            self.assertEqual(len(self.fake.calls), 1, "the five minutes haven't passed, so no second call")
            self.assertEqual(again["ac_power_w"], got["ac_power_w"])
            r.__dict__["_solax_cache"] = (r._solax_cache[0] - r.SOLAX_SECONDS, None)  # the five minutes have passed
            self.assertEqual(asyncio.run(r.solax_now())["ac_power_w"], 3000)
            self.assertEqual(len(self.fake.calls), 2)

    def test_a_refused_token_or_registration_no_is_said_plainly(self):
        with self.runtime({"SOLAX_TOKEN_ID": "wrong"}) as r:
            with self.assertRaises(RunError) as e:
                asyncio.run(r.solax_now())
        self.assertIn("refused the token or the Registration No.", str(e.exception))
        self.assertIn("SN or Token is incorrect", str(e.exception))

    def test_both_settings_are_needed(self):
        for env in ({"SOLAX_TOKEN_ID": ""}, {"SOLAX_SN": ""}):
            with self.subTest(env):
                with self.runtime(env) as r:
                    with self.assertRaises(RunError) as e:
                        asyncio.run(r.solax_now())
                self.assertIn("SOLAX_TOKEN_ID and SOLAX_SN", str(e.exception))

    def test_the_status_names(self):
        self.assertEqual(Runtime._solax_status("102"), "Normal Mode")
        self.assertEqual(Runtime._solax_status("103"), "Fault Mode")
        self.assertEqual(Runtime._solax_status("999"), "999")

    def test_an_inverter_without_a_battery_leaves_the_charge_empty(self):
        self.fake.data = dict(self.fake.data, result=dict(self.fake.data["result"], soc="-1"))
        r, got = self.run_now()
        self.assertEqual(got["battery_soc_pct"], "")

    def doctor(self, env=None):
        with self.runtime(env) as r:
            [(_, run)] = [c for c in asyncio.run(r._doctor_connections(["solax_read"], [])) if c[0] == "Solax"]
            return asyncio.run(run())

    def test_doctor_reaches_the_cloud(self):
        text = self.doctor()
        self.assertIn("reached SolaxCloud", text)
        self.assertIn("Normal Mode", text)
        self.assertIn("14:05", text)
        self.assertEqual(len(self.fake.calls), 1)

    def test_doctor_needs_the_settings(self):
        with self.assertRaises(RunError) as e:
            self.doctor(env={"SOLAX_TOKEN_ID": ""})
        self.assertIn("SOLAX_TOKEN_ID and SOLAX_SN", str(e.exception))




if __name__ == "__main__":
    unittest.main()
