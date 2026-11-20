"""UniFi through a console's Network API (#359), against tests/fake_unifi.py: it only ever reads, follows pages, and pins
the console's own certificate the way the MikroTik connection does."""
import asyncio
import importlib.util
import os
import sys
import unittest
from unittest import mock

import support
from second_thought.core import SAFETY, RunError, unifi_allowed
from second_thought.runtime import Runtime

sys.path.insert(0, str(support.ROOT / "tests"))
import fake_unifi  # noqa: E402

HAVE_CRYPTO = importlib.util.find_spec("cryptography") is not None
API = "/proxy/network/integration/v1"


class Allowed(unittest.TestCase):
    def test_only_reading_is_ever_sent(self):
        for path in ("/info", "/sites", "/sites/abc-1/clients", "/sites/abc-1/devices", "/sites/abc-1/devices/d-2/statistics/latest"):
            self.assertTrue(unifi_allowed("GET", API + path), path)
        for method, path in [("POST", "/sites/abc-1/clients/c-1/actions"), ("POST", "/sites/abc-1/devices/d-2/actions"),
                             ("POST", "/sites/abc-1/devices/d-2/interfaces/ports/1/actions"), ("POST", "/sites/abc-1/hotspot/vouchers"),
                             ("DELETE", "/sites/abc-1/hotspot/vouchers/v"), ("GET", "/sites/abc-1/hotspot/vouchers"),
                             ("GET", "/sites/abc-1/clients/../devices"), ("GET", "/sites/abc-1/clients?x=1")]:
            self.assertFalse(unifi_allowed(method, API + path), f"{method} {path}")
        self.assertFalse(unifi_allowed("GET", "/proxy/network/api/s/default/cmd/devmgr"))
        self.assertEqual({m for m, _ in SAFETY["unifi_free"]}, {"GET"})

    def test_no_settings_says_what_to_set(self):
        with mock.patch.dict(os.environ, {"UNIFI_URL": "", "UNIFI_API_KEY": ""}):
            with self.assertRaises(RunError) as e:
                asyncio.run(Runtime().unifi_clients())
        self.assertIn("Integrations", str(e.exception))


class Network(unittest.TestCase):
    def runtime(self, tls=False, pin=None, key=fake_unifi.KEY):
        self.fake = fake_unifi.FakeUnifi(tls=tls)
        url = self.fake.start()
        self.addCleanup(self.fake.stop)
        p = mock.patch.dict(os.environ, {"UNIFI_URL": url, "UNIFI_API_KEY": key, "UNIFI_CERT_SHA256": pin(self.fake) if pin else "", "UNIFI_SITE": ""})
        p.start()
        self.addCleanup(p.stop)
        r = Runtime()
        r.reset()
        r.log = lambda *a, **k: None
        return r

    def test_clients_and_devices_page_by_page(self):
        r = self.runtime()
        clients = asyncio.run(r.unifi_clients())
        self.assertEqual(len(clients), 6, "three pages of two")
        self.assertEqual({k: clients[1][k] for k in ("name", "mac", "ip", "type", "uplink")},
                         {"name": "NAS", "mac": "00:11:32:aa:bb:01", "ip": "192.168.1.10", "type": "wired", "uplink": "Office switch"})
        self.assertEqual(clients[5]["name"], "de:ad:be:ef:00:42", "a client with no name goes by its MAC address")
        devices = asyncio.run(r.unifi_devices())
        self.assertEqual([(d["name"], d["state"], d["update"]) for d in devices],
                         [("Gateway", "online", False), ("Office switch", "online", True), ("Living room AP", "online", False), ("Garden AP", "offline", True)])
        self.assertEqual((devices[0]["uptime"], devices[0]["cpu"], devices[0]["memory"]), (360, 12.5, 61.2))
        self.assertEqual(devices[3]["uptime"], "", "an offline device has no statistics")
        self.assertEqual(self.fake.refused, [])
        self.assertEqual({c.split()[0] for c in self.fake.calls}, {"GET"})

    def test_a_wrong_key_is_said_plainly(self):
        r = self.runtime(key="nope")
        with self.assertRaises(RunError) as e:
            asyncio.run(r.unifi_devices())
        self.assertIn("refused UNIFI_API_KEY", str(e.exception))

    @unittest.skipUnless(HAVE_CRYPTO, "needs the cryptography package")
    def test_the_consoles_certificate_needs_its_pin(self):
        r = self.runtime(tls=True)
        with self.assertRaises(RunError) as e:
            asyncio.run(r.unifi_devices())
        self.assertIn("UNIFI_CERT_SHA256", str(e.exception))
        self.assertEqual(self.fake.calls, [], "nothing was sent, the key included")
        r = self.runtime(tls=True, pin=lambda f: f.fingerprint)
        self.assertEqual(len(asyncio.run(r.unifi_devices())), 4)

    @unittest.skipUnless(HAVE_CRYPTO, "needs the cryptography package")
    def test_doctor_shows_the_fingerprint_then_the_network(self):
        def doctor(**kw):
            r = self.runtime(**kw)
            [(area, run)] = [c for c in asyncio.run(r._doctor_connections(["unifi_read"], [])) if c[0] == "UniFi"]
            try:
                return asyncio.run(run())
            except RunError as e:
                return "FAIL: " + str(e)
        self.assertIn("UNIFI_CERT_SHA256 = ", doctor(tls=True))
        self.assertEqual(doctor(tls=True, pin=lambda f: f.fingerprint), "UniFi Network 9.5.21, 4 devices")
        self.assertEqual(self.fake.refused, [])


if __name__ == "__main__":
    unittest.main()
