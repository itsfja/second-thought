"""Docker through its Engine API (#358), against tests/fake_docker.py: reads go without asking, restart, stop and start
always ask and never run unattended, protected containers are never touched, and nothing else is ever sent."""
import asyncio
import importlib.util
import os
import sys
import tempfile
import unittest
from unittest import mock

import support
from second_thought.core import SAFETY, RunError, docker_call
from second_thought.runtime import Runtime

sys.path.insert(0, str(support.ROOT / "tests"))
import fake_docker  # noqa: E402

HAVE_CRYPTO = importlib.util.find_spec("cryptography") is not None


class AtKeyboard:
    def isatty(self):
        return True


class Calls(unittest.TestCase):
    def test_reads_power_and_never(self):
        for path in ("/version", "/containers/json", "/containers/sonarr/json", "/containers/socket-proxy/stats", "/containers/a_b.c/logs"):
            self.assertEqual(docker_call("GET", path), "free", path)
        for action in ("restart", "stop", "start"):
            self.assertEqual(docker_call("POST", f"/containers/sonarr/{action}"), "asks")
        for method, path in [("POST", "/containers/sonarr/exec"), ("POST", "/exec/abc/start"), ("POST", "/containers/create"),
                             ("DELETE", "/containers/sonarr"), ("POST", "/containers/sonarr/kill"), ("POST", "/containers/sonarr/update"),
                             ("POST", "/images/create"), ("POST", "/build"), ("GET", "/images/json"), ("DELETE", "/volumes/data"),
                             ("POST", "/networks/create"), ("GET", "/containers/sonarr/archive"), ("GET", "/containers/sonarr/export"),
                             ("POST", "/containers/prune"), ("GET", "/containers/../version"), ("GET", "/containers/sonarr/logs/x"),
                             ("GET", "/v1.47/containers/sonarr/exec")]:
            self.assertIsNone(docker_call(method, path), f"{method} {path}")
        self.assertEqual({m for m, _ in SAFETY["docker_free"]}, {"GET"})


class Stack(unittest.TestCase):
    def runtime(self, here=True, env=None, answers=(), **start):
        self.fake = fake_docker.FakeDocker()
        host = self.fake.start(**start)
        self.addCleanup(self.fake.stop)
        patches = [mock.patch.dict(os.environ, dict({"DOCKER_HOST": host, "DOCKER_PROTECT": "socket-proxy, plex", "DOCKER_TLS_VERIFY": "", "DOCKER_CERT_PATH": ""},
                                                    **(env or {}))),
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

    def test_containers_stats_and_logs(self):
        r = self.runtime()
        cs = asyncio.run(r.docker_containers())
        self.assertEqual([c["name"] for c in cs], ["old-test", "plex", "prowlarr", "qbittorrent", "radarr", "socket-proxy", "sonarr"])
        self.assertEqual(cs[2], {"name": "prowlarr", "image": "lscr.io/linuxserver/prowlarr:latest", "state": "restarting",
                                 "status": "Restarting (1) 20 seconds ago", "health": "", "restarts": 7, "started": "2026-11-10 07:58"})
        self.assertEqual((cs[3]["health"], cs[1]["health"], cs[0]["state"]), ("unhealthy", "healthy", "exited"))
        stats = asyncio.run(r.docker_stats())
        self.assertEqual([s["name"] for s in stats], ["plex", "prowlarr", "qbittorrent", "radarr", "socket-proxy", "sonarr"], "the stopped one left out")
        self.assertEqual(stats[0], {"name": "plex", "cpu": 8, "memory_mb": 1900, "limit_mb": 2048, "memory": 92.8})
        self.assertEqual((stats[5]["memory_mb"], stats[5]["limit_mb"], stats[5]["cpu"]), (402.25, 8192, 3))
        logs = asyncio.run(r.docker_logs("/qbittorrent", 2))
        self.assertEqual(logs, ["(W) 2026-11-10T07:55:30 - Tracker 'udp://tracker.example.org:1337' unreachable",
                                "(C) 2026-11-10T07:56:02 - Disk I/O error on /downloads: Input/output error"], "output and errors together, unframed")
        self.assertEqual(asyncio.run(r.docker_logs("radarr")), [])
        with self.assertRaises(RunError) as e:
            asyncio.run(r.docker_logs("nothere"))
        self.assertIn("not found", str(e.exception))
        self.assertEqual((self.asked, self.fake.refused), ([], []))
        self.assertEqual({c.split()[0] for c in self.fake.calls}, {"GET"})

    @unittest.skipIf(os.name == "nt", "no Unix sockets on Windows")
    def test_the_socket_itself(self):
        with tempfile.TemporaryDirectory() as tmp:  # a short path: Unix sockets have a small limit
            r = self.runtime(unix=os.path.join(tmp, "docker.sock"))
            self.assertEqual(len(asyncio.run(r.docker_containers())), 7)

    @unittest.skipUnless(HAVE_CRYPTO, "needs the cryptography package")
    def test_tls_checks_the_certificate_against_ca_pem(self):
        with tempfile.TemporaryDirectory(dir=support.TMP) as certs, tempfile.TemporaryDirectory(dir=support.TMP) as empty:
            r = self.runtime(tls=certs, env={"DOCKER_TLS_VERIFY": "1", "DOCKER_CERT_PATH": certs})
            self.assertEqual(len(asyncio.run(r.docker_stats())), 6)
            with mock.patch.dict(os.environ, {"DOCKER_CERT_PATH": empty}):
                with self.assertRaises(RunError) as e:
                    asyncio.run(r.docker_stats())
            self.assertIn("certificate", str(e.exception).lower())

    def test_power_asks_every_time(self):
        r = self.runtime(answers=[True, False])
        self.assertTrue(asyncio.run(r.docker_power("restart", "prowlarr")))
        self.assertFalse(asyncio.run(r.docker_power("stop", "sonarr")))
        self.assertEqual(self.fake.powered, ["restart prowlarr"])
        self.assertIn("restart the Docker container prowlarr (lscr.io/linuxserver/prowlarr:latest, now restarting)", self.asked[0])
        self.assertEqual(len(self.asked), 2)

    def test_protected_containers_are_never_touched(self):
        r = self.runtime()
        for name in ("socket-proxy", "Plex", "/plex"):
            self.assertFalse(asyncio.run(r.docker_power("restart", name)))
        self.assertEqual((self.asked, self.fake.powered), ([], []))
        self.assertTrue(any("DOCKER_PROTECT" in str(a) for a in self.logged))

    def test_nobody_there_means_it_never_runs(self):
        for label, kw in (("no keyboard", {"here": False}), ("GitHub Actions", {"env": {"GITHUB_ACTIONS": "true"}})):
            with self.subTest(label):
                r = self.runtime(**kw)
                self.assertFalse(asyncio.run(r.docker_power("restart", "sonarr")))
                self.assertEqual((self.asked, self.fake.powered), ([], []))

    def test_a_test_run_and_bad_requests_do_nothing(self):
        r = self.runtime()
        r.testing = True
        self.assertFalse(asyncio.run(r.docker_power("restart", "sonarr")))
        r.testing = False
        for action, name in (("kill", "sonarr"), ("rm", "sonarr"), ("exec", "sonarr"), ("restart", "son arr"), ("restart", "../version"),
                             ("restart", "a/b"), ("restart", ""), ("restart", "nothere")):
            with self.assertRaises(RunError, msg=f"{action} {name}"):
                asyncio.run(r.docker_power(action, name))
        self.assertEqual((self.asked, self.fake.powered, self.fake.refused), ([], [], []))

    def test_a_power_call_without_a_yes_never_leaves(self):
        r = self.runtime()
        with self.assertRaises(RunError):
            asyncio.run(r._docker("POST", "/containers/sonarr/restart"))
        with self.assertRaises(RunError):
            asyncio.run(r._docker("POST", "/containers/sonarr/exec", approved=True))
        self.assertEqual(self.fake.calls, [])

    def test_doctor_says_the_version(self):
        r = self.runtime()
        [(area, run)] = [c for c in asyncio.run(r._doctor_connections(["docker_read"], [])) if c[0] == "Docker"]
        self.assertEqual(asyncio.run(run()), "Docker 27.3.1, 7 containers")

    def test_windows_without_an_address_is_told(self):
        r = self.runtime()
        with mock.patch.dict(os.environ, {"DOCKER_HOST": "npipe:////./pipe/docker_engine"}):
            with self.assertRaises(RunError) as e:
                asyncio.run(r.docker_containers())
        self.assertIn("tcp://", str(e.exception))


if __name__ == "__main__":
    unittest.main()
