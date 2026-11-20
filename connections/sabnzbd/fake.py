"""A stand-in for SABnzbd's API (#397), serving the sample queue the page uses (samples/connections.json,
"sabnzbd"), shaped the way SABnzbd answers: mode=queue, mode=history and mode=diskspace as JSON.

Pause and resume are recorded in .powered (as "pause"). Anything else is recorded in .refused and answered
403, so a test can show nothing else was sent.

    sabnzbd = FakeSabnzbd()
    host = sabnzbd.start()          # http://127.0.0.1:port, for SABNZBD_URL
"""
import json
import pathlib
import socketserver
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

ROOT = pathlib.Path(__file__).resolve().parent.parent
FREE = ("queue", "history", "diskspace")
ASKS = ("pause", "resume")


class FakeSabnzbd:
    def __init__(self, data=None):
        self.data = data or json.loads((ROOT / "samples" / "connections.json").read_text(encoding="utf-8"))["sabnzbd"]
        self.calls, self.refused, self.powered = [], [], []

    def answer(self, method, path, query):
        """(status, body)."""
        mode = (query.get("mode") or [""])[0]
        as_json = lambda o: (200, json.dumps(o).encode())  # noqa: E731
        if method == "GET" and path == "/api" and mode in FREE:
            if mode == "history":  # finished two and three hours ago, so the hours filter can be tested forever
                slots = [dict(s, completed=str(int(time.time()) - 7200)) for s in self.data["history"]["slots"][:1]] + \
                        [dict(s, completed=str(int(time.time()) - 10800)) for s in self.data["history"]["slots"][1:]]
                return as_json({"history": {"slots": slots}})
            return as_json({mode: self.data[mode]})
        if method == "GET" and path == "/api" and mode in ASKS:
            self.powered.append(mode)
            return as_json({"status": True})
        self.refused.append(f"{method} {path} {mode}".strip())
        return 403, json.dumps({"status": False, "error": "Refused"}).encode()

    def start(self):
        fake = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def address_string(self):
                return "client"

            def do_GET(self):
                u = urlparse(self.path)
                fake.calls.append(f"GET {u.path} {(parse_qs(u.query).get('mode') or [''])[0]}")
                status, body = fake.answer("GET", u.path, parse_qs(u.query))
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def do_POST(self):
                u = urlparse(self.path)
                self.rfile.read(int(self.headers.get("Content-Length") or 0))
                fake.calls.append(f"POST {u.path} {(parse_qs(u.query).get('mode') or [''])[0]}")
                status, body = fake.answer("POST", u.path, parse_qs(u.query))
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.server.handle_error = lambda request, address: None
        threading.Thread(target=self.server.serve_forever, kwargs={"poll_interval": 0.02}, daemon=True).start()
        return f"http://127.0.0.1:{self.server.server_address[1]}"

    def stop(self):
        self.server.shutdown()
        self.server.server_close()
