"""A stand-in for a UniFi OS console's Network API (#359), the Integration API, serving the sample network the page uses
(samples/connections.json, "unifi"), shaped the way the console answers, a page of results at a time.

It checks the X-API-KEY header and answers only reading. Anything else is recorded in .refused and answered 400, so a
test can show nothing else was ever sent. With tls=True it serves HTTPS with a new self-signed certificate, as a
console does (see fake_mikrotik.self_signed); .fingerprint is its SHA-256.

    unifi = FakeUnifi()
    url = unifi.start()          # then UNIFI_URL = url, UNIFI_API_KEY = fake_unifi.KEY
    unifi.calls, unifi.refused
"""
import hashlib
import json
import pathlib
import ssl
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

ROOT = pathlib.Path(__file__).resolve().parent.parent
KEY = "test-unifi-key"
API = "/proxy/network/integration/v1"


class FakeUnifi:
    def __init__(self, tls=False, data=None, key=KEY, page=2):
        self.data = data or json.loads((ROOT / "samples" / "connections.json").read_text(encoding="utf-8"))["unifi"]
        self.tls, self.key, self.page = tls, key, page  # page: at most this many a page, so paging is tested
        self.calls, self.refused = [], []
        self.fingerprint = None

    def answer(self, method, path, query):
        d = self.data
        site = d["sites"][0]["id"]
        lists = {f"{API}/sites": d["sites"], f"{API}/sites/{site}/devices": d["devices"], f"{API}/sites/{site}/clients": d["clients"]}
        if method == "GET" and path == f"{API}/info":
            return 200, d["info"]
        if method == "GET" and path in lists:
            items = lists[path]
            offset = int(query.get("offset", ["0"])[0])
            limit = min(int(query.get("limit", ["25"])[0]), self.page)
            data = items[offset:offset + limit]
            return 200, {"offset": offset, "limit": limit, "count": len(data), "totalCount": len(items), "data": data}
        prefix = f"{API}/sites/{site}/devices/"
        if method == "GET" and path.startswith(prefix) and path.endswith("/statistics/latest"):
            stats = d["statistics"].get(path[len(prefix):-len("/statistics/latest")])
            return (200, stats) if stats else (404, {"statusCode": 404, "message": "not found"})
        self.refused.append(f"{method} {path}")
        return 400, {"statusCode": 400, "message": "not in the stand-in"}

    def start(self):
        fake = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def _go(self, method):
                u = urlparse(self.path)
                if method != "GET":
                    self.rfile.read(int(self.headers.get("Content-Length") or 0))
                fake.calls.append(f"{method} {u.path}")
                if self.headers.get("X-API-KEY") != fake.key:
                    status, out = 401, {"statusCode": 401, "message": "Unauthorized"}
                else:
                    status, out = fake.answer(method, u.path, parse_qs(u.query))
                data = json.dumps(out).encode()
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def do_GET(self):
                self._go("GET")

            def do_POST(self):
                self._go("POST")

            def do_PUT(self):
                self._go("PUT")

            def do_DELETE(self):
                self._go("DELETE")

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.server.handle_error = lambda request, address: None
        if self.tls:
            from fake_mikrotik import self_signed
            self._dir = tempfile.TemporaryDirectory()
            cert, key, der = self_signed(self._dir.name)
            self.fingerprint = hashlib.sha256(der).hexdigest()
            ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            ctx.load_cert_chain(cert, key)
            self.server.socket = ctx.wrap_socket(self.server.socket, server_side=True)
        threading.Thread(target=self.server.serve_forever, kwargs={"poll_interval": 0.02}, daemon=True).start()
        return f"{'https' if self.tls else 'http'}://127.0.0.1:{self.server.server_address[1]}"

    def stop(self):
        self.server.shutdown()
        self.server.server_close()
