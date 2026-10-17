"""Web requests: only this computer can reach the listener unless WEBHOOK_HOST opens it up (#106)."""
import asyncio
import contextlib
import os
import socket
import threading
import unittest
import urllib.error
import urllib.request

import support  # noqa: F401  (settings that can't leak in from your machine)
from second_thought.connectors import webhook_host
from second_thought.runtime import Runtime


def lan_address():
    """This computer's address on its network (not 127.x), or None if it has none."""
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        try:
            s.connect(("10.255.255.255", 1))  # UDP: nothing is sent, it only picks the outgoing address
            ip = s.getsockname()[0]
        except OSError:
            return None
    return None if ip.startswith("127.") else ip


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@contextlib.contextmanager
def env(**values):
    old = {k: os.environ.get(k) for k in values}
    os.environ.update({k: v for k, v in values.items() if v is not None})
    for k, v in values.items():
        if v is None:
            os.environ.pop(k, None)
    try:
        yield
    finally:
        for k, v in old.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


DIRECT = urllib.request.build_opener(urllib.request.ProxyHandler({}))  # straight there, whatever proxy is set


def reaches(host, port):
    """True if the listener answers at http://host:port/ping. Asked without the key, so it only refuses (403) and runs nothing."""
    try:
        DIRECT.open(f"http://{host}:{port}/ping", timeout=3)
        return True
    except urllib.error.HTTPError as e:
        return e.code == 403
    except OSError:
        return False


def listening(**settings):
    """Start the real web-request listener in a thread, with these settings; return its port."""
    port = free_port()

    def run():
        asyncio.new_event_loop().run_until_complete(Runtime()._listen_webhook([("ping", lambda *a: None)]))

    # The listener reads its settings once, as it starts, so they're put back as soon as it answers.
    with env(WEBHOOK_SECRET="s3cret", WEBHOOK_PORT=str(port), **settings):
        threading.Thread(target=run, daemon=True).start()
        for _ in range(200):  # 127.0.0.1 answers either way
            if reaches("127.0.0.1", port):
                break
            threading.Event().wait(0.05)
    return port


class Default(unittest.TestCase):
    def test_default_is_this_computer_only(self):
        with env(WEBHOOK_HOST=None):
            self.assertEqual(webhook_host(), "127.0.0.1")
        with env(WEBHOOK_HOST="  "):
            self.assertEqual(webhook_host(), "127.0.0.1", "a blank line in the ini counts as not set")
        with env(WEBHOOK_HOST="0.0.0.0"):
            self.assertEqual(webhook_host(), "0.0.0.0")


@unittest.skipUnless(lan_address(), "this computer has no network address besides 127.0.0.1")
class Listener(unittest.TestCase):
    def test_other_computers_cant_reach_it_by_default(self):
        port = listening(WEBHOOK_HOST=None)
        self.assertTrue(reaches("127.0.0.1", port), "this computer can call it")
        self.assertFalse(reaches(lan_address(), port), "nothing else on the network can")

    def test_webhook_host_opens_it_to_the_network(self):
        port = listening(WEBHOOK_HOST="0.0.0.0")
        self.assertTrue(reaches(lan_address(), port), "with WEBHOOK_HOST = 0.0.0.0, the network can call it")


if __name__ == "__main__":
    unittest.main()
