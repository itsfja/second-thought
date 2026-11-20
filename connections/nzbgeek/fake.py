"""A stand-in for NZBGeek's Newznab API (#400), serving the sample the page uses (samples/connections.json,
"nzbgeek"), shaped the way it answers with o=json: GET /api?t=search&q=... gives {"channel": {"item": [...]}}.

GET /api?t=get&id=... (an NZB file) is recorded in .fetched (as the id) and answered with a small NZB file;
GET /api?t=caps says a version and a retention. Anything else is recorded in .refused and answered 403, so a
test can show nothing else was sent.

    geek = FakeNzbgeek()
    host = geek.start()          # http://127.0.0.1:port, for NZBGEEK_URL
"""
import json
import pathlib
import socketserver
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

ROOT = pathlib.Path(__file__).resolve().parent.parent
NZB = b'<?xml version="1.0" encoding="UTF-8"?>\n<nzb xmlns="http://www.newznab.com/DTD/2010/feeds/attributes/">\n</nzb>\n'


class FakeNzbgeek:
    def __init__(self, data=None):
        self.data = data or json.loads((ROOT / "samples" / "connections.json").read_text(encoding="utf-8"))["nzbgeek"]
        self.calls, self.refused, self.fetched = [], [], []
        self.version = "1.0"
        self.retention = 4000

    def answer(self, method, path, query, body):
        """(status, body)."""
        as_json = lambda o: (200, json.dumps(o).encode())  # noqa: E731
        q = {k: v[0] for k, v in (query or {}).items()}
        if method == "GET" and path == "/api":
            t = q.get("t", "")
            if t == "search" and q.get("o") == "json":
                return as_json({"channel": {"title": "NZBGeek", "item": self.data["search"]}})
            if t == "caps" and q.get("o") == "json":
                return as_json({"caps": {"server": {"@attributes": {"version": self.version, "title": "NZBGeek"}},
                                        "retention": {"@attributes": {"days": str(self.retention)}}}})
            if t == "get" and q.get("id"):
                self.fetched.append(q["id"])
                return 200, NZB
        self.refused.append(f"{method} {path}?{ '&'.join(f'{k}={v}' for k, v in sorted(q.items())) }".rstrip("?"))
        return 403, json.dumps({"error": {"code": 403, "description": "Forbidden"}}).encode()

    def start(self):
        fake = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def address_string(self):
                return "client"

            def _go(self, method):
                u = urlparse(self.path)
                body = self.rfile.read(int(self.headers.get("Content-Length") or 0)) if method != "GET" else b""
                fake.calls.append(f"{method} {u.path}?{u.query}")
                status, out = fake.answer(method, u.path, parse_qs(u.query), body)
                self.send_response(status)
                self.send_header("Content-Type", "application/json" if out[:1] == b"{" else "application/xml")
                self.send_header("Content-Length", str(len(out)))
                self.end_headers()
                self.wfile.write(out)

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
        threading.Thread(target=self.server.serve_forever, kwargs={"poll_interval": 0.02}, daemon=True).start()
        return f"http://127.0.0.1:{self.server.server_address[1]}"

    def stop(self):
        self.server.shutdown()
        self.server.server_close()
