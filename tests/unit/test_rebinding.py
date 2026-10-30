"""Reading pages and feeds can't be turned onto your own network by a name that changes its answer (DNS rebinding):
each name is looked up once, checked, and that exact address is used, directly or through a proxy."""
import http.server
import os
import socket
import threading
import unittest
from unittest import mock

import support  # noqa: F401
from second_thought import connectors
from second_thought.core import RunError

REAL = socket.getaddrinfo
PUBLIC, PRIVATE = "93.184.216.34", "10.0.0.5"


class Resolver:
    """Answers for made-up names: rebind.example is public the first time and private after that."""
    def __init__(self):
        self.asked = []

    def __call__(self, host, port, *a, **kw):
        if host in ("127.0.0.1", "localhost"):
            return REAL(host, port, *a, **kw)
        self.asked.append(host)
        ip = {"public.example": PUBLIC, "private.example": PRIVATE}.get(host)
        if host == "rebind.example":
            ip = PUBLIC if self.asked.count(host) == 1 else PRIVATE
        if ip is None:
            raise socket.gaierror("unknown")
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (ip, port or 80))]


class Proxy(http.server.BaseHTTPRequestHandler):
    seen = []

    def log_message(self, *a):
        pass

    def do_GET(self):
        Proxy.seen.append(("GET", self.path, self.headers.get("Host"), self.headers.get("Proxy-Authorization")))
        if self.path.endswith("/go"):
            self.send_response(302)
            self.send_header("Location", "http://private.example/")
            self.end_headers()
            return
        body = b"<title>ok</title>hello"
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_CONNECT(self):
        Proxy.seen.append(("CONNECT", self.path, None, self.headers.get("Proxy-Authorization")))
        self.send_response(502)  # no real website behind it: the test only needs to see where the tunnel was asked to go
        self.end_headers()


class Rebinding(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Proxy)
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()
        cls.proxy = f"http://127.0.0.1:{cls.server.server_address[1]}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()

    def setUp(self):
        Proxy.seen.clear()
        self.resolver = Resolver()
        clean = {k: v for k, v in os.environ.items() if k.lower() not in ("http_proxy", "https_proxy", "no_proxy", "all_proxy", "rb_local_pages")}
        self.env = mock.patch.dict(os.environ, clean, clear=True)
        self.env.start()
        self.dns = mock.patch("socket.getaddrinfo", self.resolver)
        self.dns.start()

    def tearDown(self):
        self.dns.stop()
        self.env.stop()

    def use_proxy(self, url=None):
        os.environ["http_proxy"] = os.environ["https_proxy"] = url or self.proxy

    def test_direct_connections_use_the_address_that_was_checked(self):
        tried = []

        def connect(sock, addr):
            tried.append(addr[0])
            raise OSError("not really connecting")
        with mock.patch.object(socket.socket, "connect", connect):
            with self.assertRaises(RunError):
                connectors.get_url("http://rebind.example/")
        self.assertEqual((tried, self.resolver.asked), ([PUBLIC], ["rebind.example"]))

    def test_a_private_address_is_refused(self):
        with self.assertRaises(RunError) as e:
            connectors.get_url("http://private.example/")
        self.assertIn("your own network", str(e.exception))

    def test_through_a_proxy_the_request_names_the_checked_address(self):
        self.use_proxy()
        ctype, data = connectors.get_url("http://rebind.example/page?q=1")
        self.assertEqual(data, b"<title>ok</title>hello")
        self.assertEqual(Proxy.seen, [("GET", f"http://{PUBLIC}:80/page?q=1", "rebind.example", None)])
        self.assertEqual(self.resolver.asked, ["rebind.example"])

    def test_through_a_proxy_a_redirect_is_checked_too(self):
        self.use_proxy()
        with self.assertRaises(RunError) as e:
            connectors.get_url("http://public.example/go")
        self.assertIn("your own network", str(e.exception))
        self.assertEqual(len(Proxy.seen), 1)

    def test_through_a_proxy_https_tunnels_to_the_checked_address(self):
        self.use_proxy(self.proxy.replace("http://", "http://me:secret@"))
        with self.assertRaises(RunError):
            connectors.get_url("https://rebind.example/")
        self.assertEqual(Proxy.seen[0][:2], ("CONNECT", f"{PUBLIC}:443"))
        self.assertTrue(Proxy.seen[0][3].startswith("Basic "))

    def test_addresses_from_your_settings_are_trusted(self):
        tried = []

        def connect(sock, addr):
            tried.append(addr[0])
            raise OSError("not really connecting")
        with mock.patch.object(socket.socket, "connect", connect), self.assertRaises(RunError):
            connectors.get_url("http://private.example/", trusted=True)
        self.assertEqual(tried, [PRIVATE])


if __name__ == "__main__":
    unittest.main()
