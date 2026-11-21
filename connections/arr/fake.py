"""A stand-in for Radarr and Sonarr's Servarr API (#398), serving the sample the page uses (samples/
connections.json, "arr"), shaped the way they answer: GET /api/v3/queue, wanted/missing, diskspace and
system/status as JSON.

POST /api/v3/command is recorded in .searched (as "radarr MissingMovieSearch"); its name is checked against
ARR_SEARCH. Anything else is recorded in .refused and answered 403, so a test can show nothing else was sent.

    arr = FakeArr("radarr")
    host = arr.start()          # http://127.0.0.1:port, for RADARR_URL
"""
import json
import pathlib
import socketserver
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

ROOT = pathlib.Path(__file__).resolve().parent.parent
FREE = ("/api/v3/queue", "/api/v3/wanted/missing", "/api/v3/diskspace", "/api/v3/system/status")
NAMES = {"radarr": "MissingMovieSearch", "sonarr": "MissingEpisodeSearch"}


class FakeArr:
    def __init__(self, which, data=None):
        self.which = which
        self.data = (data or json.loads((ROOT / "samples" / "connections.json").read_text(encoding="utf-8"))["arr"])[which]
        self.calls, self.refused, self.searched = [], [], []
        self.version = "4.7.5.8805"

    def answer(self, method, path, query, body):
        """(status, body)."""
        as_json = lambda o: (200, json.dumps(o).encode())  # noqa: E731
        if method == "GET" and path == "/api/v3/system/status":
            return as_json({"version": self.version})
        if method == "GET" and path in FREE:
            if path == "/api/v3/queue":
                return as_json({"page": 1, "records": self.data["queue"], "totalRecords": len(self.data["queue"])})
            if path == "/api/v3/wanted/missing":
                return as_json({"page": 1, "records": self.data["missing"]})
            return as_json(self.data["diskspace"])
        if method == "POST" and path == "/api/v3/command":
            name = (json.loads(body or b"{}") or {}).get("name")
            if name == NAMES[self.which]:
                self.searched.append(f"{self.which} {name}")
                return as_json({"id": 1})
        self.refused.append(f"{method} {path}")
        return 403, json.dumps({"message": "Forbidden"}).encode()

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
                fake.calls.append(f"{method} {u.path}")
                status, out = fake.answer(method, u.path, parse_qs(u.query), body)
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
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
