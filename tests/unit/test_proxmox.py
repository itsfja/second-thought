"""Proxmox VE through its REST API (#357), against tests/fake_proxmox.py: reads go without asking, starting, shutting
down and rebooting always ask and never run unattended, protected guests are never touched, and nothing else is sent."""
import asyncio
import importlib.util
import os
import sys
import unittest
from unittest import mock

import support
from second_thought.core import SAFETY, RunError, proxmox_call
from second_thought.runtime import Runtime

sys.path.insert(0, str(support.ROOT / "tests"))
import fake_proxmox  # noqa: E402

HAVE_CRYPTO = importlib.util.find_spec("cryptography") is not None
API = "/api2/json"


class AtKeyboard:
    def isatty(self):
        return True


class Calls(unittest.TestCase):
    def test_reads_power_and_never(self):
        for path in ("/version", "/nodes", "/cluster/resources", "/cluster/tasks", "/access/permissions", "/nodes/pve1/qemu/100/config"):
            self.assertEqual(proxmox_call("GET", API + path), "free", path)
        for action in ("start", "shutdown", "reboot"):
            self.assertEqual(proxmox_call("POST", f"{API}/nodes/pve1/lxc/104/status/{action}"), "asks")
        for method, path in [("POST", "/nodes/pve1/qemu/100/status/stop"), ("DELETE", "/nodes/pve1/qemu/100"), ("POST", "/nodes/pve1/qemu/100/snapshot"),
                             ("POST", "/nodes/pve1/qemu/100/snapshot/s1/rollback"), ("POST", "/nodes/pve1/qemu/100/agent/exec"),
                             ("POST", "/nodes/pve1/qemu/100/migrate"), ("POST", "/nodes/pve1/vzdump"), ("PUT", "/nodes/pve1/qemu/100/config"),
                             ("PUT", "/access/acl"), ("POST", "/storage"), ("PUT", "/cluster/firewall/options"), ("GET", "/nodes/pve1/qemu/100/vncproxy"),
                             ("POST", "/nodes/pve1/execute"), ("GET", "/nodes/pve1/qemu/100/config/../../../x")]:
            self.assertIsNone(proxmox_call(method, API + path), f"{method} {path}")
        self.assertEqual({m for m, _ in SAFETY["proxmox_free"]}, {"GET"})


class Cluster(unittest.TestCase):
    def runtime(self, tls=False, pin=None, here=True, env=None, answers=(), **kw):
        self.fake = fake_proxmox.FakeProxmox(tls=tls, **kw)
        url = self.fake.start()
        self.addCleanup(self.fake.stop)
        patches = [mock.patch.dict(os.environ, dict({"PROXMOX_URL": url, "PROXMOX_TOKEN_ID": fake_proxmox.TOKEN_ID, "PROXMOX_TOKEN_SECRET": fake_proxmox.SECRET,
                                                     "PROXMOX_CERT_SHA256": pin(self.fake) if pin else "", "PROXMOX_PROTECT": "100, 101"}, **(env or {}))),
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
        r.ask_first = set()
        return r

    def test_nodes_guests_storage_and_tasks(self):
        r = self.runtime()
        self.assertEqual(asyncio.run(r.proxmox_nodes())[0], {"node": "pve1", "status": "online", "cpu": 7.3, "memory": 62.5, "uptime": 504})
        guests = asyncio.run(r.proxmox_guests())
        self.assertEqual([g["vmid"] for g in guests], [100, 101, 102, 103, 104, 105], "templates left out")
        self.assertEqual({k: guests[4][k] for k in ("name", "type", "status", "onboot")}, {"name": "pihole", "type": "container", "status": "stopped", "onboot": True})
        self.assertEqual((guests[5]["onboot"], guests[0]["onboot"]), (False, ""), "onboot is read for stopped guests only")
        storage = asyncio.run(r.proxmox_storage())
        self.assertEqual({k: storage[1][k] for k in ("storage", "node", "used", "size_gb")}, {"storage": "local-lvm", "node": "pve1", "used": 88, "size_gb": 800})
        tasks = asyncio.run(r.proxmox_tasks(24))
        self.assertEqual([(t["type"], t["id"]) for t in tasks], [("vzdump", "103"), ("vzdump", "")], "newest first, the last 24 hours only")
        self.assertTrue(tasks[0]["status"].startswith("ERROR"))
        self.assertEqual(self.asked, [])
        self.assertEqual({c.split()[0] for c in self.fake.calls}, {"GET"})
        self.assertEqual(self.fake.refused, [])

    def test_power_asks_every_time_with_what_and_where(self):
        r = self.runtime(answers=[True, False])
        self.assertTrue(asyncio.run(r.proxmox_power("start", 104)))
        self.assertFalse(asyncio.run(r.proxmox_power("reboot", "102")))
        self.assertEqual(self.fake.powered, ["start 104"])
        self.assertIn("start the Proxmox guest 104 (pihole, on pve2, now stopped)", self.asked[0])
        self.assertEqual(len(self.asked), 2)

    def test_protected_guests_are_never_touched(self):
        r = self.runtime()
        for vmid in (100, 101):
            self.assertFalse(asyncio.run(r.proxmox_power("shutdown", vmid)))
        self.assertEqual((self.asked, self.fake.powered), ([], []))
        self.assertTrue(any("PROXMOX_PROTECT" in str(a) for a in self.logged))

    def test_nobody_there_means_it_never_runs(self):
        for label, kw in (("no keyboard", {"here": False}), ("GitHub Actions", {"env": {"GITHUB_ACTIONS": "true"}})):
            with self.subTest(label):
                r = self.runtime(**kw)
                self.assertFalse(asyncio.run(r.proxmox_power("start", 104)))
                self.assertEqual((self.asked, self.fake.powered), ([], []))
                self.assertTrue(any("nobody is" in str(a) for a in self.logged))

    def test_a_test_run_and_bad_requests_do_nothing(self):
        r = self.runtime()
        r.testing = True
        self.assertFalse(asyncio.run(r.proxmox_power("start", 104)))
        r.testing = False
        for action, vmid in (("stop", 104), ("destroy", 104), ("start", "x"), ("start", 99), ("start", 104.5)):
            with self.assertRaises(RunError, msg=f"{action} {vmid}"):
                asyncio.run(r.proxmox_power(action, vmid))
        with self.assertRaises(RunError):
            asyncio.run(r.proxmox_power("start", 999))
        self.assertEqual((self.asked, self.fake.powered, self.fake.refused), ([], [], []))

    def test_an_auditor_token_is_refused_by_proxmox(self):
        r = self.runtime(can_power=False)
        with self.assertRaises(RunError) as e:
            asyncio.run(r.proxmox_power("start", 104))
        self.assertIn("isn't allowed", str(e.exception))

    def test_a_power_call_without_a_yes_never_leaves(self):
        r = self.runtime()
        with self.assertRaises(RunError):
            asyncio.run(r._proxmox("POST", f"{API}/nodes/pve2/lxc/104/status/start"))
        self.assertEqual(self.fake.calls, [])

    @unittest.skipUnless(HAVE_CRYPTO, "needs the cryptography package")
    def test_doctor_pins_and_checks_the_token(self):
        def doctor(can, **kw):
            r = self.runtime(**kw)
            [(area, run)] = [c for c in asyncio.run(r._doctor_connections(can, [])) if c[0] == "Proxmox"]
            try:
                got = asyncio.run(run())
            except RunError as e:
                return "FAIL", str(e)
            return got if isinstance(got, tuple) else ("ok", got)
        status, text = doctor(["proxmox_read"], tls=True)
        self.assertEqual(status, "FAIL")
        self.assertIn(self.fake.fingerprint, text)
        pin = lambda f: f.fingerprint  # noqa: E731
        self.assertEqual(doctor(["proxmox_read"], tls=True, pin=pin), ("ok", "Proxmox VE 8.4.1"))
        self.assertEqual(doctor(["proxmox_read", "proxmox_control"], tls=True, pin=pin)[0], "FAIL", "an auditor's token can't start guests")
        admin = {"/": {"VM.Audit": 1, "VM.PowerMgmt": 1, "VM.Allocate": 1, "Sys.Modify": 1}}
        status, text = doctor(["proxmox_read"], tls=True, pin=pin, permissions=admin)
        self.assertEqual(status, "NOTE")
        self.assertIn("VM.Allocate", text)
        self.assertIn("VM.PowerMgmt", text, "a read-only program doesn't need power either")
        self.assertEqual(doctor(["proxmox_read", "proxmox_control"], tls=True, pin=pin, permissions={"/": {"VM.Audit": 1, "VM.PowerMgmt": 1}}),
                         ("ok", "Proxmox VE 8.4.1"))


if __name__ == "__main__":
    unittest.main()
