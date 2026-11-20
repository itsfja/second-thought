"""A stand-in for Pi-hole's REST API (#401, v6 and later), serving the sample the page uses (samples/
connections.json, "pihole"), shaped the way it answers: POST /api/auth with the right password gives a session id
that the reads and the changes must carry as X-FTL-SID; GET /api/stats/summary, /api/stats/top_domains,
/api/stats/top_clients and /api/dns/blocking give the sample; POST /api/dns/blocking and POST/DELETE
/api/domains/{allow,deny}list/exact are recorded in .changed (as "POST /api/dns/blocking {: ...}").

Anything else, or a request without a valid session id, is recorded in .refused and answered 401 or 403, so a test
can show nothing else was sent. Setting .expire_sid makes the next request answer 401 once, to show the runtime
signs in again.

    hole = FakePihole()
    host = hole.start()          # http://127.0.0.1:port, for PIHOLE_URL
"""
import json
import pathlib
import socketserver
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

ROOT = pathlib.Path(__file__).resolve().parent.parent


class FakePihole:
    def __init__(self, data=None, password="pw"):
        self.data = data or json.loads((ROOT / "samples" / "connections.json").read_text(encoding="utf-8"))["pihole"]
        self.password = password
        self.calls, self.refused, self.changed = [], [], []
        self.signins = 0
        self.expire_sid = False

    def answer(self, method, path, query, body, sid):
        """(status, body, sid)."""
        as_json = lambda o: (200, json.dumps(o).encode())  # noqa: E731
        if method == "POST" and path == "/api/auth":
            self.signins += 1
            if (json.loads(body or b"{}") or {}).get("password") == self.password:
                sid = "sid-{}".format(self.signins)
                return 200, json.dumps({"session": {"sid": sid, "valid": True}}).encode(), sid
            return 401, json.dumps({"error": {"key": "bad_password", "message": "Incorrect password"}}).encode(), sid
        if not sid:
            return 401, json.dumps({"error": {"key": "unauthorized", "message": "Unauthorized"}}).encode(), None
        if self.expire_sid:
            self.expire_sid = False
            return 401, json.dumps({"error": {"key": "unauthorized", "message": "Unauthorized"}}).encode(), None
        if method == "GET" and path == "/api/stats/summary":
            return as_json(self.data["summary"]) + (sid,)
        if method == "GET" and path == "/api/dns/blocking":
            return as_json({"blocking": self.data["blocking"]}) + (sid,)
        if method == "GET" and path == "/api/stats/top_domains":
            n = int((query or {}).get("count", (5,))[0])
            return as_json({"domains": self.data["top_domains"][:n]}) + (sid,)
        if method == "GET" and path == "/api/stats/top_clients":
            n = int((query or {}).get("count", (5,))[0])
            return as_json({"clients": self.data["top_clients"][:n]}) + (sid,)
        if method == "POST" and path == "/api/dns/blocking":
            self.changed.append(f"POST {path} {body.decode() if body else ''}")
            return as_json({"blocking": json.loads(body or b"{}").get("blocking")}) + (sid,)
        if method in ("POST", "DELETE") and path in ("/api/domains/allowlist/exact", "/api/domains/denylist/exact"):
            self.changed.append(f"{method} {path} {body.decode() if body else ''}")
            return as_json({}) + (sid,)
        self.refused.append(f"{method} {path}")
        return 403, json.dumps({"error": {"key": "bad_request", "message": "Not allowed"}}).encode(), sid

    def start(self):
        fake = self
        fake.sid = None

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def address_string(self):
                return "client"

            def _go(self, method):
                u = urlparse(self.path)
                body = self.rfile.read(int(self.headers.get("Content-Length") or 0)) if method != "GET" else b""
                fake.calls.append(f"{method} {u.path}")
                sid = self.headers.get("X-FTL-SID") or fake.sid
                status, out, sid = fake.answer(method, u.path, parse_qs(u.query), body, sid)
                fake.sid = sid or fake.sid
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
