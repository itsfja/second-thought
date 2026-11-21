"""MikroTik through RouterOS's REST API (#360), against tests/fake_mikrotik.py: it only ever reads, a self-signed
certificate is used only when its fingerprint is pinned, and --doctor shows that fingerprint and checks the account."""
import asyncio
import importlib.util
import os
import sys
import unittest
from unittest import mock

import support
from second_thought.core import SAFETY, RunError, mikrotik_allowed
from second_thought.runtime import Runtime

sys.path.insert(0, str(support.ROOT / "tests"))
import fake_mikrotik  # noqa: E402

HAVE_CRYPTO = importlib.util.find_spec("cryptography") is not None


class Allowed(unittest.TestCase):
    def test_only_reading_is_ever_sent(self):
        for method, path in [("GET", "/rest/interface"), ("get", "/rest/system/resource"), ("GET", "/rest/system/health"),
                             ("GET", "/rest/log"), ("POST", "/rest/interface/ethernet/monitor")]:
            self.assertTrue(mikrotik_allowed(method, path), f"{method} {path}")
        for method, path in [("POST", "/rest/system/reboot"), ("PATCH", "/rest/interface/*1"), ("PUT", "/rest/ip/address"),
                             ("DELETE", "/rest/interface/*1"), ("POST", "/rest/execute"), ("POST", "/rest/interface/set"),
                             ("GET", "/rest/interface/*1"), ("GET", "/rest/export"), ("GET", "/rest/system/backup"),
                             ("GET", "/rest/interface?x=1"), ("POST", "/rest/interface/ethernet/monitor/x")]:
            self.assertFalse(mikrotik_allowed(method, path), f"{method} {path}")
        self.assertEqual({m for m, _ in SAFETY["mikrotik_free"]}, {"GET", "POST"})

    def test_anything_else_never_leaves(self):
        r = Runtime()
        with mock.patch.dict(os.environ, {"MIKROTIK_URL": "http://127.0.0.1:9", "MIKROTIK_USER": "u"}):
            with self.assertRaises(RunError) as e:
                asyncio.run(r._mikrotik("POST", "/rest/system/reboot"))
        self.assertIn("only reads", str(e.exception))

    def test_no_settings_says_what_to_set(self):
        with mock.patch.dict(os.environ, {"MIKROTIK_URL": "", "MIKROTIK_USER": ""}):
            with self.assertRaises(RunError) as e:
                asyncio.run(Runtime().mikrotik_health())
        self.assertIn("rest-api", str(e.exception))


class Switch(unittest.TestCase):
    def runtime(self, tls=False, pin=None, password=fake_mikrotik.PASSWORD, group=None):
        self.fake = fake_mikrotik.FakeMikrotik(tls=tls, group=group)
        url = self.fake.start()
        self.addCleanup(self.fake.stop)
        env = {"MIKROTIK_URL": url, "MIKROTIK_USER": fake_mikrotik.USER, "MIKROTIK_PASSWORD": password,
               "MIKROTIK_CERT_SHA256": pin(self.fake) if pin else ""}
        p = mock.patch.dict(os.environ, env)
        p.start()
        self.addCleanup(p.stop)
        r = Runtime()
        r.reset()
        r.log = lambda *a, **k: None
        return r

    def test_ports_sfp_health_and_log(self):
        r = self.runtime()
        ports = asyncio.run(r.mikrotik_ports())
        self.assertEqual([p["port"] for p in ports], ["ether1", "sfp-sfpplus1", "sfp-sfpplus2", "sfp-sfpplus3", "sfp-sfpplus4", "bridge"])
        self.assertEqual(ports[2], {"port": "sfp-sfpplus2", "running": True, "speed": "1Gbps", "errors": 12, "drops": 3, "link_downs": 2, "comment": "NAS"})
        self.assertEqual((ports[4]["running"], ports[4]["speed"]), (False, ""))
        sfp = asyncio.run(r.mikrotik_sfp())
        self.assertEqual(sfp[1], {"port": "sfp-sfpplus2", "module": "FS SFP-10GSR-85", "temperature": 58, "rx_power": -9.871, "tx_power": -2.39})
        self.assertEqual(sfp[2]["rx_power"], "", "a copper module has no light levels")
        health = asyncio.run(r.mikrotik_health())
        self.assertEqual({k: health[k] for k in ("board", "uptime", "cpu_load", "free_memory", "temperature", "cpu_temperature", "psu1_state")},
                         {"board": "CRS309-1G-8S+", "uptime": "3w2d4h11m", "cpu_load": 4, "free_memory": 394, "temperature": 46, "cpu_temperature": 52, "psu1_state": "ok"})
        self.assertEqual(asyncio.run(r.mikrotik_log(2)), ["2026-11-09 18:02:14 interface,info: sfp-sfpplus2 link up (speed 1G, full duplex)",
                                                          "2026-11-10 07:30:00 system,info,account: user monitor logged in via rest-api"])
        self.assertEqual(self.fake.refused, [])
        self.assertEqual({c.split()[0] for c in self.fake.calls}, {"GET", "POST"})
        self.assertEqual({c for c in self.fake.calls if c.startswith("POST")}, {"POST /rest/interface/ethernet/monitor"})

    def test_a_wrong_password_is_said_plainly(self):
        r = self.runtime(password="nope")
        with self.assertRaises(RunError) as e:
            asyncio.run(r.mikrotik_health())
        self.assertIn("refused MIKROTIK_USER", str(e.exception))

    @unittest.skipUnless(HAVE_CRYPTO, "needs the cryptography package")
    def test_a_self_signed_certificate_needs_its_pin(self):
        r = self.runtime(tls=True)
        with self.assertRaises(RunError) as e:
            asyncio.run(r.mikrotik_health())
        self.assertIn("MIKROTIK_CERT_SHA256", str(e.exception))
        self.assertEqual(self.fake.calls, [], "nothing was sent, the password included")
        r = self.runtime(tls=True, pin=lambda f: f.fingerprint.upper()[:8] + ":" + f.fingerprint[8:])
        self.assertEqual(asyncio.run(r.mikrotik_health())["board"], "CRS309-1G-8S+", "the pin can be written with capitals and colons")
        r = self.runtime(tls=True, pin=lambda f: "00" * 32)
        with self.assertRaises(RunError) as e:
            asyncio.run(r.mikrotik_health())
        self.assertIn("isn't the one", str(e.exception))
        self.assertEqual(self.fake.calls, [], "a certificate that doesn't match gets nothing")

    def doctor(self, **kw):
        r = self.runtime(**kw)
        [(area, run)] = [c for c in asyncio.run(r._doctor_connections(["mikrotik_read"], [])) if c[0] == "MikroTik"]
        try:
            got = asyncio.run(run())
        except RunError as e:
            return "FAIL", str(e)
        return got if isinstance(got, tuple) else ("ok", got)

    @unittest.skipUnless(HAVE_CRYPTO, "needs the cryptography package")
    def test_doctor_shows_the_fingerprint_and_checks_the_account(self):
        status, text = self.doctor(tls=True)
        self.assertEqual(status, "FAIL")
        self.assertIn(self.fake.fingerprint, text)
        self.assertEqual(self.fake.calls, [])
        self.assertEqual(self.doctor(tls=True, pin=lambda f: f.fingerprint), ("ok", "CRS309-1G-8S+, RouterOS 7.16.1 (stable)"))
        status, text = self.doctor(tls=True, pin=lambda f: f.fingerprint, group="full")
        self.assertEqual(status, "NOTE")
        self.assertIn("write", text)
        status, text = self.doctor()
        self.assertEqual(status, "NOTE")
        self.assertIn("https://", text)
        self.assertEqual(self.fake.refused, [])


if __name__ == "__main__":
    unittest.main()
