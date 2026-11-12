"""A stand-in for Unraid's GraphQL API (#399), serving the sample the page uses (samples/connections.json,
"unraid"), shaped the way it answers: POST /graphql with {"query": "..."} gives {"data": {...}}.

The reads the runtime makes are answered from the sample. The allowed mutations (starting or stopping one
container or VM, a parity read-check) are recorded in .done (as "start container plex"); anything else is
recorded in .refused and answered 403, so a test can show nothing else was sent.

    unraid = FakeUnraid()
    host = unraid.start()          # http://127.0.0.1:port, for UNRAID_URL
"""
import json
import pathlib
import re
import socketserver
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

ROOT = pathlib.Path(__file__).resolve().parent.parent
QUERIES = {
    "query{array{state capacity{kilobytes{free total}}}info{os{uptime}}}": ("array", "info"),
    "query{vars{version}array{state}}": ("vars", "array"),
}
DISK_QUERY = re.compile(r"^query\{array\{parities\{.*\}disks\{.*\}caches\{.*\}\}\}$")
DISK_MUTATION = re.compile(r'^mutation\{docker\{(start|stop)\(id:"container:([^"]+)"\)\{id\}\}\}$')
VM_MUTATION = re.compile(r'^mutation\{vm\{(start|stop)\(id:"vm:([^"]+)"\)\}\}$')


class FakeUnraid:
    def __init__(self, data=None):
        self.data = data or json.loads((ROOT / "samples" / "connections.json").read_text(encoding="utf-8"))["unraid"]
        self.calls, self.refused, self.done = [], [], []
        self.version = self.data["vars"]["version"]

    def answer(self, method, path, query, body):
        """(status, body)."""
        as_json = lambda o: (200, json.dumps(o).encode())  # noqa: E731
        if method == "POST" and path == "/graphql":
            q = (json.loads(body or b"{}") or {}).get("query") or ""
            self.calls.append(q[:60])
            if q in QUERIES:
                return as_json({"data": {k: self.data.get(k) for k in QUERIES[q]}})
            if q == "query{shares{name free used size}}":
                return as_json({"data": {"shares": self.data["shares"]}})
            if q == "query{dockerContainers{id names state status autoStart}}":
                return as_json({"data": {"dockerContainers": self.data["dockerContainers"]}})
            if q == "query{vms{domains{id name state}}}":
                return as_json({"data": {"vms": self.data["vms"]}})
            if DISK_QUERY.match(q):
                return as_json({"data": {"array": self.data["array"]}})
            m = DISK_MUTATION.match(q)
            if m:
                self.done.append(f"{m.group(1)} container {m.group(2)}")
                return as_json({"data": {"docker": {m.group(1): {"id": "container:" + m.group(2)}}}})
            m = VM_MUTATION.match(q)
            if m:
                self.done.append(f"{m.group(1)} vm {m.group(2)}")
                return as_json({"data": {"vm": {m.group(1): True}}})
            if q == "mutation{parity{start(correct:false)}}":
                self.done.append("check parity")
                return as_json({"data": {"parity": {"start": True}}})
        self.refused.append(f"{method} {path} {body[:60] if body else ''}".rstrip())
        return 403, json.dumps({"errors": [{"message": "Forbidden"}]}).encode()

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
