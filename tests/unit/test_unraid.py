"""Unraid through its GraphQL API (#399), against tests/fake_unraid.py: reads go without asking, start,
stop and a parity check always ask and never run unattended, and nothing else is ever sent."""
import asyncio
import os
import sys
import unittest
from unittest import mock

import support
from second_thought.core import RunError, unraid_call
from second_thought.runtime import Runtime

sys.path.insert(0, str(support.ROOT / "tests"))
import fake_unraid  # noqa: E402


class AtKeyboard:
    def isatty(self):
        return True


class Calls(unittest.TestCase):
    def test_reads_ask_and_never(self):
        self.assertEqual(unraid_call("POST", "query{array{state}}"), "free")
        self.assertEqual(unraid_call("POST", "{shares{name}}"), "free")
        self.assertEqual(unraid_call("POST", '  query{vms{domains{name}}}'), "free")
        self.assertEqual(unraid_call("POST", 'mutation{docker{start(id:"container:plex"){id}}}'), "asks")
        self.assertEqual(unraid_call("POST", 'mutation{docker{stop(id:"container:pihole"){id}}}'), "asks")
        self.assertEqual(unraid_call("POST", 'mutation{vm{start(id:"vm:windows")}}'), "asks")
        self.assertEqual(unraid_call("POST", 'mutation{vm{stop(id:"vm:arch")}}'), "asks")
        self.assertEqual(unraid_call("POST", "mutation{parity{start(correct:false)}}"), "asks")
        for query in ['mutation{array{setState(input:{desiredState: STOP}){state}}}',
                      'mutation{docker{restart(id:"container:plex"){id}}}',
                      'mutation{docker{removeContainer(id:"container:plex", withImage:true)}}',
                      'mutation{docker{updateAllContainers{id}}}',
                      'mutation{vm{forceStop(id:"vm:windows")}}',
                      'mutation{parity{start(correct:true)}}',
                      'mutation{parity{cancel()}}',
                      'mutation{array{addDiskToArray(input:{id:"disk:1", slot:1}){id}}}',
                      'mutation{unraid{installPlugin(input:{url:"http://x"}){id}}}',
                      'mutation{vm{start(id:"vm:windows")restart(id:"vm:arch")}}',
                      'mutation{vm{start(id:"vm:windows")}docker{stop(id:"container:plex"){id}}}',
                      'mutation{vm{start(id:"")}}',
                      "query{array{state}}mutation{docker{stop(id:\"container:plex\"){id}}}",
                      "subscription{arraySubscription{state}}",
                      ""]:
            self.assertIsNone(unraid_call("POST", query), query)
        for method in ("GET", "PUT", "DELETE"):
            self.assertIsNone(unraid_call(method, "query{array{state}}"), method)


class Stack(unittest.TestCase):
    def runtime(self, here=True, env=None, answers=()):
        self.fake = fake_unraid.FakeUnraid()
        host = self.fake.start()
        self.addCleanup(self.fake.stop)
        patches = [mock.patch.dict(os.environ, dict({"UNRAID_URL": host, "UNRAID_API_KEY": "key"}, **(env or {}))),
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

    def test_array_disks_shares_containers_and_vms(self):
        r = self.runtime()
        a = asyncio.run(r.unraid_array())
        self.assertEqual(a, {"state": "STARTED", "started": True, "free_gb": 2048, "total_gb": 6144,
                             "uptime": "3 days, 4:56:07"})
        d = asyncio.run(r.unraid_disks())
        self.assertEqual([x["name"] for x in d], ["parity", "disk1", "disk2", "cache"])
        self.assertEqual(d[0], {"name": "parity", "type": "Parity", "status": "DISK_OK", "temp_c": 31, "errors": 0,
                                "size_gb": "", "free_gb": ""})
        self.assertEqual((d[1]["type"], d[1]["temp_c"], d[1]["size_gb"], d[1]["free_gb"]), ("Data", 32, 3815.45, 1024))
        self.assertEqual(d[3]["type"], "Cache")
        s = asyncio.run(r.unraid_shares())
        self.assertEqual(s, [{"name": "media", "free_gb": 1024, "used_gb": 1024, "total_gb": 2048},
                             {"name": "backups", "free_gb": 512, "used_gb": 1536, "total_gb": 2048}])
        c = asyncio.run(r.unraid_containers())
        self.assertEqual([(x["name"], x["state"], x["auto_start"]) for x in c],
                         [("plex", "running", True), ("pihole", "exited", True)])
        self.assertEqual(c[0]["status"], "Up 2 days")
        v = asyncio.run(r.unraid_vms())
        self.assertEqual(v, [{"name": "windows", "state": "RUNNING"}, {"name": "arch", "state": "SHUTOFF"}])
        self.assertEqual((self.fake.refused, self.fake.done, self.asked), ([], [], []))

    def test_power_and_parity_ask_every_time(self):
        r = self.runtime(answers=[True, False, True])
        self.assertTrue(asyncio.run(r.unraid_power("container", "start", "plex")))
        self.assertFalse(asyncio.run(r.unraid_power("container", "start", "plex")))
        self.assertTrue(asyncio.run(r.unraid_parity()))
        self.assertEqual(self.fake.done, ["start container plex", "check parity"])
        self.assertIn("start the Unraid container plex", self.asked[0])
        self.assertIn("check Unraid's parity", self.asked[2])
        self.assertEqual(len(self.asked), 3)

    def test_nobody_there_means_it_never_runs(self):
        for label, kw in (("no keyboard", {"here": False}), ("GitHub Actions", {"env": {"GITHUB_ACTIONS": "true"}})):
            with self.subTest(label):
                r = self.runtime(**kw)
                self.assertFalse(asyncio.run(r.unraid_power("vm", "start", "windows")))
                self.assertFalse(asyncio.run(r.unraid_parity()))
                self.assertEqual((self.asked, self.fake.done), ([], []))

    def test_a_test_run_and_bad_names_do_nothing(self):
        r = self.runtime()
        r.testing = True
        self.assertFalse(asyncio.run(r.unraid_power("container", "start", "plex")))
        self.assertFalse(asyncio.run(r.unraid_parity()))
        r.testing = False
        for kind, action, name in (("array", "start", "disk1"), ("container", "restart", "plex"), ("vm", "start", "")):
            with self.assertRaises(RunError, msg=f"{kind} {action} {name}"):
                asyncio.run(r.unraid_power(kind, action, name))
        self.assertEqual((self.asked, self.fake.done, self.fake.calls), ([], [], []))

    def test_a_mutation_without_a_yes_never_leaves(self):
        r = self.runtime()
        with self.assertRaises(RunError):
            asyncio.run(r._unraid('mutation{docker{restart(id:"container:plex"){id}}}'))
        with self.assertRaises(RunError):
            asyncio.run(r._unraid('mutation{array{setState(input:{desiredState: STOP}){state}}}', approved=True))
        self.assertEqual(self.fake.calls, [])

    def test_without_settings_it_says_what_it_needs(self):
        with mock.patch.dict(os.environ, {"UNRAID_URL": "", "UNRAID_API_KEY": ""}):
            r = Runtime()
            r.reset()
            with self.assertRaises(RunError) as e:
                asyncio.run(r.unraid_array())
        self.assertIn("UNRAID_URL", str(e.exception))

    def test_doctor_says_the_version(self):
        r = self.runtime()
        [(area, run)] = [c for c in asyncio.run(r._doctor_connections(["unraid_read"], [])) if c[0] == "Unraid"]
        self.assertEqual(asyncio.run(run()), "Unraid 7.2.1, array STARTED")


if __name__ == "__main__":
    unittest.main()
